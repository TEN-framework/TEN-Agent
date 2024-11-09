#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from asyncio import sleep
import asyncio
import json
from ten import (
    AudioFrame,
    VideoFrame,
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)


class Buf2MessageExtension(AsyncExtension):
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")
        ten_env.on_init_done()

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")

        # TODO: read properties, initialize resources

        ten_env.on_start_done()

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

        # TODO: clean up resources

        ten_env.on_stop_done()

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")
        ten_env.on_deinit_done()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        # TODO: process cmd

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        buf = data.get_property_buf("data")
        buf_text = buf.decode("utf-8")

        content = json.loads(buf_text)
        message = content.get("text", "")
        remoteStreamId = content.get("stream_id", "")

        ten_env.log_info("on_data message {}".format(message))

        cmd = Cmd.create("flush")
        await ten_env.send_cmd(cmd)

        ten_env.log_info("Send message to remote stream {}".format(remoteStreamId))

        ten_data: Data = Data.create("text_data")
        ten_data.set_property_string("text", message)
        ten_data.set_property_int("stream_id", remoteStreamId)
        ten_data.set_property_bool("is_final", True)
        ten_data.set_property_bool("end_of_segment", True)
        ten_env.send_data(ten_data)

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
