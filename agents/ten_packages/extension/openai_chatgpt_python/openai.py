#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from collections import defaultdict
from dataclasses import dataclass
import random
import requests
from openai import AsyncOpenAI, AsyncAzureOpenAI
from openai.types.chat.chat_completion import ChatCompletion

from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig


@dataclass
class OpenAIChatGPTConfig(BaseConfig):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = (
        "gpt-4o"  # Adjust this to match the equivalent of `openai.GPT4o` in the Python library
    )
    prompt: str = (
        "You are a voice assistant who talks in a conversational way and can chat with me like my friends. I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. Don’t talk like a robot, instead I would like you to talk like a real human with emotions. I will use your answer for text-to-speech, so don’t return me any meaningless characters. I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. When giving me a list of options, express the options in a narrative way instead of bullet points."
    )
    frequency_penalty: float = 0.9
    presence_penalty: float = 0.9
    top_p: float = 1.0
    temperature: float = 0.1
    max_tokens: int = 512
    seed: int = random.randint(0, 10000)
    proxy_url: str = ""
    greeting: str = "Hello, how can I help you today?"
    max_memory_length: int = 10
    vendor: str = "openai"
    azure_endpoint: str = ""
    azure_api_version: str = ""

@dataclass
class OpenAIImageConfig(BaseConfig):
    model: str = "dall-e-3"
    size: str = "512x512"
    quality: str = "standard"
    n: int = 1


class OpenAIChatGPT:
    client = None

    def __init__(self, ten_env: AsyncTenEnv, config: OpenAIChatGPTConfig, image_config: OpenAIImageConfig):
        self.config = config
        self.image_config = image_config
        ten_env.log_info(f"OpenAIChatGPT initialized with config: {config.api_key}")
        if self.config.vendor == "azure":
            self.client = AsyncAzureOpenAI(
                api_key=config.api_key,
                api_version=self.config.azure_api_version,
                azure_endpoint=config.azure_endpoint,
            )
            ten_env.log_info(
                f"Using Azure OpenAI with endpoint: {config.azure_endpoint}, api_version: {config.azure_api_version}"
            )
        else:
            self.client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        self.session = requests.Session()
        if config.proxy_url:
            proxies = {
                "http": config.proxy_url,
                "https": config.proxy_url,
            }
            ten_env.log_info(f"Setting proxies: {proxies}")
            self.session.proxies.update(proxies)
        self.client.session = self.session

    async def get_chat_completions(self, messages, tools=None) -> ChatCompletion:
        req = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": self.config.prompt,
                },
                *messages,
            ],
            "tools": tools,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "presence_penalty": self.config.presence_penalty,
            "frequency_penalty": self.config.frequency_penalty,
            "max_tokens": self.config.max_tokens,
            "seed": self.config.seed,
        }

        try:
            response = await self.client.chat.completions.create(**req)
        except Exception as e:
            raise RuntimeError(f"CreateChatCompletion failed, err: {e}") from e

        return response

    async def get_chat_completions_stream(self, messages, tools=None, listener=None):
        req = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": self.config.prompt,
                },
                *messages,
            ],
            "tools": tools,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "presence_penalty": self.config.presence_penalty,
            "frequency_penalty": self.config.frequency_penalty,
            "max_tokens": self.config.max_tokens,
            "seed": self.config.seed,
            "stream": True,
        }

        try:
            response = await self.client.chat.completions.create(**req)
        except Exception as e:
            raise RuntimeError(f"CreateChatCompletionStream failed, err: {e}") from e

        full_content = ""
        # Check for tool calls
        tool_calls_dict = defaultdict(
            lambda: {
                "id": None,
                "function": {"arguments": "", "name": None},
                "type": None,
            }
        )

        async for chat_completion in response:
            if len(chat_completion.choices) == 0:
                continue
            choice = chat_completion.choices[0]
            delta = choice.delta

            content = delta.content if delta and delta.content else ""

            # Emit content update event (fire-and-forget)
            if listener and content:
                listener.emit("content_update", content)

            full_content += content

            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    if tool_call.id is not None:
                        tool_calls_dict[tool_call.index]["id"] = tool_call.id

                    # If the function name is not None, set it
                    if tool_call.function.name is not None:
                        tool_calls_dict[tool_call.index]["function"][
                            "name"
                        ] = tool_call.function.name

                    # Append the arguments
                    tool_calls_dict[tool_call.index]["function"][
                        "arguments"
                    ] += tool_call.function.arguments

                    # If the type is not None, set it
                    if tool_call.type is not None:
                        tool_calls_dict[tool_call.index]["type"] = tool_call.type

        # Convert the dictionary to a list
        tool_calls_list = list(tool_calls_dict.values())

        # Emit tool calls event (fire-and-forget)
        if listener and tool_calls_list:
            for tool_call in tool_calls_list:
                listener.emit("tool_call", tool_call)

        # Emit content finished event after the loop completes
        if listener:
            listener.emit("content_finished", full_content)


    async def generate_image(self, prompt:str):
        try:
            response = await self.client.images.generate(
                prompt=prompt,
                model=self.image_config.model,
                size=self.image_config.size,
                quality=self.image_config.quality,
            )
        except Exception as e:
            raise RuntimeError(f"GenerateImage failed, err: {e}") from e
        
        return response.data[0].url