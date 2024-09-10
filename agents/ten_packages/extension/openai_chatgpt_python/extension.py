#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from base64 import b64encode
from datetime import datetime
from io import BytesIO
import json

from .helper import get_property_bool, get_property_float, get_property_int, get_property_string
from .openai import OpenAIChatGPT, OpenAIChatGPTConfig
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
from .log import logger

CMD_IN_FLUSH = "flush"
CMD_OUT_FLUSH = "flush"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"

PROPERTY_BASE_URL = "base_url"  # Optional
PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_MODEL = "model"  # Optional
PROPERTY_PROMPT = "prompt"  # Optional
PROPERTY_FREQUENCY_PENALTY = "frequency_penalty"  # Optional
PROPERTY_PRESENCE_PENALTY = "presence_penalty"  # Optional
PROPERTY_TEMPERATURE = "temperature"  # Optional
PROPERTY_TOP_P = "top_p"  # Optional
PROPERTY_MAX_TOKENS = "max_tokens"  # Optional
PROPERTY_GREETING = "greeting"  # Optional
PROPERTY_ENABLE_TOOLS = "enable_tools"  # Optional
PROPERTY_PROXY_URL = "proxy_url"  # Optional
PROPERTY_MAX_MEMORY_LENGTH = "max_memory_length"  # Optional
PROPERTY_CHECKING_VISION_TEXT_ITEMS = "checking_vision_text_items"  # Optional

def get_current_time():
    # Get the current time
    start_time = datetime.now()
    # Get the number of microseconds since the Unix epoch
    unix_microseconds = int(start_time.timestamp() * 1_000_000)
    return unix_microseconds


def is_punctuation(char):
    if char in [",", "，", ".", "。", "?", "？", "!", "！"]:
        return True
    return False


def parse_sentence(sentence, content):
    remain = ""
    found_punc = False

    for char in content:
        if not found_punc:
            sentence += char
        else:
            remain += char

        if not found_punc and is_punctuation(char):
            found_punc = True

    return sentence, remain, found_punc


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


class OpenAIChatGPTExtension(Extension):
    memory = []
    max_memory_length = 10
    outdate_ts = 0
    openai_chatgpt = None
    enable_tools = False
    image_data = None
    image_width = 0
    image_height = 0
    checking_vision_text_items = []

    available_tools = [
        {
            "type": "function",
            "function": {
                # ensure you use gpt-4o or later model if you need image recognition, gpt-4o-mini does not work quite well in this case
                "name": "get_vision_image",
                "description": "Get the image from camera. Call this whenever you need to understand the input camera image like you have vision capability, for example when user asks 'What can you see?' or 'Can you see me?'",
            },
            "strict": True,
        }
    ]

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("on_start")

        # Prepare configuration
        openai_chatgpt_config = OpenAIChatGPTConfig.default_config()

        # Mandatory properties
        openai_chatgpt_config.base_url = get_property_string(ten_env, PROPERTY_BASE_URL)
        openai_chatgpt_config.api_key = get_property_string(ten_env, PROPERTY_API_KEY)
        if not openai_chatgpt_config.api_key:
            logger.info(f"API key is missing, exiting on_start")
            return

        # Optional properties
        openai_chatgpt_config.model = get_property_string(ten_env, PROPERTY_MODEL)
        openai_chatgpt_config.prompt = get_property_string(ten_env, PROPERTY_PROMPT)
        openai_chatgpt_config.frequency_penalty = get_property_float(ten_env, PROPERTY_FREQUENCY_PENALTY)
        openai_chatgpt_config.presence_penalty = get_property_float(ten_env, PROPERTY_PRESENCE_PENALTY)
        openai_chatgpt_config.temperature = get_property_float(ten_env, PROPERTY_TEMPERATURE)
        openai_chatgpt_config.top_p = get_property_float(ten_env, PROPERTY_TOP_P)
        openai_chatgpt_config.max_tokens = get_property_int(ten_env, PROPERTY_MAX_TOKENS)
        openai_chatgpt_config.proxy_url = get_property_string(ten_env, PROPERTY_PROXY_URL)

        # Properties that don't affect openai_chatgpt_config
        greeting = get_property_string(ten_env, PROPERTY_GREETING)
        self.enable_tools = get_property_bool(ten_env, PROPERTY_ENABLE_TOOLS)
        self.max_memory_length = get_property_int(ten_env, PROPERTY_MAX_MEMORY_LENGTH)
        checking_vision_text_items_str = get_property_string(ten_env, PROPERTY_CHECKING_VISION_TEXT_ITEMS)
        if checking_vision_text_items_str:
            try:
                self.checking_vision_text_items = json.loads(checking_vision_text_items_str)
            except Exception as err:
                logger.info(f"Error parsing {PROPERTY_CHECKING_VISION_TEXT_ITEMS}: {err}")

        # Create openaiChatGPT instance
        try:
            self.openai_chatgpt = OpenAIChatGPT(openai_chatgpt_config)
            logger.info(f"OpenAIChatGPT initialized with max_tokens: {openai_chatgpt_config.max_tokens}, model: {openai_chatgpt_config.model}")
        except Exception as err:
            logger.info(f"Failed to initialize OpenAIChatGPT: {err}")

        # Send greeting if available
        if greeting:
            try:
                output_data = Data.create("text_data")
                output_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, greeting)
                output_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True)
                ten_env.send_data(output_data)
                logger.info(f"Greeting [{greeting}] sent")
            except Exception as err:
                logger.info(f"Failed to send greeting [{greeting}]: {err}")
        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("on_stop")

        # TODO: clean up resources

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        logger.info(f"on_cmd json: {cmd.to_json()}")

        cmd_name = cmd.get_name()

        if cmd_name == CMD_IN_FLUSH:
            self.outdate_ts = get_current_time()
            ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH), None)
            logger.info("on_cmd sent flush")
            status_code, detail = StatusCode.OK, "success"
        else:
            logger.info(f"on_cmd unknown cmd: {cmd_name}")
            status_code, detail = StatusCode.ERROR, "unknown cmd"
        
        cmd_result = CmdResult.create(status_code)
        cmd_result.set_property_string("detail", detail)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        # TODO: process data
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # logger.info(f"OpenAIChatGPTExtension on_video_frame {frame.get_width()} {frame.get_height()}")
        self.image_data = video_frame.get_buf()
        self.image_width = video_frame.get_width()
        self.image_height = video_frame.get_height()
        return
        pass

    def __append_memory(self, message):
        if len(self.memory) > self.max_memory_length:
            self.memory.pop(0)
        self.memory.append(message)

    def __send_data(self, ten, sentence, end_of_segment, input_text):
        try:
            output_data = Data.create("text_data")
            output_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, sentence)
            output_data.set_property_bool(
                DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, end_of_segment
            )
            ten.send_data(output_data)
            logger.info(
                f"for input text: [{input_text}] {'end of segment ' if end_of_segment else ''}sent sentence [{sentence}]"
            )
        except Exception as err:
            logger.info(
                f"for input text: [{input_text}] send sentence [{sentence}] failed, err: {err}"
            )
