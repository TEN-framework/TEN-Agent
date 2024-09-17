#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
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
from ..openai_chatgpt_python.aibase import LLMToolExtension, TenLLMTool, TenLLMToolResult


class WeatherToolExtension(LLMToolExtension):
    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        super().on_start(ten_env)
        logger.info("WeatherToolExtension on_start")

        # TODO: read properties, initialize resources

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_stop")

        # TODO: clean up resources

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("WeatherToolExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        super().on_cmd(ten_env, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        # TODO: process data
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        pass

    async def on_register_tool(self, ten_env: TenEnv, data: any) -> TenLLMTool:
        return TenLLMTool.tool_from_json({
            "name": "get_weather_tool",
            "description": "Get the weather of a city",
            "arguments": [],
        })
    
    async def on_run_tool(self, ten_env: TenEnv, data: any) -> TenLLMToolResult:
        result = TenLLMToolResult()
        result.add_value("text", "the weather is sunny")
        return result
