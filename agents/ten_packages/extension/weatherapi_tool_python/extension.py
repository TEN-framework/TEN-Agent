#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
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

TOOL_NAME = "get_current_weather"
TOOL_DESCRIPTION = "Determine weather in my location"
TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state e.g. San Francisco, CA"
            }
        },
        "required": ["location"],
    }

PROPERTY_API_KEY = "api_key"  # Required

class WeatherToolExtension(Extension):
    api_key: str = ""

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_init")

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
        #c = Cmd.create(CMD_TOOL_REGISTER)
        #c.set_property_string(TOOL_REGISTER_PROPERTY_NAME, TOOL_NAME)
        #c.set_property_string(TOOL_REGISTER_PROPERTY_DESCRIPTON, TOOL_DESCRIPTION)
        #c.set_property_string(TOOL_REGISTER_PROPERTY_PARAMETERS, json.dumps(TOOL_PARAMETERS))
        #ten_env.send_cmd(c, lambda ten, result: logger.info(f"register done, {result}"))

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_stop")

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd name {}".format(cmd_name))

        try:
            name = cmd.get_property_string(CMD_PROPERTY_NAME)
            if name == TOOL_NAME:
                try:
                    args = cmd.get_property_string(CMD_PROPERTY_ARGS)
                    arg_dict = json.loads(args)
                    if "location" in arg_dict:
                        resp = self._get_current_weather(arg_dict["location"])
                        cmd_result = CmdResult.create(StatusCode.OK)
                        cmd_result.set_property_string("response", json.dumps(resp))
                        ten_env.return_result(cmd_result, cmd)
                    else:
                        cmd_result = CmdResult.create(StatusCode.ERROR)
                        ten_env.return_result(cmd_result, cmd)
                except:
                    logger.exception(f"Failed to get weather")
                    cmd_result = CmdResult.create(StatusCode.ERROR)
                    ten_env.return_result(cmd_result, cmd)
        except:
            logger.exception(f"Failed to get tool name")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            ten_env.return_result(cmd_result, cmd)
            

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass

    def _get_current_weather(self, location:str) -> Any:
        url = f"http://api.weatherapi.com/v1/current.json?key={self.api_key}&q={location}&aqi=no"
        response = requests.get(url)
        result = response.json()
        return result