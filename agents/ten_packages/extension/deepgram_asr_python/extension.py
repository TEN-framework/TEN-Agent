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

from deepgram import AsyncListenWebSocketClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions

from .config import DeepgramConfig

PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_LANG = "language"  # Optional
PROPERTY_MODEL = "model"  # Optional
PROPERTY_SAMPLE_RATE = "sample_rate"  # Optional

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"

class DeepgramASRExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.deepgram_client : AsyncListenWebSocketClient = None
        self.deepgram_config : DeepgramConfig = None
        self.ten_env : AsyncTenEnv = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("DeepgramASRExtension on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        self.loop = asyncio.get_event_loop()
        self.ten_env = ten_env

        self.deepgram_config = DeepgramConfig.default_config()

        try:
            self.deepgram_config.api_key = ten_env.get_property_string(PROPERTY_API_KEY).strip()
        except Exception as e:
            ten_env.log_error(f"get property {PROPERTY_API_KEY} error: {e}")
            return

        for optional_param in [
            PROPERTY_LANG,
            PROPERTY_MODEL,
            PROPERTY_SAMPLE_RATE,
        ]:
            try:
                value = ten_env.get_property_string(optional_param).strip()
                if value:
                    self.deepgram_config.__setattr__(optional_param, value)
            except Exception as err:
                ten_env.log_debug(
                    f"get property optional {optional_param} failed, err: {err}. Using default value: {self.deepgram_config.__getattribute__(optional_param)}"
                )
        
        self.deepgram_client = AsyncListenWebSocketClient(config=DeepgramClientOptions(
            api_key=self.deepgram_config.api_key,
            options={"keepalive": "true"}
        ))

        self.loop.create_task(self._start_listen())

        ten_env.log_info("starting async_deepgram_wrapper thread")

    async def on_audio_frame(self, ten_env: AsyncTenEnv, frame: AudioFrame) -> None:
        frame_buf = frame.get_buf()

        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return

        self.stream_id = frame.get_property_int('stream_id')
        await self.deepgram_client.send(frame_buf)
    
    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")

        await self.deepgram_client.finish()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_json = cmd.to_json()
        ten_env.log_info(f"on_cmd json: {cmd_json}")

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        ten_env.return_result(cmd_result, cmd)
    
    async def _start_listen(self) -> None:
        self.ten_env.log_info(f"start and listen deepgram")

        async def on_open(_, open, **kwargs):
            self.ten_env.log_info(f"deepgram event callback on_open: {open}")

        async def on_close(_, close, **kwargs):
            self.ten_env.log_info(f"deepgram event callback on_close: {close}")

        async def on_message(_, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript

            if len(sentence) == 0:
                return

            is_final = result.is_final
            self.ten_env.log_info(f"deepgram got sentence: [{sentence}], is_final: {is_final}, stream_id: {self.stream_id}")

            await self._send_text(text=sentence, is_final=is_final, stream_id=self.stream_id)

        async def on_error(_, error, **kwargs):
            self.ten_env.log_error(f"deepgram event callback on_error: {error}")

        self.deepgram_client.on(LiveTranscriptionEvents.Open, on_open)
        self.deepgram_client.on(LiveTranscriptionEvents.Close, on_close)
        self.deepgram_client.on(LiveTranscriptionEvents.Transcript, on_message)
        self.deepgram_client.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(language=self.deepgram_config.language,
                              model=self.deepgram_config.model,
                              sample_rate=self.deepgram_config.sample_rate,
                              channels=self.deepgram_config.channels,
                              encoding=self.deepgram_config.encoding,
                              interim_results=self.deepgram_config.interim_results,
                              punctuate=self.deepgram_config.punctuate)
        # connect to websocket
        result = await self.deepgram_client.start(options)
        if result is False:
            if self.deepgram_client.status_code == 402:
                self.ten_env.log_error("Failed to connect to Deepgram - your account has run out of credits.")
            else:
                self.ten_env.log_error("Failed to connect to Deepgram")
            return

        self.ten_env.log_info(f"successfully connected to deepgram")
    
    async def _send_text(self, text: str, is_final: bool, stream_id: str) -> None:
        stable_data = Data.create("text_data")
        stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
        stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
        stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final)
        self.ten_env.send_data(stable_data)
