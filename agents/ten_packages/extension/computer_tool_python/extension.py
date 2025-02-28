#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json
from pydantic import BaseModel
from base64 import b64encode
from io import BytesIO
from typing import Any, Dict
from ten_ai_base.const import CONTENT_DATA_OUT_NAME, DATA_OUT_PROPERTY_END_OF_SEGMENT, DATA_OUT_PROPERTY_TEXT
from ten_ai_base.llm_tool import AsyncLLMToolBaseExtension
from ten_ai_base.types import LLMToolMetadata, LLMToolMetadataParameter, LLMToolResult, LLMToolResultLLMResult
from .openai import OpenAIChatGPT, OpenAIChatGPTConfig

from PIL import Image
from ten import (
    AsyncTenEnv,
    AudioFrame,
    VideoFrame,
    Data
)

OPEN_WEBSITE_TOOL_NAME = "open_website"
OPEN_WEBSITE_TOOL_DESCRIPTION = "Open a website with given site name"

class WebsiteEvent(BaseModel):
    website_name: str
    website_url: str

def rgb2base64jpeg(rgb_data, width, height):
    # Convert the RGB image to a PIL Image
    pil_image = Image.frombytes("RGBA", (width, height), bytes(rgb_data))
    pil_image = pil_image.convert("RGB")

    # Resize the image while maintaining its aspect ratio
    pil_image = resize_image_keep_aspect(pil_image, 1080)

    # Save the image to a BytesIO object in JPEG format
    buffered = BytesIO()
    pil_image.save(buffered, format="png")
    pil_image.save("test.png", format="png")

    # Get the byte data of the JPEG image
    jpeg_image_data = buffered.getvalue()

    # Convert the JPEG byte data to a Base64 encoded string
    base64_encoded_image = b64encode(jpeg_image_data).decode("utf-8")

    # Create the data URL
    mime_type = "image/png"
    base64_url = f"data:{mime_type};base64,{base64_encoded_image}"
    return base64_url


def resize_image_keep_aspect(image, max_size=512):
    """
    Resize an image while maintaining its aspect ratio, ensuring the larger dimension is max_size.
    If both dimensions are smaller than max_size, the image is not resized.

    :param image: A PIL Image object
    :param max_size: The maximum size for the larger dimension (width or height)
    :return: A PIL Image object (resized or original)
    """
    # Get current width and height
    width, height = image.size

    # If both dimensions are already smaller than max_size, return the original image
    if width <= max_size and height <= max_size:
        return image

    # Calculate the aspect ratio
    aspect_ratio = width / height

    # Determine the new dimensions
    if width > height:
        new_width = max_size
        new_height = int(max_size / aspect_ratio)
    else:
        new_height = max_size
        new_width = int(max_size * aspect_ratio)

    # Resize the image with the new dimensions
    resized_image = image.resize((new_width, new_height))

    return resized_image

class ComputerToolExtension(AsyncLLMToolBaseExtension):
    
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.openai_chatgpt = None
        self.config = None 
        self.loop = None
        self.memory = []
        self.max_memory_length = 10
        self.image_data = None
        self.image_width = 0
        self.image_height = 0

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")
        await super().on_init(ten_env)

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        await super().on_start(ten_env)

        # Prepare configuration
        self.config = await OpenAIChatGPTConfig.create_async(ten_env=ten_env)

        # Mandatory properties
        if not self.config.api_key:
            ten_env.log_info(f"API key is missing, exiting on_start")
            return
        
        self.openai_chatgpt = OpenAIChatGPT(ten_env, self.config)   

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")
        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")
        await super().on_deinit(ten_env)

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        audio_frame_name = audio_frame.get_name()
        ten_env.log_debug("on_audio_frame name {}".format(audio_frame_name))

        # TODO: process audio frame
        pass

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

        self.image_data = video_frame.get_buf()
        self.image_width = video_frame.get_width()
        self.image_height = video_frame.get_height()

    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name=OPEN_WEBSITE_TOOL_NAME,
                description=OPEN_WEBSITE_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="name",
                        type="string",
                        description="The name of the website to open",
                        required=True,
                    ),
                    LLMToolMetadataParameter(
                        name="url",
                        type="string",
                        description="The url of the given website, get based on name",
                        required=True,
                    ),
                ]
            ),
        ]

    async def run_tool(self, ten_env: AsyncTenEnv, name: str, args: dict) -> LLMToolResult:
        if name == OPEN_WEBSITE_TOOL_NAME:
            site_name = args.get("name")
            site_url = args.get("url")
            ten_env.log_info(f"open site {site_name} {site_url}")
            result = await self._open_website(site_name, site_url, ten_env)
            return LLMToolResultLLMResult(
                type="llmresult",
                content=json.dumps(result),
            )

    async def _open_website(self, site_name: str, site_url: str, ten_env: AsyncTenEnv) -> Any:
        await self._send_data(ten_env, "browse_website", {"name": site_name, "url": site_url})
        return {"result": "success"}

    async def _send_data(self, ten_env: AsyncTenEnv, action: str, data: Dict[str, Any]):
        try:
            action_data = json.dumps({
                "type": "action",
                "data": {
                    "action": action,
                    "data": data
                }
            })

            output_data = Data.create(CONTENT_DATA_OUT_NAME)
            output_data.set_property_string(
                DATA_OUT_PROPERTY_TEXT,
                action_data
            )
            output_data.set_property_bool(
                DATA_OUT_PROPERTY_END_OF_SEGMENT, True
            )
            await ten_env.send_data(output_data)
        except Exception as err:
            ten_env.log_warn(f"send data error {err}")