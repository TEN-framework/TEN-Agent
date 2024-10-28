#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from abc import ABC, abstractmethod
import asyncio
from enum import Enum
from typing import Optional, TypedDict, Union

from pydantic import BaseModel
from ten import (
    AsyncExtension,
    TenEnv,
    Data,
)
from ten.async_ten_env import AsyncTenEnv
from ten.cmd import Cmd
from ten.cmd_result import CmdResult, StatusCode
from .const import CMD_PROPERTY_TOOL, CMD_TOOL_REGISTER
from .types import TenLLMCallCompletionArgs, TenLLMDataCompletionArgs, TenLLMToolMetadata
from .helper import AsyncQueue
import json

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
        try:
            if cmd_name == CMD_TOOL_REGISTER:
                tool_metadata_json = json.loads(cmd.get_property_to_json(CMD_PROPERTY_TOOL))
                async_ten_env.log_info(f"register tool: {tool_metadata_json}")
                tool_metadata = TenLLMToolMetadata.model_validate_json(tool_metadata_json)
                async with self.available_tools_lock:
                    self.available_tools.append(tool_metadata)
                await self.on_tools_update(async_ten_env, tool_metadata)
                async_ten_env.return_result(CmdResult.create(StatusCode.OK), cmd)
        except Exception as err:
            async_ten_env.log_warn(f"on_cmd failed: {err}")
            async_ten_env.return_result(CmdResult.create(StatusCode.ERROR), cmd)


    async def queue_input_item(self, prepend: bool = False, **kargs: TenLLMDataCompletionArgs):
        await self.queue.put(kargs, prepend)

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
    async def on_call_chat_completion(self, ten_env: TenEnv, **kargs: TenLLMCallCompletionArgs) -> None:
        pass

    @abstractmethod
    async def on_data_chat_completion(self, ten_env: TenEnv, **kargs: TenLLMDataCompletionArgs) -> None:
        pass

    @abstractmethod
    async def on_tools_update(self, ten_env: TenEnv, tool: TenLLMToolMetadata) -> None:
        pass

    async def _process_queue(self, ten_env: TenEnv):
        """Asynchronously process queue items one by one."""
        while True:
            # Wait for an item to be available in the queue
            args = await self.queue.get()
            try:
                ten_env.log_info(f"Processing queue item: {args}")
                self.current_task = asyncio.create_task(
                    self.on_data_chat_completion(ten_env, **args))
                await self.current_task  # Wait for the current task to finish or be cancelled
            except asyncio.CancelledError:
                ten_env.log_info(f"Task cancelled: {args}")

    