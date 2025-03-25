#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
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


class ReasoningMode(str, Enum):
    ModeV1 = "v1"


class ThinkParser:
    def __init__(self):
        self.state = "NORMAL"  # States: 'NORMAL', 'THINK'
        self.think_content = ""
        self.content = ""

    def process(self, new_chars):
        if new_chars == "<think>":
            self.state = "THINK"
            return True
        elif new_chars == "</think>":
            self.state = "NORMAL"
            return True
        else:
            if self.state == "THINK":
                self.think_content += new_chars
        return False

    def process_by_reasoning_content(self, reasoning_content):
        state_changed = False
        if reasoning_content:
            if self.state == "NORMAL":
                self.state = "THINK"
                state_changed = True
            self.think_content += reasoning_content
        elif self.state == "THINK":
            self.state = "NORMAL"
            state_changed = True
        return state_changed


class OpenAIChatGPT:
    client = None

    def __init__(self, ten_env: AsyncTenEnv, config: OpenAIChatGPTConfig):
        self.config = config
        self.ten_env = ten_env
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
            self.client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                default_headers={
                    "api-key": config.api_key,
                    "Authorization": f"Bearer {config.api_key}",
                },
            )
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

        # Example usage
        parser = ThinkParser()
        reasoning_mode = None

        async for chat_completion in response:
            # self.ten_env.log_info(f"Chat completion: {chat_completion}")
            if len(chat_completion.choices) == 0:
                continue
            choice = chat_completion.choices[0]
            delta = choice.delta

            content = delta.content if delta and delta.content else ""
            reasoning_content = (
                delta.reasoning_content
                if delta
                and hasattr(delta, "reasoning_content")
                and delta.reasoning_content
                else ""
            )

            if reasoning_mode is None and reasoning_content is not None:
                reasoning_mode = ReasoningMode.ModeV1

            # Emit content update event (fire-and-forget)
            if listener and (content or reasoning_mode == ReasoningMode.ModeV1):
                prev_state = parser.state

                if reasoning_mode == ReasoningMode.ModeV1:
                    # self.ten_env.log_info("process_by_reasoning_content")
                    think_state_changed = parser.process_by_reasoning_content(
                        reasoning_content
                    )
                else:
                    think_state_changed = parser.process(content)

                if not think_state_changed:
                    # self.ten_env.log_info(f"state: {parser.state}, content: {content}, think: {parser.think_content}")
                    if parser.state == "THINK":
                        listener.emit("reasoning_update", parser.think_content)
                    elif parser.state == "NORMAL":
                        listener.emit("content_update", content)

                if prev_state == "THINK" and parser.state == "NORMAL":
                    listener.emit("reasoning_update_finish", parser.think_content)
                    parser.think_content = ""

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
