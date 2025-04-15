# Copyright (c) 2024, Zhendong Peng (pzd17@tsinghua.org.cn)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from functools import partial
from typing import List

import torch
from asr_decoder import CTCDecoder
from funasr import AutoModel
from funasr.frontends.wav_frontend import load_cmvn
from online_fbank import OnlineFbank
import numpy as np

from .sensevoice import SenseVoiceSmall


sensevoice_models = {}


class StreamingSenseVoice:
    def __init__(
        self,
        chunk_size: int = 10,
        padding: int = 8,
        beam_size: int = 3,
        contexts: List[str] = None,
        language: str = "zh",
        textnorm: bool = False,
        device: str = "cpu",
        model: str = "iic/SenseVoiceSmall",
    ):
        """
        Args:
        language:
            If not empty, then valid values are: auto, zh, en, ja, ko, yue
        textnorm:
            True to enable inverse text normalization; False to disable it.
        """
        self.device = device
        self.model, kwargs = self.load_model(model=model, device=device)
        # language query
        language = self.model.lid_dict[language]
        language = torch.LongTensor([[language]]).to(self.device)
        language = self.model.embed(language).repeat(1, 1, 1)
        # text normalization query
        textnorm = self.model.textnorm_dict["withitn" if textnorm else "woitn"]
        textnorm = torch.LongTensor([[textnorm]]).to(self.device)
        textnorm = self.model.embed(textnorm).repeat(1, 1, 1)
        # event and emotion query
        event_emo = self.model.embed(torch.LongTensor([[1, 2]]).to(self.device)).repeat(
            1, 1, 1
        )
        self.query = torch.cat((language, event_emo, textnorm), dim=1)
        # features
        cmvn = load_cmvn(kwargs["frontend_conf"]["cmvn_file"]).numpy()
        self.neg_mean, self.inv_stddev = cmvn[0, :], cmvn[1, :]
        self.fbank = OnlineFbank(window_type="hamming")
        # decoder
        self.tokenizer = kwargs["tokenizer"]
        bpe_model = kwargs["tokenizer_conf"]["bpemodel"]
        symbol_table = {}
        for i in range(self.tokenizer.get_vocab_size()):
            symbol_table[self.tokenizer.decode(i)] = i
        if beam_size > 1 and contexts is not None:
            self.beam_size = beam_size
            self.decoder = CTCDecoder(contexts, symbol_table, bpe_model)
        else:
            self.beam_size = 1
            self.decoder = CTCDecoder()

        self.chunk_size = chunk_size
        self.padding = padding
        self.cur_idx = -1
        self.caches_shape = (chunk_size + 2 * padding, kwargs["input_size"])
        self.caches = torch.zeros(self.caches_shape)
        self.zeros = np.zeros((1, kwargs["input_size"]), dtype=float)

    @staticmethod
    def load_model(model: str, device: str) -> tuple:
        key = f"{model}-{device}"
        if key not in sensevoice_models:
            model, kwargs = SenseVoiceSmall.from_pretrained(model=model, device=device)
            model = model.to(device)
            model.eval()
            sensevoice_models[key] = (model, kwargs)
        return sensevoice_models[key]

    def reset(self):
        self.cur_idx = -1
        self.decoder.reset()
        self.fbank = OnlineFbank(window_type="hamming")
        self.caches = torch.zeros(self.caches_shape)

    def get_size(self):
        effective_size = self.cur_idx + 1 - self.padding
        if effective_size <= 0:
            return 0
        return effective_size % self.chunk_size or self.chunk_size

    def inference(self, speech):
        speech = speech[None, :, :]
        speech_lengths = torch.tensor([speech.shape[1]])
        speech = speech.to(self.device)
        speech_lengths = speech_lengths.to(self.device)
        speech = torch.cat((self.query, speech), dim=1)
        speech_lengths += 4
        encoder_out, _ = self.model.encoder(speech, speech_lengths)
        return self.model.ctc.log_softmax(encoder_out)[0, 4:]

    def decode(self, times, tokens):
        times_ms = []
        for step, token in zip(times, tokens):
            if len(self.tokenizer.decode(token).strip()) == 0:
                continue
            times_ms.append(step * 60)
        return times_ms, self.tokenizer.decode(tokens)

    def streaming_inference(self, audio, is_last):
        self.fbank.accept_waveform(audio, is_last)
        features = self.fbank.get_lfr_frames(
            neg_mean=self.neg_mean, inv_stddev=self.inv_stddev
        )
        if is_last and len(features) == 0:
            features = self.zeros
        for idx, feature in enumerate(torch.unbind(torch.tensor(features), dim=0)):
            is_last = is_last and idx == features.shape[0] - 1
            self.caches = torch.roll(self.caches, -1, dims=0)
            self.caches[-1, :] = feature
            self.cur_idx += 1
            cur_size = self.get_size()
            if cur_size != self.chunk_size and not is_last:
                continue
            probs = self.inference(self.caches)[self.padding :]
            if cur_size != self.chunk_size:
                probs = probs[self.chunk_size - cur_size :]
            if not is_last:
                probs = probs[: self.chunk_size]
            if self.beam_size > 1:
                res = self.decoder.ctc_prefix_beam_search(
                    probs, beam_size=self.beam_size, is_last=is_last
                )
                times_ms, text = self.decode(res["times"][0], res["tokens"][0])
            else:
                res = self.decoder.ctc_greedy_search(probs, is_last=is_last)
                times_ms, text = self.decode(res["times"], res["tokens"])
            yield {"timestamps": times_ms, "text": text}
