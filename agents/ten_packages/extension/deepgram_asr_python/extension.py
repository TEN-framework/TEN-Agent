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

from deepgram import (
    AsyncListenWebSocketClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)
from dataclasses import dataclass

from ten_ai_base.config import BaseConfig

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"


@dataclass
class DeepgramASRConfig(BaseConfig):
    api_key: str = ""
    language: str = "en-US"
    model: str = "nova-2"
    sample_rate: int = 16000

    channels: int = 1
    encoding: str = "linear16"
    interim_results: bool = True
    punctuate: bool = True


class DeepgramASRExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.connected = False
        self.client: AsyncListenWebSocketClient = None
        self.config: DeepgramASRConfig = None
        self.ten_env: AsyncTenEnv = None
        self.loop = None
        self.stream_id = -1

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("DeepgramASRExtension on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        self.loop = asyncio.get_event_loop()
        self.ten_env = ten_env

        self.config = DeepgramASRConfig.create(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.api_key:
            ten_env.log_error("get property api_key")
            return

        self.loop.create_task(self._start_listen())

        ten_env.log_info("starting async_deepgram_wrapper thread")

    async def on_audio_frame(self, _: AsyncTenEnv, frame: AudioFrame) -> None:
        frame_buf = frame.get_buf()

        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return

        if not self.connected:
            self.ten_env.log_debug("send_frame: deepgram not connected.")
            return

        self.stream_id = frame.get_property_int("stream_id")
        if self.client:
            await self.client.send(frame_buf)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")

        self.stopped = True

        if self.client:
            await self.client.finish()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_json = cmd.to_json()
        ten_env.log_info(f"on_cmd json: {cmd_json}")

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        await ten_env.return_result(cmd_result, cmd)

    async def _start_listen(self) -> None:
        self.ten_env.log_info("start and listen deepgram")

        self.client = AsyncListenWebSocketClient(
            config=DeepgramClientOptions(
                api_key=self.config.api_key, options={"keepalive": "true"}
            )
        )

        async def on_open(_, event):
            self.ten_env.log_info(f"deepgram event callback on_open: {event}")
            self.connected = True

        async def on_close(_, event):
            self.ten_env.log_info(f"deepgram event callback on_close: {event}")
            self.connected = False
            if not self.stopped:
                self.ten_env.log_warn(
                    "Deepgram connection closed unexpectedly. Reconnecting..."
                )
                await asyncio.sleep(0.2)
                self.loop.create_task(self._start_listen())

        async def on_message(_, result):
            sentence = result.channel.alternatives[0].transcript

            if len(sentence) == 0:
                return

            is_final = result.is_final
            self.ten_env.log_info(
                f"deepgram got sentence: [{sentence}], is_final: {is_final}, stream_id: {self.stream_id}"
            )

            await self._send_text(
                text=sentence, is_final=is_final, stream_id=self.stream_id
            )

        async def on_error(_, error):
            self.ten_env.log_error(f"deepgram event callback on_error: {error}")

        self.client.on(LiveTranscriptionEvents.Open, on_open)
        self.client.on(LiveTranscriptionEvents.Close, on_close)
        self.client.on(LiveTranscriptionEvents.Transcript, on_message)
        self.client.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            language=self.config.language,
            model=self.config.model,
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            encoding=self.config.encoding,
            interim_results=self.config.interim_results,
            punctuate=self.config.punctuate,
        )
        # connect to websocket
        result = await self.client.start(options)
        if not result:
            self.ten_env.log_error("failed to connect to deepgram")
            await asyncio.sleep(0.2)
            self.loop.create_task(self._start_listen())
        else:
            self.ten_env.log_info("successfully connected to deepgram")

    async def _send_text(self, text: str, is_final: bool, stream_id: str) -> None:
        stable_data = Data.create("text_data")
        stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
        stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
        stable_data.set_property_bool(
            DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final
        )
        asyncio.create_task(self.ten_env.send_data(stable_data))
