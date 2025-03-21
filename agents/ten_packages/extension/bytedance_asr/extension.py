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

from .bytedance_asr import AsrWsClient

from dataclasses import dataclass

from ten_ai_base.config import BaseConfig

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"


@dataclass
class BytedanceASRConfig(BaseConfig):
    # Refer to: https://www.volcengine.com/docs/6561/80818.
    # 根据 https://www.volcengine.com/docs/6561/111522, agora_rtc subscribe_audio_samples_per_frame 需要设置为3200
    appid: str = ""
    token: str = ""
    api_url: str = "wss://openspeech.bytedance.com/api/v2/asr"
    cluster: str = "volcengine_streaming_common"


class BytedanceASRExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.connected = False
        self.client = None
        self.config: BytedanceASRConfig = None
        self.ten_env: AsyncTenEnv = None
        self.loop = None
        self.stream_id = -1

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("BytedanceASRExtension on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        self.loop = asyncio.get_event_loop()
        self.ten_env = ten_env

        self.config = await BytedanceASRConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.appid:
            raise ValueError("appid is required")

        if not self.config.token:
            raise ValueError("token is required")

        self.loop.create_task(self._start_listen())

        ten_env.log_info("starting bytedance_asr thread")

    async def on_audio_frame(self, _: AsyncTenEnv, frame: AudioFrame) -> None:
        frame_buf = frame.get_buf()

        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return

        if not self.connected:
            self.ten_env.log_debug("send_frame: bytedance_asr not connected.")
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
        self.ten_env.log_info("start and listen bytedance_asr")

        async def on_message(result):
            if not result or 'text' not in result[0] or 'utterances' not in result[0]:
                self.ten_env.log_warn("Received malformed result.")
                return

            sentence = result[0]['text']

            if len(sentence) == 0:
                return

            is_final = result[0]['utterances'][0].get('definite', False)  # Use get to avoid KeyError
            self.ten_env.log_info(
                f"bytedance_asr got sentence: [{sentence}], is_final: {is_final}, stream_id: {self.stream_id}"
            )

            await self._send_text(
                text=sentence, is_final=is_final, stream_id=self.stream_id
            )

        self.client = AsrWsClient(
            ten_env=self.ten_env,
            cluster=self.config.cluster,
            appid=self.config.appid,
            token=self.config.token,
            api_url=self.config.api_url,
            handle_received_message=on_message,
        )

        # connect to websocket
        await self.client.start()
        self.connected = True

    async def _send_text(self, text: str, is_final: bool, stream_id: str) -> None:
        stable_data = Data.create("text_data")
        stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
        stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
        stable_data.set_property_bool(
            DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final
        )
        asyncio.create_task(self.ten_env.send_data(stable_data))
