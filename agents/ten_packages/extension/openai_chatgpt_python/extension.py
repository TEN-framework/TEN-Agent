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
from typing import Iterable

from ten.async_ten_env import AsyncTenEnv
from ten.ten_env import TenEnv
from ten_ai_base.const import CMD_PROPERTY_RESULT, CMD_TOOL_CALL
from ten_ai_base.helper import AsyncEventEmitter, get_properties_int, get_properties_string, get_properties_float, get_property_bool, get_property_int, get_property_string
from ten_ai_base.llm import AsyncLLMBaseExtension
from ten_ai_base.types import LLMCallCompletionArgs, LLMChatCompletionContentPartParam, LLMChatCompletionUserMessageParam, LLMChatCompletionMessageParam, LLMDataCompletionArgs, LLMToolMetadata, LLMToolResult

from .helper import parse_sentences, rgb2base64jpeg
from .openai import OpenAIChatGPT, OpenAIChatGPTConfig
from ten import (
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)

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
PROPERTY_PROXY_URL = "proxy_url"  # Optional
PROPERTY_MAX_MEMORY_LENGTH = "max_memory_length"  # Optional


class OpenAIChatGPTExtension(AsyncLLMBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.memory = []
        self.memory_cache = []
        self.max_memory_length = 10
        self.openai_chatgpt = None
        self.sentence_fragment = ""
        self.toolcall_future = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_init")
        await super().on_init(ten_env)

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
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

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")
        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_deinit")
        await super().on_deinit(ten_env)

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_info(f"on_cmd name: {cmd_name}")

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(ten_env)
            await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            ten_env.log_info("on_cmd sent flush")
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.greeting and self.users_count == 1:
                self.send_text_output(ten_env, self.greeting, True)

            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            ten_env.return_result(cmd_result, cmd)
        else:
            await super().on_cmd(ten_env, cmd)

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

        ten_env.log_info(f"OnData input text: [{input_text}]")

        # Start an asynchronous task for handling chat completion
        message = LLMChatCompletionUserMessageParam(
            role="user", content=input_text)
        await self.queue_input_item(False, messages=[message])

    async def on_tools_update(self, ten_env: TenEnv, tool: LLMToolMetadata) -> None:
        return await super().on_tools_update(ten_env, tool)

    async def on_call_chat_completion(self, ten_env: TenEnv, **kargs: LLMCallCompletionArgs) -> any:
        kmessages: LLMChatCompletionUserMessageParam = kargs.get(
            "messages", [])

        ten_env.log_info(f"on_call_chat_completion: {kmessages}")
        response = await self.openai_chatgpt.get_chat_completions(
            kmessages, None)
        return response.to_json()

    async def on_data_chat_completion(self, ten_env: TenEnv, **kargs: LLMDataCompletionArgs) -> None:
        """Run the chatflow asynchronously."""
        kmessage: LLMChatCompletionUserMessageParam = kargs.get("messages", [])[
            0]

        if not kmessage:
            ten_env.log_error("No message in data")
            return

        message = self.message_to_dict(kmessage)

        self.memory_cache = []
        memory = self.memory
        try:
            ten_env.log_info(f"for input text: [{message}] memory: {memory}")
            tools = None
            no_tool = kargs.get("no_tool", False)

            if not isinstance(message.get("content"), str) and message.get("role") == "user":
                non_artifact_content = [item for item in message.get(
                    "content", []) if item.get("type") == "text"]
                non_artifact_message = {"role": message.get(
                    "role"), "content": non_artifact_content}
                self.memory_cache = self.memory_cache + \
                    [non_artifact_message, {
                        "role": "assistant", "content": ""}]
            else:
                self.memory_cache = self.memory_cache + \
                    [message, {"role": "assistant", "content": ""}]

            tools = [] if not no_tool and len(
                self.available_tools) > 0 else None
            for tool in self.available_tools:
                tools.append(self._convert_tools_to_dict(tool))

            self.sentence_fragment = ""

            # Create an asyncio.Event to signal when content is finished
            content_finished_event = asyncio.Event()
            # Create a future to track the single tool call task
            self.tool_task_future = None

            # Create an async listener to handle tool calls and content updates
            async def handle_tool_call(tool_call):
                self.tool_task_future = asyncio.get_event_loop().create_future()
                ten_env.log_info(f"tool_call: {tool_call}")
                for tool in self.available_tools:
                    if tool_call["function"]["name"] == tool.name:
                        cmd: Cmd = Cmd.create(CMD_TOOL_CALL)
                        cmd.set_property_string("name", tool.name)
                        cmd.set_property_from_json(
                            "arguments", tool_call["function"]["arguments"])
                        # cmd.set_property_from_json("arguments", json.dumps([]))

                        # Send the command and handle the result through the future
                        result: CmdResult = await ten_env.send_cmd(cmd)
                        if result.get_status_code() == StatusCode.OK:
                            tool_result: LLMToolResult = json.loads(
                                result.get_property_to_json(CMD_PROPERTY_RESULT))

                            ten_env.log_info(f"tool_result: {tool_result}")
                            # self.memory_cache = []
                            self.memory_cache.pop()
                            result_content = tool_result["content"]
                            nonlocal message
                            new_message = {
                                "role": "user",
                                "content": self._convert_to_content_parts(message["content"])
                            }
                            new_message["content"] = new_message["content"] + \
                                self._convert_to_content_parts(result_content)
                            await self.queue_input_item(True, messages=[new_message], no_tool=True)
                        else:
                            ten_env.log_error(f"Tool call failed")
                self.tool_task_future.set_result(None)

            async def handle_content_update(content: str):
                # Append the content to the last assistant message
                for item in reversed(self.memory_cache):
                    if item.get('role') == 'assistant':
                        item['content'] = item['content'] + content
                        break
                sentences, self.sentence_fragment = parse_sentences(
                    self.sentence_fragment, content)
                for s in sentences:
                    self.send_text_output(ten_env, s, False)

            async def handle_content_finished(full_content: str):
                # Wait for the single tool task to complete (if any)
                if self.tool_task_future:
                    await self.tool_task_future
                content_finished_event.set()

            listener = AsyncEventEmitter()
            listener.on("tool_call", handle_tool_call)
            listener.on("content_update", handle_content_update)
            listener.on("content_finished", handle_content_finished)

            # Make an async API call to get chat completions
            await self.openai_chatgpt.get_chat_completions_stream(memory + [message], tools, listener)

            # Wait for the content to be finished
            await content_finished_event.wait()

            ten_env.log_info(
                f"Chat completion finished for input text: {message}")
        except asyncio.CancelledError:
            ten_env.log_info(f"Task cancelled: {message}")
        except Exception as e:
            ten_env.log_error(
                f"Error in chat_completion: {traceback.format_exc()} for input text: {message}")
        finally:
            self.send_text_output(ten_env, "", True)
            # always append the memory
            for m in self.memory_cache:
                self._append_memory(m)

    def _convert_to_content_parts(self, content: Iterable[LLMChatCompletionContentPartParam]):
        content_parts = []

        if isinstance(content, str):
            content_parts.append({
                "type": "text",
                "text": content
            })
        else:
            for part in content:
                content_parts.append(part)
        return content_parts

    def _convert_tools_to_dict(self, tool: LLMToolMetadata):
        json = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False
                },
            },
            "strict": True
        }

        for param in tool.parameters:
            json["function"]["parameters"]["properties"][param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.required:
                json["function"]["parameters"]["required"].append(param.name)

        return json

    def message_to_dict(self, message: LLMChatCompletionMessageParam):
        if isinstance(message["content"], str):
            message["content"] = str(message["content"])
        else:
            message["content"] = list(message["content"])
        return message

    def _append_memory(self, message: str):
        if len(self.memory) > self.max_memory_length:
            self.memory.pop(0)
        self.memory.append(message)
