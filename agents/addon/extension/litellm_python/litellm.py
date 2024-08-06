import litellm
import random
from typing import Dict, List, Optional


class LiteLLMConfig:
    def __init__(self,
                 api_key: str,
                 base_url: str,
                 frequency_penalty: float,
                 max_tokens: int,
                 model: str,
                 presence_penalty: float,
                 prompt: str,
                 provider: str,
                 temperature: float,
                 top_p: float,
                 seed: Optional[int] = None,):
        self.api_key = api_key
        self.base_url = base_url
        self.frequency_penalty = frequency_penalty
        self.max_tokens = max_tokens
        self.model = model
        self.presence_penalty = presence_penalty
        self.prompt = prompt
        self.provider = provider
        self.seed = seed if seed is not None else random.randint(0, 10000)
        self.temperature = temperature
        self.top_p = top_p

    @classmethod
    def default_config(cls):
        return cls(
            api_key="",
            base_url="https://api.openai.com/v1",
            max_tokens=512,
            model="gpt-4o-mini",
            prompt="You are a voice assistant who talks in a conversational way and can chat with me like my friends. I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. Don’t talk like a robot, instead I would like you to talk like a real human with emotions. I will use your answer for text-to-speech, so don’t return me any meaningless characters. I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. When giving me a list of options, express the options in a narrative way instead of bullet points.",
            frequency_penalty=0.9,
            presence_penalty=0.9,
            provider="openai",
            seed=random.randint(0, 10000),
            temperature=0.1,
            top_p=1.0
        )


class LiteLLM:
    def __init__(self, config: LiteLLMConfig):
        self.config = config

    def get_chat_completions_stream(self, messages: List[Dict[str, str]]):
        kwargs = {
            "base_url": self.config.base_url,
            "custom_llm_provider": self.config.provider,
            "frequency_penalty": self.config.frequency_penalty,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": self.config.prompt,
                },
                *messages,
            ],
            "model": self.config.model,
            "presence_penalty": self.config.presence_penalty,
            "seed": self.config.seed,
            "stream": True,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }

        try:
            response = litellm.completion(**kwargs)

            return response
        except Exception as e:
            raise Exception(f"CreateChatCompletionStream failed, err: {e}")
