#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from abc import ABC, abstractmethod
import asyncio
from enum import Enum
from typing import Optional, TypedDict
from ten import (
    AsyncExtension,
    TenEnv,
    Data,
)
from ten.async_ten_env import AsyncTenEnv
from ten.audio_frame import AudioFrame
from ten.cmd import Cmd
from ten.cmd_result import CmdResult, StatusCode
from ten.video_frame import VideoFrame
from .helper import AsyncQueue
import json
from pydantic import BaseModel

CMD_TOOL_REGISTER = "tool_register"
CMD_TOOL_CALL = "tool_call"
CMD_PROPERTY_TOOL = "tool"
CMD_PROPERTY_RESULT = "tool_result"

class TenLLMToolMetadataParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool

class TenLLMToolMetadata(BaseModel):
    name: str
    description: str
    parameters: list[TenLLMToolMetadataParameter]

class TenLLMToolResultItem(BaseModel):
    type: str
    data: str

class TenLLMToolResult(BaseModel):
    items: list[TenLLMToolResultItem]

class TenLLMToolBaseExtension(AsyncExtension, ABC):
    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        tools = self.get_tool_metadata()
        for tool in tools:
            ten_env.log_debug(f"tool: {tool}")
            c:Cmd = Cmd.create(CMD_TOOL_REGISTER)
            c.set_property_from_json(CMD_PROPERTY_TOOL, json.dumps(tool.model_dump_json()))
            await ten_env.send_cmd(c)
            ten_env.log_debug(f"tool registered, {tool}")


    async def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        if cmd_name == CMD_TOOL_CALL:
            tool_name = cmd.get_property_string("name")
            tool_args = json.loads(cmd.get_property_to_json("arguments"))
            ten_env.log_debug(f"tool_name: {tool_name}, tool_args: {tool_args}")
            result = await self.run_tool(tool_name, tool_args)
            cmd_result:CmdResult = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_from_json(CMD_PROPERTY_RESULT, json.dumps(result.model_dump_json()))
            ten_env.return_result(cmd_result, cmd)
            ten_env.log_debug(f"tool result done, {result}")

    async def on_data(self, ten_env: TenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        # TODO: process data
        pass

    async def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        audio_frame_name = audio_frame.get_name()
        ten_env.log_debug("on_audio_frame name {}".format(audio_frame_name))

        # TODO: process audio frame
        pass

    async def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

        # TODO: process video frame
        pass

    @abstractmethod
    def get_tool_metadata(self) -> list[TenLLMToolMetadata]:
        pass

    @abstractmethod
    def run_tool(self, name: str, args: dict) -> TenLLMToolResult:
        pass
    

class TenLLMDataType(Enum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"

class TenLLMTextCompletionArgs(TypedDict, total=False):
    no_tool: bool = False

class TenLLMAudioCompletionArgs(TypedDict, total=False):
    no_tool: bool = False

class TenLLMBaseExtension(AsyncExtension, ABC):
    # Create the queue for message processing
    queue = AsyncQueue()
    available_tools: list[TenLLMToolMetadata] = []
    available_tools_lock = asyncio.Lock()  # Lock to ensure thread-safe access
    current_task = None

    async def on_init(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_start")

        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._process_queue(ten_env))

    async def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, async_ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        async_ten_env.log_debug(f"on_cmd name {cmd_name}")

        if cmd_name == CMD_TOOL_REGISTER:
            tool_metadata_json = json.loads(cmd.get_property_to_json(CMD_PROPERTY_TOOL))
            async_ten_env.log_info(f"register tool: {tool_metadata_json}")
            tool_metadata = TenLLMToolMetadata.model_validate_json(tool_metadata_json)
            async with self.available_tools_lock:
                self.available_tools.append(tool_metadata)
            async_ten_env.return_result(CmdResult.create(StatusCode.OK), cmd)


    async def queue_input_item(self, data_type: TenLLMDataType, message: any, prepend: bool = False):
        await self.queue.put([data_type, message], prepend)

    async def flush_input_items(self, ten_env: TenEnv):
        """Flushes the self.queue and cancels the current task."""
        # Flush the queue using the new flush method
        await self.queue.flush()

        # Cancel the current task if one is running
        if self.current_task:
            ten_env.log_info("Cancelling the current task during flush.")
            self.current_task.cancel()

    def send_text_output(self, ten_env: TenEnv, sentence: str, end_of_segment: bool):
        try:
            output_data = Data.create("text_data")
            output_data.set_property_string(
                "text", sentence)
            output_data.set_property_bool(
                "end_of_segment", end_of_segment
            )
            ten_env.send_data(output_data)
            ten_env.log_info(
                f"{'end of segment ' if end_of_segment else ''}sent sentence [{sentence}]"
            )
        except Exception as err:
            ten_env.log_warn(
                f"send sentence [{sentence}] failed, err: {err}"
            )

    @abstractmethod
    async def on_text_completion(self, ten_env: TenEnv, message: any, **kargs: TenLLMTextCompletionArgs) -> None:
        pass

    @abstractmethod
    async def on_audio_completion(self, ten_env: TenEnv, message: any, **kargs: TenLLMAudioCompletionArgs) -> None:
        pass

    async def _process_queue(self, ten_env: TenEnv):
        """Asynchronously process queue items one by one."""
        while True:
            # Wait for an item to be available in the queue
            [data_type, message] = await self.queue.get()
            try:
                # Create a new task for the new message
                if data_type == TenLLMDataType.TEXT:
                    self.current_task = asyncio.create_task(
                        self.on_text_completion(ten_env, message))
                    await self.current_task  # Wait for the current task to finish or be cancelled
                elif data_type == TenLLMDataType.AUDIO:
                    await self.on_audio_completion(ten_env, message)
                else:
                    ten_env.log_warn(f"Unknown data type: {data_type}")
            except asyncio.CancelledError:
                ten_env.log_info(f"Task cancelled: {message}")

    