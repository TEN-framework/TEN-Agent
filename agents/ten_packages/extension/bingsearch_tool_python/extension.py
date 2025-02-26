#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import json
import aiohttp
from typing import Any, List

from ten import (
    Cmd,
)
from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig
from ten_ai_base.types import LLMToolMetadata, LLMToolMetadataParameter, LLMToolResult
from ten_ai_base.llm_tool import AsyncLLMToolBaseExtension

CMD_TOOL_REGISTER = "tool_register"
CMD_TOOL_CALL = "tool_call"
CMD_PROPERTY_NAME = "name"
CMD_PROPERTY_ARGS = "args"

TOOL_REGISTER_PROPERTY_NAME = "name"
TOOL_REGISTER_PROPERTY_DESCRIPTON = "description"
TOOL_REGISTER_PROPERTY_PARAMETERS = "parameters"
TOOL_CALLBACK = "callback"

TOOL_NAME = "bing_search"
TOOL_DESCRIPTION = "Use Bing.com to search for latest information. Call this function if you are not sure about the answer."
TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query to call Bing Search.",
        }
    },
    "required": ["query"],
}

PROPERTY_API_KEY = "api_key"  # Required

DEFAULT_BING_SEARCH_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

# BING_SEARCH_ENDPOINT is the default endpoint for Bing Web Search API.
# Currently There are two web-based Bing Search services available on Azure,
# i.e. Bing Web Search[1] and Bing Custom Search[2]. Compared to Bing Custom Search,
# Both services that provides a wide range of search results, while Bing Custom
# Search requires you to provide an additional custom search instance, `customConfig`.
# Both services are available for BingSearchAPIWrapper.
# History of Azure Bing Search API:
# Before shown in Azure Marketplace as a separate service, Bing Search APIs were
# part of Azure Cognitive Services, the endpoint of which is unique, and the user
# must specify the endpoint when making a request. After transitioning to Azure
# Marketplace, the endpoint is standardized and the user does not need to specify
# the endpoint[3].
# Reference:
#  1. https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
#  2. https://learn.microsoft.com/en-us/bing/search-apis/bing-custom-search/overview
#  3. https://azure.microsoft.com/en-in/updates/bing-search-apis-will-transition-from-azure-cognitive-services-to-azure-marketplace-on-31-october-2023/

class BingSearchToolConfig(BaseConfig):
    api_key: str = ""

class BingSearchToolExtension(AsyncLLMToolBaseExtension):

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.session = None
        self.config = None
        self.k = 10

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")
        self.session = aiohttp.ClientSession()
        await super().on_init(ten_env)

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        await super().on_start(ten_env)

        self.config = await BingSearchToolConfig.create_async(ten_env=ten_env)

        if not self.config.api_key:
            ten_env.log_info("API key is missing, exiting on_start")
            return

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

        # clean up resources
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None  # Ensure it can't be reused accidentally

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        await super().on_cmd(ten_env, cmd)

    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name=TOOL_NAME,
                description=TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="query",
                        type="string",
                        description="The search query to call Bing Search.",
                        required=True,
                    ),
                ],
            )
        ]

    async def run_tool(
        self, ten_env: AsyncTenEnv, name: str, args: dict
    ) -> LLMToolResult | None:
        if name == TOOL_NAME:
            result = await self._do_search(ten_env, args)
            # result = LLMCompletionContentItemText(text="I see something")
            return {"content": json.dumps(result)}

    async def _do_search(self, ten_env: AsyncTenEnv, args: dict) -> Any:
        if "query" not in args:
            raise ValueError("Failed to get property")

        query = args["query"]
        snippets = []
        results = await self._bing_search_results(ten_env, query, count=self.k)
        if len(results) == 0:
            return "No good Bing Search Result was found"

        for result in results:
            snippets.append(result["snippet"])

        return snippets

    async def _initialize_session(self, ten_env: AsyncTenEnv):
        if self.session is None or self.session.closed:
            ten_env.log_debug("Initializing new session")
            self.session = aiohttp.ClientSession()

    async def _bing_search_results(self, ten_env: AsyncTenEnv, search_term: str, count: int) -> List[dict]:
        await self._initialize_session(ten_env)
        headers = {"Ocp-Apim-Subscription-Key": self.config.api_key}
        params = {
            "q": search_term,
            "count": count,
            "textDecorations": "true",
            "textFormat": "HTML",
        }

        async with self.session as session:
            async with session.get(
                DEFAULT_BING_SEARCH_ENDPOINT, headers=headers, params=params
            ) as response:
                response.raise_for_status()
                search_results = await response.json()

        if "webPages" in search_results:
            return search_results["webPages"]["value"]
        return []
