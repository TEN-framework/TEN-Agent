import random
import requests
import openai
from typing import List, Dict, Any, Optional


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
    def __init__(self, config: OpenAIChatGPTConfig):
        self.config = config
        openai.api_key = config.api_key
        openai.api_base = config.base_url
        if config.proxy_url:
            proxies = {
                "http": config.proxy_url,
                "https": config.proxy_url,
            }
            self.session = requests.Session()
            self.session.proxies.update(proxies)
        else:
            self.session = requests.Session()

    def get_chat_completions_stream(self, messages):
        req = {
            "model": self.config["Model"],
            "messages": [
                {
                    "role": "system",
                    "content": self.config["Prompt"],
                },
                *messages,
            ],
            "temperature": self.config["Temperature"],
            "top_p": self.config["TopP"],
            "presence_penalty": self.config["PresencePenalty"],
            "frequency_penalty": self.config["FrequencyPenalty"],
            "max_tokens": self.config["MaxTokens"],
            "seed": self.config["Seed"],
            "stream": True,
        }

        try:
            response = self.client.Completion.create(**req)
            return response
        except Exception as e:
            raise Exception(f"CreateChatCompletionStream failed, err: {e}")