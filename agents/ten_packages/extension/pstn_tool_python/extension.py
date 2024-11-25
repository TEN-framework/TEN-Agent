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

TOOL_NAME = "set_pstn"
TOOL_DESCRIPTION = "Use this function to dial a cell phone and connect the callee into the conversation. After using this function the next voice you hear should be the callee. "
TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "pstn": {
                "type": "string",
                "description": "The phone number to dial including country code."
            }
        },
        "required": ["pstn"],
    }


class PSTNToolExtension(Extension):
    tools: dict = {}
    k: int = 10
    ten_env: Any = None
    auth_key: str = ""
    channel: str = ""
    app_id: str = ""
    sip: str = ""
    region: str = ""
    uid: str = ""
    cfrom: str = ""

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("PSTNToolExtension on_init")
        self.ten_env = ten_env
        self.tools = {
            TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: TOOL_PARAMETERS,
                TOOL_CALLBACK: self._set_pstn
            }
        }

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("PSTNToolExtension on_start")
        self.channel = ten_env.get_property_string("channel")
        self.auth_key = ten_env.get_property_string("auth_key")
        self.app_id = ten_env.get_property_string("app_id")
        self.sip = ten_env.get_property_string("sip")
        self.region = ten_env.get_property_string("region")
        self.cfrom = ten_env.get_property_string("cfrom")
        self.uid = ten_env.get_property_string("uid")
        
        # Register func
        for name, tool in self.tools.items():
            c = Cmd.create(CMD_TOOL_REGISTER)
            c.set_property_string(TOOL_REGISTER_PROPERTY_NAME, name)
            c.set_property_string(TOOL_REGISTER_PROPERTY_DESCRIPTON, tool[TOOL_REGISTER_PROPERTY_DESCRIPTON])
            c.set_property_string(TOOL_REGISTER_PROPERTY_PARAMETERS, json.dumps(tool[TOOL_REGISTER_PROPERTY_PARAMETERS]))
            ten_env.send_cmd(c, lambda ten, result: logger.info(f"register done, {result}"))

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("PSTNToolExtension on_stop")
        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("PSTNToolExtension on_deinit")
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
    
    def _set_pstn(self,  args:dict) -> Any:
        pstn = args["pstn"]
        logger.info(f"BenSet3 PSTN {pstn}")
        url = "https://sipcm.agora.io/v1/api/pstn"
        headers = {            
            "Authorization": f"Basic {self.auth_key}",
            "Content-Type": "application/json"
        }
        data = {
            "action": "outbound",
            "appid": self.app_id,
            "region": self.region,
            "uid": self.uid,
            "channel": self.channel,
            "from":  self.cfrom,
            "to": pstn,
            "prompt": "false",
            "sip": self.sip,
            "token": self.app_id
        }
        logger.info(f"PRE CALL response PSTN ")
        response = requests.post(url, headers=headers, data=json.dumps(data))
        logger.info(f"response PSTN {response} {response.text} {response.status_code}")
        if response.status_code == 200:
            logger.info(f"Request succeeded: {response.json()}")
        else:
            logger.info(f"Request failed with status code {response.json()} {response.status_code}: {response.text}")
        
        return "OK"

        

        

        
