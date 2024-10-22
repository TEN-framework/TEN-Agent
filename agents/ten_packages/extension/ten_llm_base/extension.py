#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from abc import ABC, abstractmethod
import asyncio
from enum import Enum
from typing import TypedDict
from ten import (
    AsyncExtension,
    TenEnv,
    Data,
)
from .helper import AsyncQueue

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

    async def on_init(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_init")
        ten_env.on_init_done()

    async def on_start(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_start")

        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._process_queue(ten_env))

    async def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def queue_input_item(self, data_type: TenLLMDataType, message: any):
        await self.queue.put([data_type, message])

    async def flush_input_items(self, ten_env: TenEnv):
        """Flushes the self.queue and cancels the current task."""
        # Flush the queue using the new flush method
        await self.queue.flush()

        # Cancel the current task if one is running
        if self.current_task:
            ten_env.log_info("Cancelling the current task during flush.")
            self.current_task.cancel()

    async def send_text_output(self, ten_env: TenEnv, sentence: str, end_of_segment: bool):
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

    