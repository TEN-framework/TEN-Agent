#
#
# Agora Real Time Engagement
# Created by Tomas Liu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

import json
import requests

from typing import Any

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

CURRENT_TOOL_NAME = "get_current_weather"
CURRENT_TOOL_DESCRIPTION = "Determine current weather in user's location."
CURRENT_TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state (use only English) e.g. San Francisco, CA"
            }
        },
        "required": ["location"],
    }

# for free key, only 7 days before, see more in https://www.weatherapi.com/pricing.aspx
HISTORY_TOOL_NAME = "get_past_weather"
HISTORY_TOOL_DESCRIPTION = "Determine weather within past 7 days in user's location." 
HISTORY_TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state (use only English) e.g. San Francisco, CA"
            },
            "datetime": {
                "type": "string",
                "description": "The datetime user is referring in date format e.g. 2024-10-09"
            }
        },
        "required": ["location", "datetime"],
}

# for free key, only 3 days after, see more in https://www.weatherapi.com/pricing.aspx
FORCAST_TOOL_NAME = "get_future_weather"
FORCAST_TOOL_DESCRIPTION = "Determine weather in next 3 days in user's location." 
FORCAST_TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state (use only English) e.g. San Francisco, CA"
            }
        },
        "required": ["location"],
}

PROPERTY_API_KEY = "api_key"  # Required

class WeatherToolExtension(Extension):
    api_key: str = ""
    tools: dict = {}

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_init")

        self.tools = {
            CURRENT_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: CURRENT_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: CURRENT_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: CURRENT_TOOL_PARAMETERS,
                TOOL_CALLBACK: self._get_current_weather
            },
            HISTORY_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: HISTORY_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: HISTORY_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: HISTORY_TOOL_PARAMETERS,
                TOOL_CALLBACK: self._get_past_weather
            },
            FORCAST_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: FORCAST_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: FORCAST_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: FORCAST_TOOL_PARAMETERS,
                TOOL_CALLBACK: self._get_future_weather
            },
            # TODO other tools
        }

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_start")

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
        logger.info("WeatherToolExtension on_stop")

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_deinit")
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

    def _get_current_weather(self, args:dict) -> Any:
        if "location" not in args:
            raise Exception("Failed to get property")
        
        location = args["location"]
        url = f"http://api.weatherapi.com/v1/current.json?key={self.api_key}&q={location}&aqi=no"
        response = requests.get(url)
        result = response.json()
        return result
    
    def _get_past_weather(self, args:dict) -> Any:
        if "location" not in args or "datetime" not in args:
            raise Exception("Failed to get property")
        
        location = args["location"]
        datetime = args["datetime"]
        url = f"http://api.weatherapi.com/v1/history.json?key={self.api_key}&q={location}&dt={datetime}"
        response = requests.get(url)
        result = response.json()
        # remove all hourly data
        del result["forecast"]["forecastday"][0]["hour"]
        return result
    
    def _get_future_weather(self, args:dict) -> Any:
        if "location" not in args:
            raise Exception("Failed to get property")
        
        location = args["location"]
        url = f"http://api.weatherapi.com/v1/forecast.json?key={self.api_key}&q={location}&days=3&aqi=no&alerts=no"
        response = requests.get(url)
        result = response.json()
        logger.info(f"get result {result}")
        # remove all hourly data
        for d in result["forecast"]["forecastday"]:
            del d["hour"]
        del result["current"]
        return result