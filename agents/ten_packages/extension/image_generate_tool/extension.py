#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    TenEnv,
    AsyncTenEnv,
)
from ten_ai_base import (
    AsyncLLMToolBaseExtension, LLMToolMetadata, LLMToolResult, BaseConfig
)
from dataclasses import dataclass


@dataclass
class ImageGenerateToolConfig(BaseConfig):
    # TODO: add extra config fields here
    pass


class ImageGenerateToolExtension(AsyncLLMToolBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.config = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)

        # initialize configuration
        self.config = await ImageGenerateToolConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        # Implement this method to construct and start your resources.
        ten_env.log_debug("TODO: on_start")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)

        #Implement this method to stop and destruct your resources.
        ten_env.log_debug("TODO: on_stop")

    def get_tool_metadata(self, ten_env: TenEnv) -> list[LLMToolMetadata]:
        ten_env.log_debug("TODO: get_tool_metadata")
        return []

    async def run_tool(self, ten_env: AsyncTenEnv, name: str, args: dict) -> LLMToolResult | None:
        ten_env.log_debug(f"TODO: run_tool {name} {args}")
