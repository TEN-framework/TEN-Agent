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

import json

import nls

from dataclasses import dataclass

from ten_ai_base.config import BaseConfig

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"


@dataclass
class AliyunASRConfig(BaseConfig):
    # Refer to: https://help.aliyun.com/zh/isi/developer-reference/sdk-for-python-2.
    appkey: str = ""
    akid: str = ""
    aksecret: str = ""
    api_url: str = "wss://nls-gateway.aliyuncs.com/ws/v1"


class AliyunASRExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.connected = False
        self.client = None
        self.config: AliyunASRConfig = None
        self.ten_env: AsyncTenEnv = None
        self.loop = None
        self.stream_id = -1

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("AliyunASRExtension on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        self.loop = asyncio.get_event_loop()
        self.ten_env = ten_env

        self.config = await AliyunASRConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.appkey:
            raise ValueError("appkey is required")

        if not self.config.akid:
            raise ValueError("akid is required")

        if not self.config.aksecret:
            raise ValueError("aksecret is required")

        self.loop.create_task(self._start_listen())

        ten_env.log_info("starting aliyun_asr thread")

    async def on_audio_frame(self, _: AsyncTenEnv, frame: AudioFrame) -> None:
        frame_buf = frame.get_buf()

        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
            return

        if not self.connected:
            self.ten_env.log_debug("send_frame: aliyun_asr not connected.")
            return

        self.stream_id = frame.get_property_int("stream_id")
        if self.client:
            self.client.send_audio(frame_buf)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")

        self.stopped = True

        if self.client:
            self.client.stop()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_json = cmd.to_json()
        ten_env.log_info(f"on_cmd json: {cmd_json}")

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        await ten_env.return_result(cmd_result, cmd)

    async def _start_listen(self) -> None:
        self.ten_env.log_info("start and listen aliyun_asr")

        def on_start(message, *args):
            self.ten_env.log_info(f"aliyun_asr event callback on_start: {message}")
            self.connected = True

        def on_close(*args):
            self.ten_env.log_info(f"aliyun_asr event callback on_close: {args}")
            self.connected = False
            if not self.stopped:
                self.ten_env.log_warn(
                    "aliyun_asr connection closed unexpectedly. Reconnecting..."
                )

        def on_message(result, *args):
            if not result:
                self.ten_env.log_warn("Received empty result.")
                return

            try:
                # Parse the JSON string once
                result_data = json.loads(result)  # Assuming result is a JSON string

                if 'payload' not in result_data:
                    self.ten_env.log_warn("Received malformed result.")
                    return

                sentence = result_data.get('payload', {}).get('result', '')

                if len(sentence) == 0:
                    return

                is_final = result_data.get('header', {}).get('name') == 'SentenceEnd'
                self.ten_env.log_info(
                    f"aliyun_asr got sentence: [{sentence}], is_final: {is_final}, stream_id: {self.stream_id}"
                )

                self.loop.create_task(self._send_text(
                    text=sentence, is_final=is_final, stream_id=self.stream_id
                ))
            except Exception as e:
                self.ten_env.log_error(f"Error processing message: {e}")

        def on_error(message, *args):
            self.ten_env.log_error(f"aliyun_asr event callback on_error: {message}")

        token = nls.token.getToken(self.config.akid, self.config.aksecret)
        self.client = nls.NlsSpeechTranscriber(
            url=self.config.api_url,
            appkey=self.config.appkey,
            token=token,
            on_start=on_start,
            on_sentence_begin=on_message,
            on_sentence_end=on_message,
            on_result_changed=on_message,
            on_completed=on_message,
            on_error=on_error,
            on_close=on_close,
            callback_args=[]
        )

        # connect to websocket
        self.client.start(
            aformat="pcm",
            enable_intermediate_result=True,
            enable_punctuation_prediction=True,
            enable_inverse_text_normalization=True
        )

    async def _send_text(self, text: str, is_final: bool, stream_id: str) -> None:
        stable_data = Data.create("text_data")
        stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
        stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
        stable_data.set_property_bool(
            DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final
        )
        asyncio.create_task(self.ten_env.send_data(stable_data))
