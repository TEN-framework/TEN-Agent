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
from ten_ai_base.const import CMD_PROPERTY_RESULT, CMD_TOOL_CALL
from ten_ai_base.helper import (
    AsyncEventEmitter,
    get_property_bool,
    get_property_string,
)
from ten_ai_base import AsyncLLMBaseExtension
from ten_ai_base.types import (
    LLMCallCompletionArgs,
    LLMChatCompletionContentPartParam,
    LLMChatCompletionUserMessageParam,
    LLMChatCompletionMessageParam,
    LLMDataCompletionArgs,
    LLMToolMetadata,
    LLMToolResult,
    LLMToolResultRequery,
)

from .helper import parse_sentences
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


class OpenAIChatGPTExtension(AsyncLLMBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.memory = []
        self.memory_cache = []
        self.config = None
        self.client = None
        self.sentence_fragment = ""
        self.tool_task_future: asyncio.Future | None = None
        self.users_count = 0

    async def on_init(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_init")
        await super().on_init(async_ten_env)

    async def on_start(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_start")
        await super().on_start(async_ten_env)

        self.config = await OpenAIChatGPTConfig.create_async(ten_env=async_ten_env)

        # Mandatory properties
        if not self.config.api_key:
            async_ten_env.log_info("API key is missing, exiting on_start")
            return

        # Create instance
        try:
            self.client = OpenAIChatGPT(async_ten_env, self.config)
            async_ten_env.log_info(
                f"initialized with max_tokens: {self.config.max_tokens}, model: {self.config.model}, vendor: {self.config.vendor}"
            )
        except Exception as err:
            async_ten_env.log_info(f"Failed to initialize OpenAIChatGPT: {err}")

    async def on_stop(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_stop")
        await super().on_stop(async_ten_env)

    async def on_deinit(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_deinit")
        await super().on_deinit(async_ten_env)

    async def on_cmd(self, async_ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        async_ten_env.log_info(f"on_cmd name: {cmd_name}")

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(async_ten_env)
            await async_ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            async_ten_env.log_info("on_cmd sent flush")
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.config.greeting and self.users_count == 1:
                self.send_text_output(async_ten_env, self.config.greeting, True)

            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        else:
            await super().on_cmd(async_ten_env, cmd)

    async def on_data(self, async_ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        async_ten_env.log_debug("on_data name {}".format(data_name))

        # Get the necessary properties
        is_final = get_property_bool(data, "is_final")
        input_text = get_property_string(data, "text")

        if not is_final:
            async_ten_env.log_debug("ignore non-final input")
            return
        if not input_text:
            async_ten_env.log_warn("ignore empty text")
            return

        async_ten_env.log_info(f"OnData input text: [{input_text}]")

        # Start an asynchronous task for handling chat completion
        message = LLMChatCompletionUserMessageParam(role="user", content=input_text)
        await self.queue_input_item(False, messages=[message])

    async def on_tools_update(
        self, async_ten_env: AsyncTenEnv, tool: LLMToolMetadata
    ) -> None:
        return await super().on_tools_update(async_ten_env, tool)

    async def on_call_chat_completion(
        self, async_ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs
    ) -> any:
        kmessages: LLMChatCompletionUserMessageParam = kargs.get("messages", [])

        async_ten_env.log_info(f"on_call_chat_completion: {kmessages}")
        response = await self.client.get_chat_completions(kmessages, None)
        return response.to_json()

    async def on_data_chat_completion(
        self, async_ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs
    ) -> None:
        """Run the chatflow asynchronously."""
        kmessages: Iterable[LLMChatCompletionUserMessageParam] = kargs.get(
            "messages", []
        )

        if len(kmessages) == 0:
            async_ten_env.log_error("No message in data")
            return

        messages = []
        for message in kmessages:
            messages = messages + [self.message_to_dict(message)]

        self.memory_cache = []
        memory = self.memory
        try:
            async_ten_env.log_info(f"for input text: [{messages}] memory: {memory}")
            tools = None
            no_tool = kargs.get("no_tool", False)

            for message in messages:
                if (
                    not isinstance(message.get("content"), str)
                    and message.get("role") == "user"
                ):
                    non_artifact_content = [
                        item
                        for item in message.get("content", [])
                        if item.get("type") == "text"
                    ]
                    non_artifact_message = {
                        "role": message.get("role"),
                        "content": non_artifact_content,
                    }
                    self.memory_cache = self.memory_cache + [
                        non_artifact_message,
                    ]
                else:
                    self.memory_cache = self.memory_cache + [
                        message,
                    ]
            self.memory_cache = self.memory_cache + [{"role": "assistant", "content": ""}]

            tools = None
            if not no_tool and len(self.available_tools) > 0:
                tools = []
                for tool in self.available_tools:
                    tools.append(self._convert_tools_to_dict(tool))
                    async_ten_env.log_info(f"tool: {tool}")

            self.sentence_fragment = ""

            # Create an asyncio.Event to signal when content is finished
            content_finished_event = asyncio.Event()
            # Create a future to track the single tool call task
            self.tool_task_future = None

            # Create an async listener to handle tool calls and content updates
            async def handle_tool_call(tool_call):
                self.tool_task_future = asyncio.get_event_loop().create_future()
                async_ten_env.log_info(f"tool_call: {tool_call}")
                for tool in self.available_tools:
                    if tool_call["function"]["name"] == tool.name:
                        cmd: Cmd = Cmd.create(CMD_TOOL_CALL)
                        cmd.set_property_string("name", tool.name)
                        cmd.set_property_from_json(
                            "arguments", tool_call["function"]["arguments"]
                        )
                        # cmd.set_property_from_json("arguments", json.dumps([]))

                        # Send the command and handle the result through the future
                        [result, _] = await async_ten_env.send_cmd(cmd)
                        if result.get_status_code() == StatusCode.OK:
                            tool_result: LLMToolResult = json.loads(
                                result.get_property_to_json(CMD_PROPERTY_RESULT)
                            )

                            async_ten_env.log_info(f"tool_result: {tool_result}")

                            
                            if tool_result["type"] == "normal":
                                result_content = tool_result["content"]
                                if isinstance(result_content, str):
                                    tool_message = {
                                        "role": "assistant",
                                        "tool_calls": [tool_call],
                                    }
                                    new_message = {
                                        "role": "tool",
                                        "content": result_content,
                                        "tool_call_id": tool_call["id"],
                                    }
                                    await self.queue_input_item(
                                        True, messages=[tool_message, new_message], no_tool=True
                                    )
                                else:
                                    async_ten_env.log_error(
                                        f"Unknown tool result content: {result_content}"
                                    )
                            elif tool_result["type"] == "requery":
                                # self.memory_cache = []
                                self.memory_cache.pop()
                                result_content = tool_result["content"]
                                nonlocal message
                                new_message = {
                                    "role": "user",
                                    "content": self._convert_to_content_parts(
                                        message["content"]
                                    ),
                                }
                                new_message["content"] = new_message[
                                    "content"
                                ] + self._convert_to_content_parts(result_content)
                                await self.queue_input_item(
                                    True, messages=[new_message], no_tool=True
                                )
                            else:
                                async_ten_env.log_error(
                                    f"Unknown tool result type: {tool_result}"
                                )
                        else:
                            async_ten_env.log_error("Tool call failed")
                self.tool_task_future.set_result(None)

            async def handle_content_update(content: str):
                # Append the content to the last assistant message
                for item in reversed(self.memory_cache):
                    if item.get("role") == "assistant":
                        item["content"] = item["content"] + content
                        break
                sentences, self.sentence_fragment = parse_sentences(
                    self.sentence_fragment, content
                )
                for s in sentences:
                    self.send_text_output(async_ten_env, s, False)

            async def handle_content_finished(_: str):
                # Wait for the single tool task to complete (if any)
                if self.tool_task_future:
                    await self.tool_task_future
                content_finished_event.set()

            listener = AsyncEventEmitter()
            listener.on("tool_call", handle_tool_call)
            listener.on("content_update", handle_content_update)
            listener.on("content_finished", handle_content_finished)

            # Make an async API call to get chat completions
            await self.client.get_chat_completions_stream(
                memory + messages, tools, listener
            )

            # Wait for the content to be finished
            await content_finished_event.wait()

            async_ten_env.log_info(
                f"Chat completion finished for input text: {messages}"
            )
        except asyncio.CancelledError:
            async_ten_env.log_info(f"Task cancelled: {messages}")
        except Exception:
            async_ten_env.log_error(
                f"Error in chat_completion: {traceback.format_exc()} for input text: {messages}"
            )
        finally:
            self.send_text_output(async_ten_env, "", True)
            # always append the memory
            for m in self.memory_cache:
                self._append_memory(m)

    def _convert_to_content_parts(
        self, content: Iterable[LLMChatCompletionContentPartParam]
    ):
        content_parts = []

        if isinstance(content, str):
            content_parts.append({"type": "text", "text": content})
        else:
            for part in content:
                content_parts.append(part)
        return content_parts

    def _convert_tools_to_dict(self, tool: LLMToolMetadata):
        json_dict = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
            "strict": True,
        }

        for param in tool.parameters:
            json_dict["function"]["parameters"]["properties"][param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                json_dict["function"]["parameters"]["required"].append(param.name)

        return json_dict

    def message_to_dict(self, message: LLMChatCompletionMessageParam):
        if message.get("content") is not None:
            if isinstance(message["content"], str):
                message["content"] = str(message["content"])
            else:
                message["content"] = list(message["content"])
        return message

    def _append_memory(self, message: str):
        if len(self.memory) > self.config.max_memory_length:
            self.memory.pop(0)
        self.memory.append(message)
