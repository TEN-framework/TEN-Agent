from abc import ABC, abstractmethod
from asyncio import sleep
import asyncio
from ten import (
    AsyncExtension,
    Data,
    TenEnv,
)
from ten.async_ten_env import AsyncTenEnv
from ten.audio_frame import AudioFrame
from ten.cmd import Cmd
from ten.cmd_result import CmdResult, StatusCode
from ten.video_frame import VideoFrame
from .types import LLMToolMetadata, LLMToolResult
from .const import CMD_TOOL_REGISTER, CMD_TOOL_CALL, CMD_PROPERTY_TOOL, CMD_PROPERTY_RESULT
import json


class AsyncLLMToolBaseExtension(AsyncExtension, ABC):
    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)

        tools = self.get_tool_metadata(ten_env)
        for tool in tools:
            ten_env.log_info(f"tool: {tool}")
            c: Cmd = Cmd.create(CMD_TOOL_REGISTER)
            c.set_property_from_json(
                CMD_PROPERTY_TOOL, json.dumps(tool.model_dump_json()))
            await ten_env.send_cmd(c)
            ten_env.log_info(f"tool registered, {tool}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        if cmd_name == CMD_TOOL_CALL:
            try:
                tool_name = cmd.get_property_string("name")
                tool_args = json.loads(cmd.get_property_to_json("arguments"))
                tool_call = json.loads(cmd.get_property_to_json("tool_call"))
                ten_env.log_debug(
                    f"tool_name: {tool_name}, tool_args: {tool_args}")
                result = await asyncio.create_task(self.run_tool(tool_name, tool_args, tool_call))

                if result is None:
                    await sleep(5)
                    ten_env.return_result(CmdResult.create(StatusCode.OK), cmd)
                    return

                cmd_result: CmdResult = CmdResult.create(StatusCode.OK)
                cmd_result.set_property_from_json(
                    CMD_PROPERTY_RESULT, json.dumps(result))
                await sleep(5)
                ten_env.return_result(cmd_result, cmd)
                ten_env.log_info(f"tool result done, {result}")
            except Exception as err:
                ten_env.log_warn(f"on_cmd failed: {err}")
                ten_env.return_result(CmdResult.create(StatusCode.ERROR), cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        # TODO: process data
        pass

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        audio_frame_name = audio_frame.get_name()
        ten_env.log_debug("on_audio_frame name {}".format(audio_frame_name))

        # TODO: process audio frame
        pass

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

        # TODO: process video frame
        pass

    @abstractmethod
    def get_tool_metadata(self, ten_env: TenEnv) -> list[LLMToolMetadata]:
        pass

    @abstractmethod
    async def run_tool(self, ten_env: AsyncTenEnv, name: str, args: dict, tool_call: dict) -> LLMToolResult:
        pass
