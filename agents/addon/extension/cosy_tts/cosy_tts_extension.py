#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import traceback
from rte_runtime_python import (
    Extension,
    Rte,
    Cmd,
    PcmFrame,
    RTE_PCM_FRAME_DATA_FMT,
    Data,
    StatusCode,
    CmdResult,
    MetadataInfo,
)
from typing import List, Any
import dashscope
import queue
import threading
from datetime import datetime
from dashscope.audio.tts_v2 import ResultCallback, SpeechSynthesizer, AudioFormat
from .log import logger


class CosyTTSCallback(ResultCallback):
    _player = None
    _stream = None

    def __init__(self, rte: Rte, sample_rate: int):
        super().__init__()
        self.rte = rte
        self.sample_rate = sample_rate
        self.frame_size = int(self.sample_rate * 1 * 2 / 100)
        self.canceled = False
        self.closed = False

    def on_open(self):
        logger.info("websocket is open.")

    def on_complete(self):
        logger.info("speech synthesis task complete successfully.")

    def on_error(self, message: str):
        logger.info(f"speech synthesis task failed, {message}")

    def on_close(self):
        logger.info("websocket is closed.")
        self.closed = True

    def on_event(self, message):
        pass
        # logger.info(f"recv speech synthsis message {message}")

    def get_frame(self, data: bytes) -> PcmFrame:
        f = PcmFrame.create("pcm_frame")
        f.set_sample_rate(self.sample_rate)
        f.set_bytes_per_sample(2)
        f.set_number_of_channels(1)
        # f.set_timestamp = 0
        f.set_data_fmt(RTE_PCM_FRAME_DATA_FMT.RTE_PCM_FRAME_DATA_FMT_INTERLEAVE)
        f.set_samples_per_channel(self.sample_rate // 100)
        f.alloc_buf(self.frame_size)
        buff = f.lock_buf()
        if len(data) < self.frame_size:
            buff[:] = bytes(self.frame_size)  # fill with 0
        buff[: len(data)] = data
        f.unlock_buf(buff)
        return f

    def cancel(self) -> None:
        self.canceled = True

    def on_data(self, data: bytes) -> None:
        if self.canceled:
            return

        # logger.info("audio result length: %d, %d", len(data), self.frame_size)
        try:
            chunk = int(len(data) / self.frame_size)
            offset = 0
            for i in range(0, chunk):
                if self.canceled:
                    return
                f = self.get_frame(data[offset : offset + self.frame_size])
                self.rte.send_pcm_frame(f)
                offset += self.frame_size

            if self.canceled:
                return
            if offset < len(data):
                size = len(data) - offset
                f = self.get_frame(data[offset : offset + size])
                self.rte.send_pcm_frame(f)
        except Exception as e:
            logger.exception(e)


class CosyTTSExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.api_key = ""
        self.voice = ""
        self.model = ""
        self.sample_rate = 16000
        self.tts = None
        self.callback = None
        self.format = None
        self.outdateTs = datetime.now()

        self.stopped = False
        self.thread = None
        self.queue = queue.Queue()
        self.mutex = threading.Lock()

    def on_init(self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo) -> None:
        logger.info("CosyTTSExtension on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        logger.info("CosyTTSExtension on_start")
        self.api_key = rte.get_property_string("api_key")
        self.voice = rte.get_property_string("voice")
        self.model = rte.get_property_string("model")
        self.sample_rate = rte.get_property_int("sample_rate")

        dashscope.api_key = self.api_key
        f = AudioFormat.PCM_16000HZ_MONO_16BIT
        if self.sample_rate == 8000:
            f = AudioFormat.PCM_8000HZ_MONO_16BIT
        elif self.sample_rate == 16000:
            f = AudioFormat.PCM_16000HZ_MONO_16BIT
        elif self.sample_rate == 22050:
            f = AudioFormat.PCM_22050HZ_MONO_16BIT
        elif self.sample_rate == 24000:
            f = AudioFormat.PCM_24000HZ_MONO_16BIT
        elif self.sample_rate == 44100:
            f = AudioFormat.PCM_44100HZ_MONO_16BIT
        elif self.sample_rate == 48000:
            f = AudioFormat.PCM_48000HZ_MONO_16BIT
        else:
            logger.info("unknown sample rate %d", self.sample_rate)
            exit()

        self.format = f

        self.thread = threading.Thread(target=self.async_handle, args=[rte])
        self.thread.start()
        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        logger.info("CosyTTSExtension on_stop")

        self.stopped = True
        self.queue.put(None)
        self.flush()
        self.thread.join()
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        logger.info("CosyTTSExtension on_deinit")
        rte.on_deinit_done()

    def need_interrupt(self, ts: datetime.time) -> bool:
        return self.outdateTs > ts and (self.outdateTs - ts).total_seconds() > 1

    def async_handle(self, rte: Rte):
        try:
            tts = None
            callback = None
            while not self.stopped:
                try:
                    value = self.queue.get()
                    if value is None:
                        break
                    inputText, ts = value
                    if len(inputText) == 0:
                        logger.warning("empty input for interrupt")
                        if tts is not None:
                            try:
                                tts.streaming_cancel()
                            except Exception as e:
                                logger.exception(e)
                        if callback is not None:
                            callback.cancel()
                        tts = None
                        callback = None
                        continue

                    if self.need_interrupt(ts):
                        continue

                    if callback is not None and callback.closed is True:
                        tts = None

                    if tts is None:
                        logger.info("creating tts")
                        callback = CosyTTSCallback(rte, self.sample_rate)
                        tts = SpeechSynthesizer(
                            model=self.model,
                            voice=self.voice,
                            format=self.format,
                            callback=callback,
                        )

                    logger.info("on message %s", inputText)
                    tts.streaming_call(inputText)
                except Exception as e:
                    logger.exception(e)
                    logger.exception(traceback.format_exc())
        finally:
            if tts is not None:
                tts.streaming_complete()

    def flush(self):
        logger.info("CosyTTSExtension flush")
        while not self.queue.empty():
            self.queue.get()
        self.queue.put(("", datetime.now()))

    def on_data(self, rte: Rte, data: Data) -> None:
        logger.info("CosyTTSExtension on_data")
        inputText = data.get_property_string("text")
        if len(inputText) == 0:
            logger.info("ignore empty text")
            return

        is_end = data.get_property_bool("end_of_segment")

        logger.info("on data %s %d", inputText, is_end)
        self.queue.put((inputText, datetime.now()))

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        logger.info("CosyTTSExtension on_cmd")
        cmd_json = cmd.to_json()
        logger.info("CosyTTSExtension on_cmd json: %s" + cmd_json)

        cmdName = cmd.get_name()
        if cmdName == "flush":
            self.outdateTs = datetime.now()
            self.flush()
            cmd_out = Cmd.create("flush")
            rte.send_cmd(
                cmd_out, lambda rte, result: print("DefaultExtension send_cmd done")
            )
        else:
            logger.info("unknown cmd %s", cmdName)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)
