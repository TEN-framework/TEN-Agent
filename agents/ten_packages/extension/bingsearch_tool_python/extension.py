#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import json
import requests
from typing import Any, List

from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from .log import logger

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
                "description": "The search query to call Bing Search."
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

class BingSearchToolExtension(Extension):
    api_key: str = ""
    tools: dict = {}
    k: int = 10

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("BingSearchToolExtension on_init")
        self.tools = {
            TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: TOOL_PARAMETERS,
                TOOL_CALLBACK: self._do_search
            }
        }

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("BingSearchToolExtension on_start")

        try:
            api_key = ten_env.get_property_string(PROPERTY_API_KEY)
            self.api_key = api_key
        except Exception as err:
            logger.info(
                f"GetProperty required {PROPERTY_API_KEY} failed, err: {err}")
            return
        
        # Register func
        for name, tool in self.tools.items():
            c = Cmd.create(CMD_TOOL_REGISTER)
            c.set_property_string(TOOL_REGISTER_PROPERTY_NAME, name)
            c.set_property_string(TOOL_REGISTER_PROPERTY_DESCRIPTON, tool[TOOL_REGISTER_PROPERTY_DESCRIPTON])
            c.set_property_string(TOOL_REGISTER_PROPERTY_PARAMETERS, json.dumps(tool[TOOL_REGISTER_PROPERTY_PARAMETERS]))
            ten_env.send_cmd(c, lambda ten, result: logger.info(f"register done, {result}"))

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("BingSearchToolExtension on_stop")

        # TODO: clean up resources

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("BingSearchToolExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info(f"on_cmd name {cmd_name} {cmd.to_json()}")

        # FIXME need to handle async
        try:
            name = cmd.get_property_string(CMD_PROPERTY_NAME)
            if name in self.tools:
                try:
                    tool = self.tools[name]
                    args = cmd.get_property_string(CMD_PROPERTY_ARGS)
                    arg_dict = json.loads(args)
                    logger.info(f"before callback {name}")
                    resp = tool[TOOL_CALLBACK](arg_dict)
                    logger.info(f"after callback {resp}")
                    cmd_result = CmdResult.create(StatusCode.OK)
                    cmd_result.set_property_string("response", json.dumps(resp))
                    ten_env.return_result(cmd_result, cmd)
                    return
                except:
                    logger.exception("Failed to callback")
                    cmd_result = CmdResult.create(StatusCode.ERROR)
                    ten_env.return_result(cmd_result, cmd)
                    return
            else:
                logger.error(f"unknown tool name {name}")
        except:
            logger.exception("Failed to get tool name")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            ten_env.return_result(cmd_result, cmd)
            return
            
        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass
    
    def _do_search(self, args:dict) -> Any:
        if "query" not in args:
            raise Exception("Failed to get property")
        
        query = args["query"]
        snippets = []
        results = self._bing_search_results(query, count=self.k)
        if len(results) == 0:
            return "No good Bing Search Result was found"
        for result in results:
            snippets.append(result["snippet"])

        return snippets
    
    def _bing_search_results(self, search_term: str, count: int) -> List[dict]:
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {
            "q": search_term,
            "count": count,
            "textDecorations": True,
            "textFormat": "HTML"
        }
        response = requests.get(
            DEFAULT_BING_SEARCH_ENDPOINT,
            headers=headers,
            params=params,  # type: ignore
        )
        response.raise_for_status()
        search_results = response.json()
        if "webPages" in search_results:
            return search_results["webPages"]["value"]
        return []