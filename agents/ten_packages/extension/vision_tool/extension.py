#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from abc import abstractmethod
from base64 import b64encode
from ..openai_chatgpt_python.aibase import LLMToolExtension, TenLLMTool, TenLLMToolResult
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
from PIL import Image
from io import BytesIO
from .log import logger


def rgb2base64jpeg(rgb_data, width, height):
    # Convert the RGB image to a PIL Image
    pil_image = Image.frombytes("RGBA", (width, height), bytes(rgb_data))
    pil_image = pil_image.convert("RGB")

    # Resize the image while maintaining its aspect ratio
    pil_image = resize_image_keep_aspect(pil_image, 320)

    # Save the image to a BytesIO object in JPEG format
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")
    # pil_image.save("test.jpg", format="JPEG")

    # Get the byte data of the JPEG image
    jpeg_image_data = buffered.getvalue()

    # Convert the JPEG byte data to a Base64 encoded string
    base64_encoded_image = b64encode(jpeg_image_data).decode("utf-8")

    # Create the data URL
    mime_type = "image/jpeg"
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


class VisionToolExtension(LLMToolExtension):
    image_data = None
    image_width = 0
    image_height = 0

    def on_init(self, ten_env: TenEnv) -> None:
        super().on_init(ten_env)
        logger.info("VisionToolExtension on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        super().on_start(ten_env)
        logger.info("VisionToolExtension on_start")
        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        super().on_stop(ten_env)
        logger.info("VisionToolExtension on_stop")

        # TODO: clean up resources

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        super().on_deinit(ten_env)
        logger.info("VisionToolExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        super().on_cmd(ten_env, cmd)

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        self.image_data = video_frame.get_buf()
        self.image_width = video_frame.get_width()
        self.image_height = video_frame.get_height()

    async def on_register_tool(self, ten_env: TenEnv, data: any) -> TenLLMTool:
        return TenLLMTool.tool_from_json({
            "name": "get_vision_tool",
            "description": "Get the image from camera. Call this whenever you need to understand the input camera image like you have vision capability, for example when user asks 'What can you see?' or 'Can you see me?'",
            "arguments": [],
        })
    
    async def on_run_tool(self, ten_env: TenEnv, data: any) -> TenLLMToolResult:
        if self.image_data is None:
            logger.error("No image data available")
            raise Exception("No image data available")

        base64_image = rgb2base64jpeg(self.image_data, self.image_width, self.image_height)
        result = TenLLMToolResult()
        result.add_value("image", base64_image)
        return result