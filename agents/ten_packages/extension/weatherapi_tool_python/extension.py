#
#
# Agora Real Time Engagement
# Created by Tomas Liu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

import json
import aiohttp

from typing import Any
from dataclasses import dataclass

from ten import Cmd

from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig
from ten_ai_base import AsyncLLMToolBaseExtension
from ten_ai_base.types import LLMToolMetadata, LLMToolMetadataParameter, LLMToolResult, LLMToolResultLLMResult

CMD_TOOL_REGISTER = "tool_register"
CMD_TOOL_CALL = "tool_call"
CMD_PROPERTY_NAME = "name"
CMD_PROPERTY_ARGS = "args"

TOOL_REGISTER_PROPERTY_NAME = "name"
TOOL_REGISTER_PROPERTY_DESCRIPTON = "description"
TOOL_REGISTER_PROPERTY_PARAMETERS = "parameters"
TOOL_CALLBACK = "callback"

CURRENT_TOOL_NAME = "get_current_weather"
CURRENT_TOOL_DESCRIPTION = "Determine current weather in user's location."


# for free key, only 7 days before, see more in https://www.weatherapi.com/pricing.aspx
HISTORY_TOOL_NAME = "get_past_weather"
HISTORY_TOOL_DESCRIPTION = "Determine weather within past 7 days in user's location."

# for free key, only 3 days after, see more in https://www.weatherapi.com/pricing.aspx
FORECAST_TOOL_NAME = "get_future_weather"
FORECAST_TOOL_DESCRIPTION = "Determine weather in next 3 days in user's location."


PROPERTY_API_KEY = "api_key"  # Required

@dataclass
class WeatherToolConfig(BaseConfig):
    api_key: str = ""


class WeatherToolExtension(AsyncLLMToolBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.session = None
        self.ten_env = None
        self.config: WeatherToolConfig = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")
        self.session = aiohttp.ClientSession()

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")

        self.config = await WeatherToolConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")
        if self.config.api_key:
            await super().on_start(ten_env)

        self.ten_env = ten_env

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

        # TODO: clean up resources
        if self.session:
            await self.session.close()
            self.session = None  # Ensure it can't be reused accidentally

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        await super().on_cmd(ten_env, cmd)

    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name=CURRENT_TOOL_NAME,
                description=CURRENT_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="location",
                        type="string",
                        description="The city and state (use only English) e.g. San Francisco, CA",
                        required=True,
                    ),
                ],
            ),
            LLMToolMetadata(
                name=HISTORY_TOOL_NAME,
                description=HISTORY_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="location",
                        type="string",
                        description="The city and state (use only English) e.g. San Francisco, CA",
                        required=True,
                    ),
                    LLMToolMetadataParameter(
                        name="datetime",
                        type="string",
                        description="The datetime user is referring in date format e.g. 2024-10-09",
                        required=True,
                    ),
                ],
            ),
            LLMToolMetadata(
                name=FORECAST_TOOL_NAME,
                description=FORECAST_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="location",
                        type="string",
                        description="The city and state (use only English) e.g. San Francisco, CA",
                        required=True,
                    ),
                ],
            ),
        ]

    async def run_tool(
        self, ten_env: AsyncTenEnv, name: str, args: dict
    ) -> LLMToolResult | None:
        ten_env.log_info(f"run_tool name: {name}, args: {args}")
        if name == CURRENT_TOOL_NAME:
            result = await self._get_current_weather(args)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        elif name == HISTORY_TOOL_NAME:
            result = await self._get_past_weather(args)
            # result = LLMCompletionContentItemText(text="I see something")
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        elif name == FORECAST_TOOL_NAME:
            result = await self._get_future_weather(args)
            # result = LLMCompletionContentItemText(text="I see something")
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )

    async def _get_current_weather(self, args: dict) -> Any:
        if "location" not in args:
            raise ValueError("Failed to get property")

        try:
            location = args["location"]
            url = f"http://api.weatherapi.com/v1/current.json?key={self.config.api_key}&q={location}&aqi=no"

            async with self.session.get(url) as response:
                result = await response.json()
                return {
                    "location": result.get("location", {}).get("name", ""),
                    "temperature": result.get("current", {}).get("temp_c", ""),
                    "humidity": result.get("current", {}).get("humidity", ""),
                    "wind_speed": result.get("current", {}).get("wind_kph", ""),
                }
        except Exception as e:
            self.ten_env.log_error(f"Failed to get current weather: {e}")
            return None

    async def _get_past_weather(self, args: dict) -> Any:
        if "location" not in args or "datetime" not in args:
            raise ValueError("Failed to get property")

        location = args["location"]
        datetime = args["datetime"]
        url = f"http://api.weatherapi.com/v1/history.json?key={self.config.api_key}&q={location}&dt={datetime}"

        async with self.session.get(url) as response:
            result = await response.json()

            # Remove all hourly data
            if (
                "forecast" in result
                and "forecastday" in result["forecast"]
                and result["forecast"]["forecastday"]
            ):
                result["forecast"]["forecastday"][0].pop("hour", None)

            return result

    async def _get_future_weather(self, args: dict) -> Any:
        if "location" not in args:
            raise ValueError("Failed to get property")

        location = args["location"]
        url = f"http://api.weatherapi.com/v1/forecast.json?key={self.config.api_key}&q={location}&days=3&aqi=no&alerts=no"

        async with self.session.get(url) as response:
            result = await response.json()

            # Log the result
            self.ten_env.log_info(f"get result {result}")

            # Remove all hourly data
            for d in result.get("forecast", {}).get("forecastday", []):
                d.pop("hour", None)

            # Remove current weather data
            result.pop("current", None)

            return result
