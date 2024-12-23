from abc import ABC, abstractmethod
import asyncio
import traceback
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
from .const import (
    CMD_TOOL_REGISTER,
    CMD_TOOL_CALL,
    CMD_PROPERTY_TOOL,
    CMD_PROPERTY_RESULT,
)
import json


class AsyncLLMToolBaseExtension(AsyncExtension, ABC):
    async def on_start(self, async_ten_env: AsyncTenEnv) -> None:
        await super().on_start(async_ten_env)

        tools: list[LLMToolMetadata] = self.get_tool_metadata(async_ten_env)
        for tool in tools:
            async_ten_env.log_info(f"tool: {tool}")
            c: Cmd = Cmd.create(CMD_TOOL_REGISTER)
            c.set_property_from_json(
                CMD_PROPERTY_TOOL, json.dumps(tool.model_dump_json())
            )
            async_ten_env.log_info(f"begin tool register, {tool}")
            await async_ten_env.send_cmd(c)
            async_ten_env.log_info(f"tool registered, {tool}")

    async def on_stop(self, async_ten_env: AsyncTenEnv) -> None:
        await super().on_stop(async_ten_env)

    async def on_cmd(self, async_ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        async_ten_env.log_debug("on_cmd name {}".format(cmd_name))

        if cmd_name == CMD_TOOL_CALL:
            try:
                tool_name = cmd.get_property_string("name")
                tool_args = json.loads(cmd.get_property_to_json("arguments"))
                async_ten_env.log_debug(
                    f"tool_name: {tool_name}, tool_args: {tool_args}"
                )
                result = await asyncio.create_task(
                    self.run_tool(async_ten_env, tool_name, tool_args)
                )

                if result is None:
                    await async_ten_env.return_result(
                        CmdResult.create(StatusCode.OK), cmd
                    )
                    return

                cmd_result: CmdResult = CmdResult.create(StatusCode.OK)
                cmd_result.set_property_from_json(
                    CMD_PROPERTY_RESULT, json.dumps(result)
                )
                await async_ten_env.return_result(cmd_result, cmd)
                async_ten_env.log_info(f"tool result done, {result}")
            except Exception:
                async_ten_env.log_warn(f"on_cmd failed: {traceback.format_exc()}")
                await async_ten_env.return_result(
                    CmdResult.create(StatusCode.ERROR), cmd
                )

    async def on_data(self, async_ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        async_ten_env.log_debug(f"on_data name {data_name}")

    async def on_audio_frame(
        self, async_ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        audio_frame_name = audio_frame.get_name()
        async_ten_env.log_debug("on_audio_frame name {}".format(audio_frame_name))

    async def on_video_frame(
        self, async_ten_env: AsyncTenEnv, video_frame: VideoFrame
    ) -> None:
        video_frame_name = video_frame.get_name()
        async_ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

    @abstractmethod
    def get_tool_metadata(self, ten_env: TenEnv) -> list[LLMToolMetadata]:
        pass

    @abstractmethod
    async def run_tool(
        self, ten_env: AsyncTenEnv, name: str, args: dict
    ) -> LLMToolResult | None:
        pass
