#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from collections import defaultdict
import random
import requests
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
from .log import logger


class OpenAIChatGPTConfig:
    def __init__(self, 
            base_url: str, 
            api_key: str, 
            model: str, 
            prompt: str, 
            frequency_penalty: float, 
            presence_penalty: float, 
            top_p: float, 
            temperature: float, 
            max_tokens: int, 
            seed: Optional[int] = None, 
            proxy_url: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.prompt = prompt
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.top_p = top_p
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed if seed is not None else random.randint(0, 10000)
        self.proxy_url = proxy_url

    @classmethod
    def default_config(cls):
        return cls(
            base_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4",  # Adjust this to match the equivalent of `openai.GPT4o` in the Python library
            prompt="You are a voice assistant who talks in a conversational way and can chat with me like my friends. I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. Don’t talk like a robot, instead I would like you to talk like a real human with emotions. I will use your answer for text-to-speech, so don’t return me any meaningless characters. I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. When giving me a list of options, express the options in a narrative way instead of bullet points.",
            frequency_penalty=0.9,
            presence_penalty=0.9,
            top_p=1.0,
            temperature=0.1,
            max_tokens=512,
            seed=random.randint(0, 10000),
            proxy_url=""
        )
    

class OpenAIChatGPT:
    client = None
    def __init__(self, config: OpenAIChatGPTConfig):
        self.config = config
        logger.info(f"OpenAIChatGPT initialized with config: {config.api_key}")
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        self.session = requests.Session()
        if config.proxy_url:
            proxies = {
                "http": config.proxy_url,
                "https": config.proxy_url,
            }
            logger.info(f"Setting proxies: {proxies}")
            self.session.proxies.update(proxies)
        self.client.session = self.session

    async def get_chat_completions_stream(self, messages, tools = None, listener = None):
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
            raise Exception(f"CreateChatCompletionStream failed, err: {e}")
        
        full_content = ""
        # Check for tool calls
        tool_calls_dict = defaultdict(lambda: {"id": None, "function": {"arguments": "", "name": None}, "type": None})

        async for chat_completion in response:
            choice = chat_completion.choices[0]
            delta = choice.delta

            content = delta.content if delta and delta.content else ""

            # Emit content update event (fire-and-forget)
            if listener and content:
                listener.emit('content_update', content)

            full_content += content

            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    logger.info(f"tool_call: {tool_call}")
                    if tool_call.id is not None:
                        tool_calls_dict[tool_call.index]["id"] = tool_call.id

                    # If the function name is not None, set it
                    if tool_call.function.name is not None:
                        tool_calls_dict[tool_call.index]["function"]["name"] = tool_call.function.name

                    # Append the arguments
                    tool_calls_dict[tool_call.index]["function"]["arguments"] += tool_call.function.arguments

                    # If the type is not None, set it
                    if tool_call.type is not None:
                        tool_calls_dict[tool_call.index]["type"] = tool_call.type


        # Convert the dictionary to a list
        tool_calls_list = list(tool_calls_dict.values())

        # Emit tool calls event (fire-and-forget)
        if listener and tool_calls_list:
            for tool_call in tool_calls_list:
                listener.emit('tool_call', tool_call)

        # Emit content finished event after the loop completes
        if listener:
            listener.emit('content_finished', full_content)
