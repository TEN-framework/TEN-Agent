#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import AsyncTenEnv
from ten_ai_base import (
    AsyncLLMBaseExtension, LLMCallCompletionArgs, LLMDataCompletionArgs, LLMToolMetadata
)


class DefaultAsyncLLMExtension(AsyncLLMBaseExtension):
    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)

        """Implement this method to construct and start your resources."""
        ten_env.log_debug("TODO: on_start")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)

        """Implement this method to stop and destruct your resources."""
        ten_env.log_debug("TODO: on_stop")

    async def on_call_chat_completion(self, ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs) -> None:
        """Called when a chat completion is requested by cmd call. Implement this method to process the chat completion."""
        ten_env.log_debug("TODO: on_call_chat_completion")

    async def on_data_chat_completion(self, ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs) -> None:
        """
        Called when a chat completion is requested by data input. Implement this method to process the chat completion.
        Note that this method is stream-based, and it should consider supporting local context caching.
        """
        ten_env.log_debug("TODO: on_data_chat_completion")

    async def on_tools_update(self, ten_env: AsyncTenEnv, tool: LLMToolMetadata) -> None:
        """Called when a new tool is registered. Implement this method to process the new tool."""
        ten_env.log_debug("TODO: on_tools_update")
