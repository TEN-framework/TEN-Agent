#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
import json
import traceback

from ten.async_ten_env import AsyncTenEnv
from ..ten_llm_base.helper import AsyncEventEmitter, AsyncQueue, get_properties_int, get_properties_string, get_properties_float, get_property_bool, get_property_int, get_property_string

from .helper import parse_sentences, rgb2base64jpeg
from .openai import OpenAIChatGPT, OpenAIChatGPTConfig
from ten import (
    AudioFrame,
    VideoFrame,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ..ten_llm_base.extension import TenLLMAudioCompletionArgs, TenLLMBaseExtension, TenLLMDataType, TenLLMTextCompletionArgs

from .log import logger

CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
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


class OpenAIChatGPTExtension(TenLLMBaseExtension):
    memory = []
    max_memory_length = 10
    openai_chatgpt = None
    image_data = None
    image_width = 0
    image_height = 0
    sentence_fragment = ""

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

    async def on_init(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_init")
        await super().on_init(ten_env)
        ten_env.on_init_done()

    async def on_start(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_start")
        await super().on_start(ten_env)

        # Prepare configuration
        openai_chatgpt_config = OpenAIChatGPTConfig.default_config()

        # Mandatory properties
        get_properties_string(ten_env, [PROPERTY_BASE_URL, PROPERTY_API_KEY], lambda name, value: setattr(
            openai_chatgpt_config, name, value or getattr(openai_chatgpt_config, name)))
        if not openai_chatgpt_config.api_key:
            ten_env.log_info(f"API key is missing, exiting on_start")
            return

        # Optional properties
        get_properties_string(ten_env, [PROPERTY_MODEL, PROPERTY_PROMPT, PROPERTY_PROXY_URL], lambda name, value: setattr(
            openai_chatgpt_config, name, value or getattr(openai_chatgpt_config, name)))
        get_properties_float(ten_env, [PROPERTY_FREQUENCY_PENALTY, PROPERTY_PRESENCE_PENALTY, PROPERTY_TEMPERATURE, PROPERTY_TOP_P], lambda name, value: setattr(
            openai_chatgpt_config, name, value or getattr(openai_chatgpt_config, name)))
        get_properties_int(ten_env, [PROPERTY_MAX_TOKENS], lambda name, value: setattr(
            openai_chatgpt_config, name, value or getattr(openai_chatgpt_config, name)))

        # Properties that don't affect openai_chatgpt_config
        self.greeting = get_property_string(ten_env, PROPERTY_GREETING)
        self.max_memory_length = get_property_int(
            ten_env, PROPERTY_MAX_MEMORY_LENGTH)
        self.users_count = 0

        # Create instance
        try:
            self.openai_chatgpt = OpenAIChatGPT(openai_chatgpt_config)
            ten_env.log_info(
                f"initialized with max_tokens: {openai_chatgpt_config.max_tokens}, model: {openai_chatgpt_config.model}")
        except Exception as err:
            ten_env.log_info(f"Failed to initialize OpenAIChatGPT: {err}")

        ten_env.on_start_done()

    async def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_stop")
        await super().on_stop(ten_env)
        ten_env.on_stop_done()

    async def on_deinit(self, ten_env: TenEnv) -> None:
        ten_env.log_info("on_deinit")
        await super().on_deinit(ten_env)
        ten_env.on_deinit_done()

    async def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_info(f"on_cmd name: {cmd_name}")

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(ten_env)
            ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH), None)
            ten_env.log_info("on_cmd sent flush")
            status_code, detail = StatusCode.OK, "success"
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.greeting and self.users_count == 1:
                try:
                    output_data = Data.create("text_data")
                    output_data.set_property_string(
                        DATA_OUT_TEXT_DATA_PROPERTY_TEXT, self.greeting)
                    output_data.set_property_bool(
                        DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True)
                    ten_env.send_data(output_data)
                    ten_env.log_info(f"Greeting [{self.greeting}] sent")
                except Exception as err:
                    ten_env.log_info(
                        f"Failed to send greeting [{self.greeting}]: {err}")

            status_code, detail = StatusCode.OK, "success"
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
            status_code, detail = StatusCode.OK, "success"
        else:
            ten_env.log_info(f"on_cmd unknown cmd: {cmd_name}")
            status_code, detail = StatusCode.ERROR, "unknown cmd"

        cmd_result = CmdResult.create(status_code)
        cmd_result.set_property_string("detail", detail)
        ten_env.return_result(cmd_result, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        # Get the necessary properties
        is_final = get_property_bool(data, "is_final")
        input_text = get_property_string(data, "text")

        if not is_final:
            ten_env.log_debug("ignore non-final input")
            return
        if not input_text:
            ten_env.log_warn("ignore empty text")
            return

        ten_env.log_debug(f"OnData input text: [{input_text}]")

        # Start an asynchronous task for handling chat completion
        await self.queue_input_item(TenLLMDataType.TEXT, [{
            "type": "text",
            "text": input_text,
        }])

    async def on_audio_completion(self, ten_env: TenEnv, message: any, **kargs: TenLLMAudioCompletionArgs) -> None:
        return await super().on_audio_completion(ten_env, message, **kargs)

    async def on_text_completion(self, ten_env: TenEnv, content: any, **kargs: TenLLMTextCompletionArgs) -> None:
        """Run the chatflow asynchronously."""
        memory_cache = []
        memory = self.memory
        try:
            ten_env.log_info(f"for input text: [{content}] memory: {memory}")
            message = None
            tools = None
            no_tool = kargs.get("no_tool", False)

            message = {"role": "user", "content": content}
            non_artifact_content = [item for item in content if item.get("type") == "text"]
            non_artifact_message = {"role": "user", "content": non_artifact_content}
            memory_cache = memory_cache + [non_artifact_message, {"role": "assistant", "content": ""}]
            tools = self.available_tools if not no_tool else None

            self.sentence_fragment = ""

            # Create an asyncio.Event to signal when content is finished
            content_finished_event = asyncio.Event()

            # Create an async listener to handle tool calls and content updates
            async def handle_tool_call(tool_call):
                ten_env.log_info(f"tool_call: {tool_call}")
                if tool_call.function.name == "get_vision_image":
                    # Append the vision image to the last assistant message
                    pass

            async def handle_content_update(content: str):
                # Append the content to the last assistant message
                for item in reversed(memory_cache):
                    if item.get('role') == 'assistant':
                        item['content'] = item['content'] + content
                        break
                sentences, self.sentence_fragment = parse_sentences(
                    self.sentence_fragment, content)
                for s in sentences:
                    self.send_text_output(ten_env, s, False)

            async def handle_content_finished(full_content: str):
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
            ten_env.log_info(f"Task cancelled: {content}")
        except Exception as e:
            logger.error(
                f"Error in chat_completion: {traceback.format_exc()} for input text: {content}")
        finally:
            self.send_text_output(ten_env, "", True)
            # always append the memory
            for m in memory_cache:
                self._append_memory(m)

    def _append_memory(self, message: str):
        if len(self.memory) > self.max_memory_length:
            self.memory.pop(0)
        self.memory.append(message)
