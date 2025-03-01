import random
import requests
from openai import AsyncOpenAI
from ten_ai_base.config import BaseConfig
from dataclasses import dataclass
from ten.async_ten_env import AsyncTenEnv

@dataclass
class OpenAIChatGPTConfig(BaseConfig):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"  # Adjust this to match the equivalent of `openai.GPT4o` in the Python library
    prompt: str = "You are a voice assistant who talks in a conversational way and can chat with me like my friends. I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. Don’t talk like a robot, instead I would like you to talk like a real human with emotions. I will use your answer for text-to-speech, so don’t return me any meaningless characters. I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. When giving me a list of options, express the options in a narrative way instead of bullet points."
    frequency_penalty: float = 0.9
    presence_penalty: float = 0.9
    top_p: float = 1.0
    temperature: float = 0.1
    max_tokens: int = 512
    seed: int = random.randint(0, 10000)
    proxy_url: str = ""
    max_memory_length: int = 10
    vendor: str = "openai"
    azure_endpoint: str = ""
    azure_api_version: str = ""

    @classmethod
    def default_config(cls):
        return cls(
            base_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4o",  # Adjust this to match the equivalent of `openai.GPT4o` in the Python library
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
    def __init__(self, ten_env:AsyncTenEnv, config: OpenAIChatGPTConfig):
        self.config = config
        ten_env.log_info(f"apikey {config.api_key}, base_url {config.base_url}")
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
            self.session.proxies.update(proxies)
        self.client.session = self.session

    async def get_chat_completions_structured(self, messages, response_format):
        req = {
            "model":"gpt-4o-2024-08-06",
            "messages": [
                {
                    "role": "system",
                    "content": self.config.prompt,
                },
                *messages,
            ],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "presence_penalty": self.config.presence_penalty,
            "frequency_penalty": self.config.frequency_penalty,
            "max_tokens": self.config.max_tokens,
            "seed": self.config.seed,
            "response_format": response_format,
        }

        try:
            completion = await self.client.beta.chat.completions.parse(**req)
            response = completion.choices[0].message
            if response.parsed:
                return response.parsed
            elif response.refusal:
                # handle refusal
                raise RuntimeError(f"Refusal: {response.refusal}")
        except Exception as e:
            raise RuntimeError(f"CreateChatCompletionStructured failed, err: {e}") from e

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
            raise RuntimeError(f"CreateChatCompletionStream failed, err: {e}") from e
        
        full_content = ""

        async for chat_completion in response:
            choice = chat_completion.choices[0]
            delta = choice.delta
            content = delta.content if delta and delta.content else ""
            # Emit content update event (fire-and-forget)
            if listener and content:
                listener.emit('content_update', content)

            full_content += content
            # Check for tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    # Emit tool call event (fire-and-forget)
                    if listener:
                        listener.emit('tool_call', tool_call)

        # Emit content finished event after the loop completes
        if listener:
            listener.emit('content_finished', full_content)