#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
import json
import random
import threading
import traceback

from .helper import get_current_time, get_property_bool, get_property_float, get_property_int, get_property_string, parse_sentence, rgb2base64jpeg
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

async def test_task():
    logger.info("Test task is running")

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
    loop = None

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

        self.loop = asyncio.new_event_loop()
        def start_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        threading.Thread(target=start_loop, args=[]).start()

        # Prepare configuration
        openai_chatgpt_config = OpenAIChatGPTConfig.default_config()

        # Mandatory properties
        openai_chatgpt_config.base_url = get_property_string(ten_env, PROPERTY_BASE_URL) or openai_chatgpt_config.base_url
        openai_chatgpt_config.api_key = get_property_string(ten_env, PROPERTY_API_KEY)
        if not openai_chatgpt_config.api_key:
            logger.info(f"API key is missing, exiting on_start")
            return

        # Optional properties
        openai_chatgpt_config.model = get_property_string(ten_env, PROPERTY_MODEL) or openai_chatgpt_config.model
        openai_chatgpt_config.prompt = get_property_string(ten_env, PROPERTY_PROMPT) or openai_chatgpt_config.prompt
        openai_chatgpt_config.frequency_penalty = get_property_float(ten_env, PROPERTY_FREQUENCY_PENALTY) or openai_chatgpt_config.frequency_penalty
        openai_chatgpt_config.presence_penalty = get_property_float(ten_env, PROPERTY_PRESENCE_PENALTY) or openai_chatgpt_config.presence_penalty
        openai_chatgpt_config.temperature = get_property_float(ten_env, PROPERTY_TEMPERATURE) or openai_chatgpt_config.temperature
        openai_chatgpt_config.top_p = get_property_float(ten_env, PROPERTY_TOP_P) or openai_chatgpt_config.top_p
        openai_chatgpt_config.max_tokens = get_property_int(ten_env, PROPERTY_MAX_TOKENS) or openai_chatgpt_config.max_tokens
        openai_chatgpt_config.proxy_url = get_property_string(ten_env, PROPERTY_PROXY_URL) or openai_chatgpt_config.proxy_url

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

        # Create instance
        try:
            self.openai_chatgpt = OpenAIChatGPT(openai_chatgpt_config)
            logger.info(f"initialized with max_tokens: {openai_chatgpt_config.max_tokens}, model: {openai_chatgpt_config.model}")
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
        # Get the necessary properties
        is_final = get_property_bool(data, DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
        input_text = get_property_string(data, DATA_IN_TEXT_DATA_PROPERTY_TEXT)

        if not is_final:
            logger.info("ignore non-final input")
            return
        if not input_text:
            logger.info("ignore empty text")
            return

        logger.info(f"OnData input text: [{input_text}]")

        # Start an asynchronous task for handling chat completion
        start_time = get_current_time()
        asyncio.run_coroutine_threadsafe(self.__async_chat_completion(ten_env, start_time, input_text, self.memory), self.loop)

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # logger.info(f"OpenAIChatGPTExtension on_video_frame {frame.get_width()} {frame.get_height()}")
        self.image_data = video_frame.get_buf()
        self.image_width = video_frame.get_width()
        self.image_height = video_frame.get_height()
        return

    def __append_memory(self, message:str):
        if len(self.memory) > self.max_memory_length:
            self.memory.pop(0)
        self.memory.append(message)

    def __send_data(self, ten_env: TenEnv, sentence: str, end_of_segment: bool, input_text: str):
        try:
            output_data = Data.create("text_data")
            output_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, sentence)
            output_data.set_property_bool(
                DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, end_of_segment
            )
            ten_env.send_data(output_data)
            logger.info(
                f"for input text: [{input_text}] {'end of segment ' if end_of_segment else ''}sent sentence [{sentence}]"
            )
        except Exception as err:
            logger.info(
                f"for input text: [{input_text}] send sentence [{sentence}] failed, err: {err}"
            )

    async def __async_chat_completion(self, ten: TenEnv, start_time, input_text, memory):
        """Async chat completion task to be run from on_data."""
        try:
            logger.info(f"for input text: [{input_text}] memory: {memory}")
            message = {"role": "user", "content": input_text}
            tools = self.available_tools if self.enable_tools else None

            # Make an async API call to get chat completions
            resp = await self.openai_chatgpt.get_chat_completions_stream(memory + [message], tools)
            if not resp:
                logger.error(f"get_chat_completions_stream Response is None: {input_text}")
                return

            # Process the completions asynchronously
            await self.__process_completions(resp, ten, start_time, input_text, memory)
        except Exception as e:
            logger.error(f"Error in chat_completion: {traceback.format_exc()} for input text: {input_text}")

    async def __async_chat_completion_with_vision(self, ten: TenEnv, start_time, input_text, memory):
        """Handles chat completion when a vision-based tool call is invoked."""
        try:
            logger.info(f"for input text: [{input_text}] memory: {memory}")
            
            # Prepare the message with vision content
            message = {"role": "user", "content": input_text}
            if self.image_data is not None:
                url = rgb2base64jpeg(self.image_data, self.image_width, self.image_height)
                message = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": input_text},
                        {"type": "image_url", "image_url": {"url": url}},
                    ],
                }
                logger.info(f"msg with vision data: {message}")

            # Asynchronous request to OpenAI for chat completions with vision
            resp = await self.openai_chatgpt.get_chat_completions_stream(memory + [message])
            if not resp:
                logger.error(f"get_chat_completions_stream Response is None for input text: {input_text}")
                return

            # Process completions asynchronously
            await self.__process_completions(resp, ten, start_time, input_text, memory)

        except Exception as e:
            logger.error(f"Error in chat_completion_with_vision: {str(e)} for input text: {input_text}")


    async def __process_completions(self, chat_completions, ten, start_time, input_text, memory):
        """Processes completions and sends them asynchronously."""
        full_content = ""
        first_sentence_sent = False

        async for chat_completion in chat_completions:
            if start_time < self.outdate_ts:
                logger.info(f"recv interrupt for input text: [{input_text}]")
                break

            content = chat_completion.choices[0].delta.content if len(chat_completion.choices) > 0 and chat_completion.choices[0].delta.content else ""

            if chat_completion.choices[0].delta.tool_calls:
                for tool_call in chat_completion.choices[0].delta.tool_calls:
                    logger.info(f"tool_call: {tool_call}")
                    if tool_call.function.name == "get_vision_image":
                        if not full_content and self.checking_vision_text_items:
                            await self.__send_data(ten, random.choice(self.checking_vision_text_items), True, input_text)
                        await self.__async_chat_completion_with_vision(ten, start_time, input_text, memory)
                        return

            full_content += content

            sentence, content, sentence_is_final = "", content, False
            while sentence_is_final:
                sentence, content, sentence_is_final = parse_sentence(sentence, content)
                logger.info(f"recv for input text: [{input_text}] got sentence: [{sentence}]")
                await self.__send_data(ten, sentence, False, input_text)
                if not first_sentence_sent:
                    first_sentence_sent = True
                    logger.info(f"first sentence latency: {get_current_time() - start_time}ms")

        self.__append_memory({"role": "user", "content": input_text})
        self.__append_memory({"role": "assistant", "content": full_content})
        self.__send_data(ten, full_content, True, input_text)