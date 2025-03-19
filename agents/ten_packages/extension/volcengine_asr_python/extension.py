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

import asyncio
import datetime
import gzip
import json
import time
import uuid
import wave
from io import BytesIO
import websockets

from dataclasses import dataclass

from ten_ai_base.config import BaseConfig

from .volcengine_asr_client import VolcengineAsrClient

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"


@dataclass
class VolcengineASRConfig(BaseConfig):
    app_id: str = ""
    access_token: str = ""
    resource_id: str = ""
    sample_rate: int = 16000

    channels: int = 1
    format:str = "pcm"
    codec: str = "raw"
    punctuate: bool = True


class VolcengineASRExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.connected = False
        self.client: VolcengineAsrClient = None
        self.config: VolcengineASRConfig = None
        self.ten_env: AsyncTenEnv = None
        self.loop = None
        self.stream_id = -1
        self.frame_buff = bytearray()
        self.lock = asyncio.Lock()

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("VolcengineASRExtension on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        self.loop = asyncio.get_event_loop()
        self.ten_env = ten_env

        self.config = await VolcengineASRConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.app_id:
            ten_env.log_error("get property api_key")
            return
        if not self.config.access_token:
            ten_env.log_error("get property access_token")
            return
        if not self.config.resource_id:
            ten_env.log_error("get property resource_id")
            return

        self.loop.create_task(self._start_listen())

        ten_env.log_info("starting async_volcengine_wrapper thread")

    async def on_audio_frame(self, _: AsyncTenEnv, frame: AudioFrame) -> None:
         async with self.lock:
            frame_buf = frame.get_buf()
            if not frame_buf:
                self.ten_env.log_warn("send_frame: empty pcm_frame detected.")
                return
            self.frame_buff.extend(frame_buf)
            if not self.connected:
                self.ten_env.log_error("send_frame: volcengine asr not connected.")
                return

            self.stream_id = frame.get_property_int("stream_id")
            # volcengine asr 要求单包音频必须在100ms大小左右，不能过大或者过小，这里选取120ms
            seg_duration = self.config.sample_rate * 2 * self.config.channels * 120 / 1000
            if self.client:
                if len(self.frame_buff) >= seg_duration:
                    # self.ten_env.log_info(f"send frame_buf:{len(self.frame_buff)}")
                    await self.client.send(bytes(self.frame_buff[:]))
                    self.frame_buff.clear()
                    # self.ten_env.log_info(f"send frame_buf over:{len(self.frame_buff)}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")

        self.stopped = True

        if self.client:
            await self.client.close()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_json = cmd.to_json()
        ten_env.log_info(f"on_cmd json: {cmd_json}")

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        await ten_env.return_result(cmd_result, cmd)

    async def _start_listen(self) -> None:
        self.ten_env.log_info("start and listen volcengine")

        self.client = VolcengineAsrClient(**{
            "app_id":self.config.app_id,
            "access_token":self.config.access_token,
            "resource_id":self.config.resource_id,
            })

        async def on_open():
            self.ten_env.log_info(f"volcengine event callback on_open")
            self.connected = True

        async def on_close():
            self.ten_env.log_info(f"volcengine event callback on_close")
            self.connected = False
            if not self.stopped:
                self.ten_env.log_warn(
                    "volcengine connection closed unexpectedly. Reconnecting..."
                )
                await asyncio.sleep(0.2)
                self.loop.create_task(self._start_listen())

        async def on_message(result):
            sentence = result.get("text")
            is_final = result.get("is_final")
            if len(sentence) == 0:
                return

            is_final = result.get("is_final")
            self.ten_env.log_info(
                f"volcengine got sentence: [{sentence}], is_final: {is_final}, stream_id: {self.stream_id}"
            )

            await self._send_text(
                text=sentence, is_final=is_final, stream_id=self.stream_id
            )

        async def on_error(error):
            import traceback
            self.ten_env.log_error(traceback.format_exc())
            self.ten_env.log_error(f"volcengine event callback on_error: {error}")

        # connect to websocket
        self.client.on(on_open = on_open,on_close=on_close,on_error=on_error,on_transcript=on_message)
        result = await self.client.start()
        if not result:
            self.ten_env.log_error("failed to connect to volcengine")
            await asyncio.sleep(0.2)
            self.loop.create_task(self._start_listen())
        else:
            self.ten_env.log_info("successfully connected to volcengine")
            await self.client.send_full_client_request()

    async def _send_text(self, text: str, is_final: bool, stream_id: str) -> None:
        stable_data = Data.create("text_data")
        stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
        stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
        stable_data.set_property_bool(
            DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final
        )
        asyncio.create_task(self.ten_env.send_data(stable_data))
