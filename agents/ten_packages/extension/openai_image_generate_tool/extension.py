#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json
from ten import (
    TenEnv,
    AsyncTenEnv,
)
from ten_ai_base import (
    AsyncLLMToolBaseExtension, LLMToolMetadata, LLMToolResult
)
from ten_ai_base.types import LLMChatCompletionContentPartImageParam, LLMToolMetadataParameter, LLMToolResultNormal
from .openai import OpenAIImageGenerateClient, OpenAIImageGenerateToolConfig

class OpenAIImageGenerateToolExtension(AsyncLLMToolBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.config = None
        self.client = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)

        # initialize configuration
        self.config = await OpenAIImageGenerateToolConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.api_key:
            ten_env.log_error("API key is not set")
            return

        # initialize OpenAIImageGenerateClient
        self.client = OpenAIImageGenerateClient(ten_env, self.config)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)

    def get_tool_metadata(self, ten_env: TenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name="image_generate",
                description="Generate image by prompt query",
                parameters=[
                    LLMToolMetadataParameter(
                        name="prompt",
                        type="string",
                        description="Prompt to generate images",
                    ),
                ],
            )
        ]

    async def run_tool(self, ten_env: AsyncTenEnv, name: str, args: dict) -> LLMToolResult | None:
        ten_env.log_info(f"run_tool {name} {args}")
        if name == "image_generate":
            prompt = args.get("prompt")
            if prompt:
                # Implement this method to run your tool with the given arguments.
                ten_env.log_info(f"Generating image with prompt: {prompt}")
                # call OpenAIImageGenerateClient to generate images
                response_url = await self.client.generate_images(prompt)
                ten_env.log_info(f"Generated image: {response_url}")
                result = LLMToolResultNormal(
                    type="normal",
                    content={"data":{"image_url": response_url}, "type": "image_url"},
                )
                return result
