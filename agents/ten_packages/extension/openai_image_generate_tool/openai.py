#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from dataclasses import dataclass
import requests
from openai import AsyncOpenAI, AsyncAzureOpenAI

from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig


@dataclass
class OpenAIImageGenerateToolConfig(BaseConfig):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "dall-e-3"
    size: str = "1024x1024"
    quality: str = "standard"
    n: int = 1
    proxy_url: str = ""
    vendor: str = "openai"
    azure_endpoint: str = ""
    azure_api_version: str = ""

class OpenAIImageGenerateClient:
    client = None

    def __init__(self, ten_env: AsyncTenEnv, config: OpenAIImageGenerateToolConfig):
        self.config = config
        ten_env.log_info(f"OpenAIImageGenerateClient initialized with config: {config.api_key}")
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


    async def generate_images(self, prompt: str) -> str:
        req = {
            "model": self.config.model,
            "prompt": prompt,
            "size": self.config.size,
            "quality": self.config.quality,
            "n": self.config.n,
        }

        try:
            response = await self.client.images.generate(**req)
        except Exception as e:
            raise RuntimeError(f"GenerateImages failed, err: {e}") from e
        return response.data[0].url