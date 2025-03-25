#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import traceback
from ten import (
    AudioFrame,
    AudioFrameDataFmt,
    VideoFrame,
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten_ai_base.config import BaseConfig
from ten_ai_base.types import TTSPcmOptions
from .heygen import HeyGenRecorder
from dataclasses import dataclass


@dataclass
class HeygenAvatarConfig(BaseConfig):
    api_key: str = ""
    avatar_name: str = "Wayne_20240711"


class HeygenAvatarExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.config = None
        self.input_audio_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue[bytes]()
        self.video_queue = asyncio.Queue()
        self.recorder: HeyGenRecorder = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")

        try:
            self.config = await HeygenAvatarConfig.create_async(ten_env)

            recorder = HeyGenRecorder(
                self.config.api_key,
                self.config.avatar_name,
                ten_env=ten_env,
                audio_queue=self.audio_queue,
                video_queue=self.video_queue,
            )
            self.recorder = recorder

            asyncio.create_task(self._loop_audio_sender(ten_env))
            asyncio.create_task(self._loop_video_sender(ten_env))
            asyncio.create_task(self._loop_input_audio_sender(ten_env))

            # 1) Get the HeyGen token
            token = recorder.get_heygen_token()
            # 2) Create a streaming session => get LiveKit URL/token
            lk_url, lk_token = recorder.create_streaming_session(token)
            # 3) Start session
            recorder.start_streaming_session(token)
            # 4) Connect to WebSocket to feed audio
            recorder.connect_to_websocket()
            # 5) Enter indefinite recording loop
            await recorder.record(lk_url, lk_token)
        except Exception as e:
            ten_env.log_error(f"error on_start, {traceback.format_exc()}")

    async def _loop_video_sender(self, ten_env: AsyncTenEnv):
        while True:
            video_frame = await self.video_queue.get()
            # await ten_env.send_video_frame(video_frame)

    async def _loop_audio_sender(self, ten_env: AsyncTenEnv):
        while True:
            audio_frame = await self.audio_queue.get()
            await self.send_audio_out(ten_env, audio_frame)

    async def _loop_input_audio_sender(self, ten_env: AsyncTenEnv):
        while True:
            audio_frame = await self.input_audio_queue.get()

            if self.recorder is not None:
                await self.recorder.send_audio(audio_frame)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

        # TODO: clean up resources

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        # TODO: process cmd

        cmd_result = CmdResult.create(StatusCode.OK)
        await ten_env.return_result(cmd_result, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        # TODO: process data
        pass

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        audio_frame_name = audio_frame.get_name()
        ten_env.log_debug("on_audio_frame name {}".format(audio_frame_name))

        frame_buf = audio_frame.get_buf()
        self.input_audio_queue.put_nowait(frame_buf)

    async def on_video_frame(
        self, ten_env: AsyncTenEnv, video_frame: VideoFrame
    ) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

        # TODO: process video frame
        pass
