from pydantic import BaseModel
from ten import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    Data,
    AudioFrame,
    StatusCode,
    CmdResult,
)

import asyncio
from dataclasses import dataclass

from ten_ai_base.config import BaseConfig

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"
from .streaming_sensevoice import StreamingSenseVoice
from silero_vad import VADIterator
import numpy as np

@dataclass
class SenseVoiceASRConfig(BaseConfig):
    api_key: str = ""
    language: str = "en-US"
    model: str = "nova-2"
    sample_rate: int = 16000

    channels: int = 1
    encoding: str = "linear16"
    interim_results: bool = True
    punctuate: bool = True


class TranscriptionChunk(BaseModel):
    timestamps: list[int]
    raw_text: str
    final_text: str | None = None
    spk_id: int | None = None


class TranscriptionResponse(BaseModel):
    type: str = "TranscriptionResponse"
    id: int
    begin_at: float
    end_at: float | None
    data: TranscriptionChunk
    is_final: bool
    session_id: str | None = None


class VADEvent(BaseModel):
    type: str = "VADEvent"
    is_active: bool

class SenseVoiceASRExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.connected = False
        self.config: SenseVoiceASRConfig = None
        self.ten_env: AsyncTenEnv = None
        self.loop = None
        self.stream_id = -1
        self.cache = {}
        self.model = None
        self.buf = b""
        self.chunks = asyncio.Queue()
        self.model_prepared = False

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("DeepgramASRExtension on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        self.loop = asyncio.get_event_loop()
        self.ten_env = ten_env

        self.config = await SenseVoiceASRConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        # if not self.config.api_key:
        #     ten_env.log_error("get property api_key")
        #     return

        # ten_env.log_info("starting async_deepgram_wrapper thread")
        self.loop.create_task(self._processing_audio())
        self._prepare_model()

    async def on_audio_frame(self, _: AsyncTenEnv, frame: AudioFrame) -> None:
        frame_buf = frame.get_buf()

        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return

        self.buf += frame_buf

    def _prepare_model(self) -> None:
        if self.model_prepared:
            return

        # Load the model
        # self.model = AutoModel(model="SenseVoiceSmall", device="cpu")
        
        # load model on startup
        self.ten_env.log_info("Loading model...")
        StreamingSenseVoice.load_model(model="iic/SenseVoiceSmall", device="cpu")
        self.ten_env.log_info("Model loaded successfully")
        self.model_prepared = True

    async def _processing_audio(self) -> None:
        chunk_duration = 0.04 # 40ms
        vad_threshold = 0.5
        vad_min_silence_duration_ms = 550

        sensevoice_model = StreamingSenseVoice(
            model="iic/SenseVoiceSmall", device="cpu"
        )
        vad_iterator = VADIterator(
            version="v5",
            threshold=vad_threshold,
            min_silence_duration_ms=vad_min_silence_duration_ms,
        )

        chunk_size = int(chunk_duration * 16000)  # 40ms

        speech_count = 0
        currentAudioBeginTime = 0.0

        asrDetected = False

        transcription_response: TranscriptionResponse = None
        while True:
            audio_buffer = self.buf
            while len(audio_buffer) >= chunk_size:
                chunk = audio_buffer[:chunk_size]
                audio_buffer = audio_buffer[chunk_size:]

                for speech_dict, speech_samples in vad_iterator(chunk):
                    if "start" in speech_dict:
                        sensevoice_model.reset()

                        currentAudioBeginTime: float = (
                            speech_dict["start"] / 16000
                        )

                        if asrDetected:
                            self.ten_env.log_debug(
                                f"{speech_count}: VAD *NOT* end: \n{transcription_response.data.raw_text}\n{str(transcription_response.data.timestamps)}"
                            )
                            speech_count += 1
                        asrDetected = False

                        self.ten_env.log_debug(
                            f"{speech_count}: VAD start: {currentAudioBeginTime}"
                        )
                        # await websocket.send_json(VADEvent(is_active=True).model_dump())
                        self.ten_env.log_info(
                            f"VAD start: {VADEvent(is_active=True).model_dump()}"
                        )

                    is_last = "end" in speech_dict

                    for res in sensevoice_model.streaming_inference(
                        speech_samples, is_last
                    ):

                        if len(res["text"]) > 0:
                            asrDetected = True

                        if asrDetected:
                            transcription_response = TranscriptionResponse(
                                id=speech_count,
                                begin_at=currentAudioBeginTime,
                                end_at=None,
                                data=TranscriptionChunk(
                                    timestamps=res["timestamps"], raw_text=res["text"]
                                ),
                                is_final=False,
                            )
                            self.ten_env.log_info(
                                transcription_response.model_dump()
                            )

                    if is_last:
                        if asrDetected:
                            speech_count += 1
                            asrDetected = False

                            transcription_response.is_final = True
                            transcription_response.end_at = (
                                speech_dict["end"] / 16000
                            )

                            self.ten_env.log_info(
                                transcription_response.model_dump()
                            )
                            self.ten_env.log_info(
                                f"{speech_count}: VAD end: {speech_dict['end'] / 16000}\n{transcription_response.data.raw_text}\n{str(transcription_response.data.timestamps)}"
                            )
                        else:
                            self.ten_env.log_info(
                                f"{speech_count}: VAD end: {speech_dict['end'] / 16000}\nNo Speech"
                            )
                        self.ten_env.log_info(
                            f"VAD start: {VADEvent(is_active=False).model_dump()}"
                        )
        
        


    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")

        self.stopped = True

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_json = cmd.to_json()
        ten_env.log_info(f"on_cmd json: {cmd_json}")

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        await ten_env.return_result(cmd_result, cmd)

    async def _send_text(self, text: str, is_final: bool, stream_id: str) -> None:
        stable_data = Data.create("text_data")
        stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
        stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
        stable_data.set_property_bool(
            DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final
        )
        asyncio.create_task(self.ten_env.send_data(stable_data))
