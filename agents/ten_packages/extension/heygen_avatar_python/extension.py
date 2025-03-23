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
        self.audio_queue = asyncio.Queue[bytes]()
        self.video_queue = asyncio.Queue()
        self.leftover_bytes = b''

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")

        self.config = await HeygenAvatarConfig.create_async(ten_env)

        recorder = HeyGenRecorder(
            self.config.api_key,
            self.config.avatar_name,
            ten_env=ten_env,
            audio_queue=self.audio_queue,
            video_queue=self.video_queue
        )

        asyncio.create_task(self._loop_audio_sender(ten_env))
        asyncio.create_task(self._loop_video_sender(ten_env))

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

    async def _loop_video_sender(self, ten_env: AsyncTenEnv):
        while True:
            video_frame = await self.video_queue.get()
            # await ten_env.send_video_frame(video_frame)

    async def _loop_audio_sender(self, ten_env: AsyncTenEnv):
        while True:
            audio_frame = await self.audio_queue.get()
            await self.send_audio_out(ten_env, audio_frame)


    async def send_audio_out(self, ten_env: AsyncTenEnv, audio_data: bytes, **args: TTSPcmOptions) -> None:
        """End sending audio out."""
        sample_rate = args.get("sample_rate", 16000)
        bytes_per_sample = args.get("bytes_per_sample", 2)
        number_of_channels = args.get("number_of_channels", 1)
        try:
            # Combine leftover bytes with new audio data
            combined_data = self.leftover_bytes + audio_data

            # Check if combined_data length is odd
            if len(combined_data) % (bytes_per_sample * number_of_channels) != 0:
                # Save the last incomplete frame
                valid_length = len(combined_data) - (len(combined_data) %
                                                     (bytes_per_sample * number_of_channels))
                self.leftover_bytes = combined_data[valid_length:]
                combined_data = combined_data[:valid_length]
            else:
                self.leftover_bytes = b''

            if combined_data:
                f = AudioFrame.create("pcm_frame")
                f.set_sample_rate(sample_rate)
                f.set_bytes_per_sample(bytes_per_sample)
                f.set_number_of_channels(number_of_channels)
                f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
                f.set_samples_per_channel(
                    len(combined_data) // (bytes_per_sample * number_of_channels))
                f.alloc_buf(len(combined_data))
                buff = f.lock_buf()
                buff[:] = combined_data
                f.unlock_buf(buff)
                await ten_env.send_audio_frame(f)
        except Exception as e:
            ten_env.log_error(
                f"error send audio frame, {traceback.format_exc()}")           

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

        # TODO: process audio frame
        pass

    async def on_video_frame(
        self, ten_env: AsyncTenEnv, video_frame: VideoFrame
    ) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

        # TODO: process video frame
        pass
