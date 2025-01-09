#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
from ten import (
    Data,
    TenEnv,
    AsyncTenEnv,
)
from ten_ai_base import (
    AsyncLLMToolBaseExtension, LLMToolMetadata, LLMToolResult
)
from ten_ai_base.const import DATA_OUT_PROPERTY_END_OF_SEGMENT, DATA_OUT_PROPERTY_TEXT, RAW_DATA_OUT_NAME
from ten_ai_base.types import LLMToolMetadataParameter, LLMToolResultNormal
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

    async def send_image(self, async_ten_env: AsyncTenEnv, image_url: str) -> None:
        # Implement this method to send the image to the chat.
        async_ten_env.log_info(f"Sending image: {image_url}")
        try:
            sentence = json.dumps({"data":{"image_url": image_url}, "type": "image_url"})
            output_data = Data.create(RAW_DATA_OUT_NAME)
            output_data.set_property_string(
                DATA_OUT_PROPERTY_TEXT,
                sentence
            )
            output_data.set_property_bool(
                DATA_OUT_PROPERTY_END_OF_SEGMENT, True
            )
            asyncio.create_task(async_ten_env.send_data(output_data))
            async_ten_env.log_info(
                f"sent sentence [{sentence}]"
            )
        except Exception as err:
            async_ten_env.log_warn(f"send sentence [{sentence}] failed, err: {err}")


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
                await self.send_image(ten_env, response_url)
                result = LLMToolResultNormal(
                    type="normal",
                    content=json.dumps({"success": True}),
                )
                return result
