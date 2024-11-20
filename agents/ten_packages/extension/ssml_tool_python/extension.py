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

TOOL_NAME = "set_ssml"
TOOL_DESCRIPTION = "Use this function to trigger actions or music within the VR scene where the user can see and hear you."
TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "ssml": {
                "type": "string",
                "description": "Send one of these words to perform the corresponding action; SSML_KISS: blow a kiss, SSML_STRETCH: perform a stretch, SSML_BACKGROUND: change the scene background, SSML_DANCE: perform a dance, SSML_MUSIC: play some music, SSML_MUSIC_STOP: to stop the music. "
            }
        },
        "required": ["ssml"],
    }


class SSMLToolExtension(Extension):
    tools: dict = {}
    k: int = 10
    ten_env: Any = None

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("SSMLToolExtension on_init")
        self.ten_env = ten_env
        self.tools = {
            TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: TOOL_PARAMETERS,
                TOOL_CALLBACK: self._set_ssml
            }
        }

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("SSMLToolExtension on_start")
        
        # Register func
        for name, tool in self.tools.items():
            c = Cmd.create(CMD_TOOL_REGISTER)
            c.set_property_string(TOOL_REGISTER_PROPERTY_NAME, name)
            c.set_property_string(TOOL_REGISTER_PROPERTY_DESCRIPTON, tool[TOOL_REGISTER_PROPERTY_DESCRIPTON])
            c.set_property_string(TOOL_REGISTER_PROPERTY_PARAMETERS, json.dumps(tool[TOOL_REGISTER_PROPERTY_PARAMETERS]))
            ten_env.send_cmd(c, lambda ten, result: logger.info(f"register done, {result}"))

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("SSMLToolExtension on_stop")
        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("SSMLToolExtension on_deinit")
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
    
    def _set_ssml(self,  args:dict) -> Any:
        ssml = args["ssml"]
        logger.error(f"BenSet3 SSML {ssml}")
        try:
            d = Data.create("text_data")
            d.set_property_string("text", f"{ssml}")
            d.set_property_bool("end_of_segment", True)
            stream_id = 0
            d.set_property_int("stream_id", stream_id)
            d.set_property_bool("is_final", True)
            logger.debug(
                f"send SSML text {ssml}")
            self.ten_env.send_data(d)
        except:
            logger.exception(
                f"Error send SSML")

        return "OK"
