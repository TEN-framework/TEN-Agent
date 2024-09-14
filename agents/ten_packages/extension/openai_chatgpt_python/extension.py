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

from .helper import AsyncEventEmitter, AsyncQueue, get_current_time, get_property_bool, get_property_float, get_property_int, get_property_string, parse_sentences, rgb2base64jpeg
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


TASK_TYPE_CHAT_COMPLETION = "chat_completion"
TASK_TYPE_CHAT_COMPLETION_WITH_VISION = "chat_completion_with_vision"

class OpenAIChatGPTExtension(Extension):
    memory = []
    max_memory_length = 10
    openai_chatgpt = None
    enable_tools = False
    image_data = None
    image_width = 0
    image_height = 0
    checking_vision_text_items = []
    loop = None
    sentence_fragment = ""

    # Create the queue for message processing
    queue = AsyncQueue()

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

        self.loop.create_task(self._process_queue(ten_env))

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
            asyncio.run_coroutine_threadsafe(self._flush_queue(), self.loop)
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
        asyncio.run_coroutine_threadsafe(self.queue.put([TASK_TYPE_CHAT_COMPLETION, input_text]), self.loop)

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # logger.info(f"OpenAIChatGPTExtension on_video_frame {frame.get_width()} {frame.get_height()}")
        self.image_data = video_frame.get_buf()
        self.image_width = video_frame.get_width()
        self.image_height = video_frame.get_height()
        return

    async def _process_queue(self, ten_env: TenEnv):
        """Asynchronously process queue items one by one."""
        while True:
            # Wait for an item to be available in the queue
            [task_type, message] = await self.queue.get()
            try:
                # Create a new task for the new message
                self.current_task = asyncio.create_task(self._run_chatflow(ten_env, task_type, message, self.memory))
                await self.current_task  # Wait for the current task to finish or be cancelled
            except asyncio.CancelledError:
                logger.info(f"Task cancelled: {message}")

    async def _flush_queue(self):
        """Flushes the self.queue and cancels the current task."""
        # Flush the queue using the new flush method
        await self.queue.flush()

        # Cancel the current task if one is running
        if self.current_task:
            logger.info("Cancelling the current task during flush.")
            self.current_task.cancel()

    async def _run_chatflow(self, ten_env: TenEnv, task_type:str, input_text: str, memory):
        """Run the chatflow asynchronously."""
        memory_cache = []
        try:
            logger.info(f"for input text: [{input_text}] memory: {memory}")
            message = None
            tools = None

            # Prepare the message and tools based on the task type
            if task_type == TASK_TYPE_CHAT_COMPLETION:
                message = {"role": "user", "content": input_text}
                memory_cache = memory_cache + [message, {"role": "assistant", "content": ""}]
                tools = self.available_tools if self.enable_tools else None
            elif task_type == TASK_TYPE_CHAT_COMPLETION_WITH_VISION:
                message = {"role": "user", "content": input_text}
                memory_cache = memory_cache + [message, {"role": "assistant", "content": ""}]
                tools = self.available_tools if self.enable_tools else None
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


            self.sentence_fragment = ""

            # Create an asyncio.Event to signal when content is finished
            content_finished_event = asyncio.Event()

            # Create an async listener to handle tool calls and content updates
            async def handle_tool_call(tool_call):
                logger.info(f"tool_call: {tool_call}")
                if tool_call.function.name == "get_vision_image":
                    self.queue._queue.appendleft([TASK_TYPE_CHAT_COMPLETION_WITH_VISION, input_text])

            async def handle_content_update(content:str):
                # Append the content to the last assistant message
                for item in reversed(memory_cache):
                    if item.get('role') == 'assistant':
                        item['content'] = item['content'] + content
                        break
                sentences, self.sentence_fragment = parse_sentences(self.sentence_fragment, content)
                for s in sentences:
                    self._send_data(ten_env, s, False)

            async def handle_content_finished(full_content:str):
                content_finished_event.set()

            listener = AsyncEventEmitter()
            listener.on("tool_call", handle_tool_call)
            listener.on("content_update", handle_content_update)
            listener.on("content_finished", handle_content_finished)

            # Make an async API call to get chat completions
            await self.openai_chatgpt.get_chat_completions_stream(memory + [message], tools, listener)

            # Wait for the content to be finished
            await content_finished_event.wait()
        except asyncio.CancelledError:
            logger.info(f"Task cancelled: {input_text}")
        except Exception as e:
            logger.error(f"Error in chat_completion: {traceback.format_exc()} for input text: {input_text}")
        finally:
            self._send_data(ten_env, "", True)
            # always append the memory
            for m in memory_cache:
                self._append_memory(m)

    def _append_memory(self, message:str):
        if len(self.memory) > self.max_memory_length:
            self.memory.pop(0)
        self.memory.append(message)

    def _send_data(self, ten_env: TenEnv, sentence: str, end_of_segment: bool):
        try:
            output_data = Data.create("text_data")
            output_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, sentence)
            output_data.set_property_bool(
                DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, end_of_segment
            )
            ten_env.send_data(output_data)
            logger.info(
                f"{'end of segment ' if end_of_segment else ''}sent sentence [{sentence}]"
            )
        except Exception as err:
            logger.info(
                f"send sentence [{sentence}] failed, err: {err}"
            )