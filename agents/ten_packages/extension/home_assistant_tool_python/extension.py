#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json
from typing import Any, Dict, List
from dataclasses import dataclass
from ten_ai_base.config import BaseConfig
from ten_ai_base import AsyncLLMToolBaseExtension
from ten_ai_base.types import LLMToolMetadata, LLMToolMetadataParameter, LLMToolResult, LLMToolResultLLMResult
from .device_controller import DeviceController

from ten import (
    AsyncTenEnv,
    Cmd,
)

LIGHT_TOOL_NAME = "light_control"
CAMERA_TOOL_NAME = "camera_control"
CLIMATE_TOOL_NAME = "climate_control"
COVER_TOOL_NAME = "cover_control"
MEDIA_PLAYER_TOOL_NAME = "media_player_control"
FAN_TOOL_NAME = "fan_control"

@dataclass
class HomeAssistantConfig(BaseConfig):
    base_url: str = ""
    api_key: str = ""

class HomeAssistantExtension(AsyncLLMToolBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.session = None
        self.config: HomeAssistantConfig = None
        self.device_controller: DeviceController = None
        self.categorized_devices: Dict[str, List[Dict[str, Any]]] = {}
        self.ten_env: AsyncTenEnv = None
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        self.ten_env = ten_env
        self.config = await HomeAssistantConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")
        if self.config.api_key and self.config.base_url:
            self.device_controller = DeviceController(self.config.base_url, self.config.api_key)
            self.categorized_devices = await self._get_all_devices()
            ten_env.log_info("get all devices finished")

            await super().on_start(ten_env)


    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        await super().on_cmd(ten_env, cmd)

    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        if not self.categorized_devices:
            ten_env.log_info("categorized_devices is empty")
            return []
        
        metadata_list = []
        for domain, category in self.categorized_devices.items():
            if domain == "light":
                metadata = self.light_metadata(domain, category['devices'], ten_env)
                metadata_list.append(metadata)
                ten_env.log_info(f"will register tool: {metadata.name}")
            elif domain == "camera":
                metadata = self.camera_metadata(domain, category['devices'], ten_env)
                metadata_list.append(metadata)
                ten_env.log_info(f"will register tool: {metadata.name}")
            elif domain == "climate":
                metadata = self.climate_metadata(domain, category['devices'], ten_env)
                metadata_list.append(metadata)
                ten_env.log_info(f"will register tool: {metadata.name}")
            elif domain == "cover":
                metadata = self.cover_metadata(domain, category['devices'], ten_env)
                metadata_list.append(metadata)
                ten_env.log_info(f"will register tool: {metadata.name}")
            elif domain == "media_player":
                metadata = self.media_player_metadata(domain, category['devices'], ten_env)
                metadata_list.append(metadata)
                ten_env.log_info(f"will register tool: {metadata.name}")
            elif domain == "fan":
                metadata = self.fan_metadata(domain, category['devices'], ten_env)
                metadata_list.append(metadata)
                ten_env.log_info(f"will register tool: {metadata.name}")

        return metadata_list
    
    def tool_description(self, device_type: str, action: str, devices: List[Dict[str, Any]], ten_env: AsyncTenEnv) -> str:
        system_prompt = f"Control the {device_type} in the user's home based on voice commands."
        user_prompt = action
        device_info = f"Devices:\n"
        
        unique_services = set()
        for device in devices:
            unique_services.update(device['supported_services'])
            device_info += f"{device['name']} ({device['entity_id']})\n"
        
        device_info += f"Supported services: {list(unique_services)}\n"
        user_prompt += device_info

        tool_description = f"{system_prompt}\n{user_prompt}"
        return tool_description
    
    def fan_metadata(self, device_type: str, devices: List[Dict[str, Any]], ten_env: AsyncTenEnv) -> LLMToolMetadata:
        action = f"""
        1. Turn on the {device_type}
        2. Turn off the {device_type}
        """
        tool_description = self.tool_description(device_type, action, devices, ten_env)
        ten_env.log_info(f"fan_tool_name: {FAN_TOOL_NAME}, fan_tool_description: {tool_description}")

        return LLMToolMetadata(
            name=FAN_TOOL_NAME,
            description=tool_description,
            parameters=[
                LLMToolMetadataParameter(
                    name="entity_id",
                    type="string",
                    description="The entity_id of the device to control",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="action",
                    type="string",
                    description="The action to perform on the device, such as turn on, turn off etc.",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="percentage",
                    type="string",
                    description="The speed to set, in percentage",
                    required=False,
                ),
            ],
        )
    
    def cover_metadata(self, device_type: str, devices: List[Dict[str, Any]], ten_env: AsyncTenEnv) -> LLMToolMetadata:
        action = f"""
        1. Open the {device_type}
        2. Close the {device_type}
        """
        tool_description = self.tool_description(device_type, action, devices, ten_env)
        ten_env.log_info(f"cover_tool_name: {COVER_TOOL_NAME}, cover_tool_description: {tool_description}")

        return LLMToolMetadata(
            name=COVER_TOOL_NAME,
            description=tool_description,
            parameters=[
                LLMToolMetadataParameter(
                    name="entity_id",
                    type="string",
                    description="The entity_id of the device to control",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="action",
                    type="string",
                    description="The action to perform on the device, such as turn on, turn off etc.",
                    required=True,
                ),
            ],
        )
    
    def media_player_metadata(self, device_type: str, devices: List[Dict[str, Any]], ten_env: AsyncTenEnv) -> LLMToolMetadata:
        action = f"""
        1. Play the {device_type}
        2. Pause the {device_type}
        3. Stop the {device_type}
        """
        tool_description = self.tool_description(device_type, action, devices, ten_env)
        ten_env.log_info(f"media_player_tool_name: {MEDIA_PLAYER_TOOL_NAME}, media_player_tool_description: {tool_description}")

        return LLMToolMetadata(
            name=MEDIA_PLAYER_TOOL_NAME,
            description=tool_description,
            parameters=[
                LLMToolMetadataParameter(
                    name="entity_id",
                    type="string",
                    description="The entity_id of the device to control",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="action",
                    type="string",
                    description="The action to perform on the device, such as play, pause, stop etc.",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="volume",
                    type="string",
                    description="The volume to set, in percentage",
                    required=False,
                ),
            ],
        )

    def climate_metadata(self, device_type: str, devices: List[Dict[str, Any]], ten_env: AsyncTenEnv) -> LLMToolMetadata:
        action = f"""
        1. Turn on the {device_type}
        2. Turn off the {device_type}
        """
        tool_description = self.tool_description(device_type, action, devices, ten_env)
        ten_env.log_info(f"climate_tool_name: {CLIMATE_TOOL_NAME}, climate_tool_description: {tool_description}")

        return LLMToolMetadata(
            name=CLIMATE_TOOL_NAME,
            description=tool_description,
            parameters=[
                LLMToolMetadataParameter(
                    name="entity_id",
                    type="string",
                    description="The entity_id of the device to control",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="action",
                    type="string",
                    description="The action to perform on the device, such as turn on, turn off etc.",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="temperature",
                    type="number",
                    description="The temperature to set, in degrees Celsius",
                    required=False,
                ),
            ],
        )
    
    def camera_metadata(self, device_type: str, devices: List[Dict[str, Any]], ten_env: AsyncTenEnv) -> LLMToolMetadata:
        action = f"""
        1. Turn on the {device_type}
        2. Turn off the {device_type}
        """
        tool_description = self.tool_description(device_type, action, devices, ten_env)
        ten_env.log_info(f"camera_tool_name: {CAMERA_TOOL_NAME}, camera_tool_description: {tool_description}")

        return LLMToolMetadata(
            name=CAMERA_TOOL_NAME,
            description=tool_description,
            parameters=[
                LLMToolMetadataParameter(
                    name="entity_id",
                    type="string",
                    description="The entity_id of the device to control",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="action",
                    type="string",
                    description="The action to perform on the device, such as turn on, turn off etc.",
                    required=True,
                ),
            ],
        )
    
    def light_metadata(self, device_type: str, devices: List[Dict[str, Any]], ten_env: AsyncTenEnv) -> LLMToolMetadata:
        action = f"""
        1. Turn on the {device_type}
        2. Turn off the {device_type}
        """
        tool_description = self.tool_description(device_type, action, devices, ten_env)

        ten_env.log_info(f"light_tool_name: {LIGHT_TOOL_NAME}, light_tool_description: {tool_description}")
        return LLMToolMetadata(
            name=LIGHT_TOOL_NAME,
            description=tool_description,
            parameters=[
                LLMToolMetadataParameter(
                    name="entity_id",
                    type="string",
                    description="The entity_id of the device to control",
                    required=True,
                ),
                LLMToolMetadataParameter(
                    name="action",
                    type="string",
                    description="The action to perform on the device, such as turn on, turn off etc.",
                    required=True,
                ),
            ],
        )
    
    async def run_tool(self, ten_env: AsyncTenEnv, name: str, args: dict) -> LLMToolResult | None:
        ten_env.log_info(f"run_tool name: {name}, args: {args}")
        entity_id = args.get("entity_id")
        action = args.get("action")
        if name == LIGHT_TOOL_NAME:
            result = await self._control_light(entity_id, action)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        elif name == CAMERA_TOOL_NAME:
            result = await self._control_camera(entity_id, action)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        elif name == CLIMATE_TOOL_NAME:
            temperature = args.get("temperature")
            result = await self._control_climate(entity_id, action, temperature=temperature)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        elif name == COVER_TOOL_NAME:
            result = await self._control_cover(entity_id, action)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        elif name == MEDIA_PLAYER_TOOL_NAME:
            volume = args.get("volume")
            result = await self._control_media_player(entity_id, action, volume=volume)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        elif name == FAN_TOOL_NAME:
            percentage = args.get("percentage")
            result = await self._control_fan(entity_id, action, percentage=percentage)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )
        return None
    
    async def _get_all_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        categorized_devices = await self.device_controller.get_devices_by_type()
        return categorized_devices

    async def _control_device(self, entity_id: str, action: str) -> Any:
        self.ten_env.log_info(f"control_device entity_id: {entity_id}, action: {action}")
        result = await self.device_controller.control_device(entity_id, action)
        return result
    
    async def _control_cover(self, entity_id: str, action: str) -> Any:
        return await self._control_device(entity_id, action)
    
    async def _control_light(self, entity_id: str, action: str) -> Any:
        return await self._control_device(entity_id, action)
    
    async def _control_camera(self, entity_id: str, action: str) -> Any:
        return await self._control_device(entity_id, action)

    async def _control_media_player(self, entity_id: str, action: str, **kwargs) -> Any:
        self.ten_env.log_info(f"control_media_player entity_id: {entity_id}, action: {action}, kwargs: {kwargs}")
        if kwargs.get("volume") is None:
            return await self._control_device(entity_id, action)
        
        return await self.device_controller.control_device(entity_id, action, **kwargs)

    async def _control_climate(self, entity_id: str, action: str, **kwargs) -> Any:
        self.ten_env.log_info(f"control_climate entity_id: {entity_id}, action: {action}, kwargs: {kwargs}")
        if kwargs.get("temperature") is None:
            return await self._control_device(entity_id, action)
        
        return await self.device_controller.control_device(entity_id, action, **kwargs)

    async def _control_fan(self, entity_id: str, action: str, **kwargs) -> Any:
        self.ten_env.log_info(f"control_fan entity_id: {entity_id}, action: {action}, kwargs: {kwargs}")
        if kwargs.get("percentage") is None:
            return await self._control_device(entity_id, action)
        
        return await self.device_controller.control_device(entity_id, action, **kwargs)
