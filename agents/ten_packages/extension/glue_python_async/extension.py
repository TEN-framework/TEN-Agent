#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import traceback
import aiohttp
import json
import time
import re

import numpy as np
from typing import List, Any, AsyncGenerator
from dataclasses import dataclass, field
from pydantic import BaseModel

from ten import (
    AudioFrame,
    VideoFrame,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)

from ten_ai_base.config import BaseConfig
from ten_ai_base.chat_memory import (
    ChatMemory,
    EVENT_MEMORY_APPENDED,
)
from ten_ai_base.usage import (
    LLMUsage,
    LLMCompletionTokensDetails,
    LLMPromptTokensDetails,
)
from ten_ai_base import (
    AsyncLLMBaseExtension,
)
from ten_ai_base.types import (
    LLMChatCompletionUserMessageParam,
    LLMToolResult,
    LLMCallCompletionArgs,
    LLMDataCompletionArgs,
    LLMToolMetadata,
)

CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
CMD_OUT_FLUSH = "flush"
CMD_OUT_TOOL_CALL = "tool_call"

DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"

CMD_PROPERTY_RESULT = "tool_result"


def is_punctuation(char):
    if char in [",", "，", ".", "。", "?", "？", "!", "！"]:
        return True
    return False


def parse_sentences(sentence_fragment, content):
    sentences = []
    current_sentence = sentence_fragment
    for char in content:
        current_sentence += char
        if is_punctuation(char):
            stripped_sentence = current_sentence
            if any(c.isalnum() for c in stripped_sentence):
                sentences.append(stripped_sentence)
            current_sentence = ""

    remain = current_sentence
    return sentences, remain


class ToolCallFunction(BaseModel):
    name: str | None = None
    arguments: str | None = None


class ToolCall(BaseModel):
    index: int
    type: str = "function"
    id: str | None = None
    function: ToolCallFunction


class ToolCallResponse(BaseModel):
    id: str
    response: LLMToolResult
    error: str | None = None


class Delta(BaseModel):
    content: str | None = None
    tool_calls: List[ToolCall] = None


class Choice(BaseModel):
    delta: Delta = None
    index: int
    finish_reason: str | None


class ResponseChunk(BaseModel):
    choices: List[Choice]
    usage: LLMUsage | None = None


@dataclass
class GlueConfig(BaseConfig):
    api_url: str = "http://localhost:8000/chat/completions"
    token: str = ""
    prompt: str = ""
    max_history: int = 10
    greeting: str = ""
    failure_info: str = ""
    modalities: List[str] = field(default_factory=lambda: ["text"])
    rtm_enabled: bool = True
    ssml_enabled: bool = False
    context_enabled: bool = False
    extra_context: dict = field(default_factory=dict)
    enable_storage: bool = False


class AsyncGlueExtension(AsyncLLMBaseExtension):
    def __init__(self, name):
        super().__init__(name)

        self.config: GlueConfig = None
        self.ten_env: AsyncTenEnv = None
        self.loop: asyncio.AbstractEventLoop = None
        self.stopped: bool = False
        self.memory: ChatMemory = None
        self.total_usage: LLMUsage = LLMUsage()
        self.users_count = 0

        self.completion_times = []
        self.connect_times = []
        self.first_token_times = []

        self.remote_stream_id: int = 999

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

        self.loop = asyncio.get_event_loop()

        self.config = await GlueConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        self.memory = ChatMemory(self.config.max_history)

        if self.config.enable_storage:
            result = await ten_env.send_cmd(Cmd.create("retrieve"))
            if result.get_status_code() == StatusCode.OK:
                try:
                    history = json.loads(result.get_property_string("response"))
                    for i in history:
                        self.memory.put(i)
                    ten_env.log_info(f"on retrieve context {history}")
                except Exception:
                    ten_env.log_error("Failed to handle retrieve result {e}")
            else:
                ten_env.log_warn("Failed to retrieve content")

        self.memory.on(EVENT_MEMORY_APPENDED, self._on_memory_appended)

        self.ten_env = ten_env

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

        self.stopped = True
        await self.queue.put(None)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        status = StatusCode.OK
        detail = "success"

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(ten_env)
            await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            ten_env.log_info("on flush")
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.config.greeting and self.users_count == 1:
                self.send_text_output(ten_env, self.config.greeting, True)
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
        else:
            await super().on_cmd(ten_env, cmd)
            return

        cmd_result = CmdResult.create(status)
        cmd_result.set_property_string("detail", detail)
        await ten_env.return_result(cmd_result, cmd)

    async def on_call_chat_completion(
        self, ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs
    ) -> any:
        raise RuntimeError("Not implemented")

    async def on_data_chat_completion(
        self, ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs
    ) -> None:
        input_messages: LLMChatCompletionUserMessageParam = kargs.get("messages", [])

        messages = []
        if self.config.prompt:
            messages.append({"role": "system", "content": self.config.prompt})

        history = self.memory.get()
        while history:
            if history[0].get("role") == "tool":
                history = history[1:]
                continue
            if history[0].get("role") == "assistant" and history[0].get("tool_calls"):
                history = history[1:]
                continue

            # Skip the first tool role
            break

        messages.extend(history)

        if not input_messages:
            ten_env.log_warn("No message in data")
        else:
            messages.extend(input_messages)
            for i in input_messages:
                self.memory.put(i)

        def tool_dict(tool: LLMToolMetadata):
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

        def trim_xml(input_string):
            return re.sub(r"<[^>]+>", "", input_string).strip()

        tools = []
        for tool in self.available_tools:
            tools.append(tool_dict(tool))

        total_output = ""
        sentence_fragment = ""
        calls = {}

        sentences = []
        start_time = time.time()
        first_token_time = None
        response = self._stream_chat(messages=messages, tools=tools)
        async for message in response:
            self.ten_env.log_debug(f"content: {message}")
            try:
                c = ResponseChunk(**message)
                if c.choices:
                    if c.choices[0].delta.content:
                        if first_token_time is None:
                            first_token_time = time.time()
                            self.first_token_times.append(first_token_time - start_time)

                        content = c.choices[0].delta.content
                        if self.config.ssml_enabled and content.startswith("<speak>"):
                            content = trim_xml(content)
                        total_output += content
                        sentences, sentence_fragment = parse_sentences(
                            sentence_fragment, content
                        )
                        for s in sentences:
                            await self._send_text(s)
                    if c.choices[0].delta.tool_calls:
                        self.ten_env.log_info(
                            f"tool_calls: {c.choices[0].delta.tool_calls}"
                        )
                        for call in c.choices[0].delta.tool_calls:
                            if call.index not in calls:
                                calls[call.index] = ToolCall(
                                    id=call.id,
                                    index=call.index,
                                    function=ToolCallFunction(name="", arguments=""),
                                )
                            if call.function.name:
                                calls[call.index].function.name += call.function.name
                            if call.function.arguments:
                                calls[
                                    call.index
                                ].function.arguments += call.function.arguments
                if c.usage:
                    self.ten_env.log_info(f"usage: {c.usage}")
                    await self._update_usage(c.usage)
            except Exception as e:
                self.ten_env.log_error(f"Failed to parse response: {message} {e}")
                traceback.print_exc()
        if sentence_fragment:
            await self._send_text(sentence_fragment)
        end_time = time.time()
        self.completion_times.append(end_time - start_time)

        if total_output:
            self.memory.put({"role": "assistant", "content": total_output})

        if calls:
            tasks = []
            tool_calls = []
            for _, call in calls.items():
                self.ten_env.log_info(f"tool call: {call}")
                tool_calls.append(call.model_dump())
                tasks.append(self.handle_tool_call(call))
            self.memory.put({"role": "assistant", "tool_calls": tool_calls})
            responses = await asyncio.gather(*tasks)
            for r in responses:
                content = r.response["content"]
                self.ten_env.log_info(f"tool call response: {content} {r.id}")
                self.memory.put(
                    {
                        "role": "tool",
                        "content": json.dumps(content),
                        "tool_call_id": r.id,
                    }
                )

            # request again to let the model know the tool call results
            await self.on_data_chat_completion(ten_env)

        self.ten_env.log_info(f"total_output: {total_output} {calls}")

    async def on_tools_update(
        self, ten_env: AsyncTenEnv, tool: LLMToolMetadata
    ) -> None:
        # Implement the logic for tool updates
        return await super().on_tools_update(ten_env, tool)

    async def handle_tool_call(self, call: ToolCall) -> ToolCallResponse:
        cmd: Cmd = Cmd.create(CMD_OUT_TOOL_CALL)
        cmd.set_property_string("name", call.function.name)
        cmd.set_property_from_json("arguments", call.function.arguments)

        # Send the command and handle the result through the future
        result: CmdResult = await self.ten_env.send_cmd(cmd)
        if result.get_status_code() == StatusCode.OK:
            tool_result: LLMToolResult = json.loads(
                result.get_property_to_json(CMD_PROPERTY_RESULT)
            )

            self.ten_env.log_info(f"tool_result: {call} {tool_result}")
            return ToolCallResponse(id=call.id, response=tool_result)
        else:
            self.ten_env.log_error("Tool call failed")
            return ToolCallResponse(
                id=call.id,
                error=f"Tool call failed with status code {result.get_status_code()}",
            )

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_info(f"on_data name {data_name}")

        is_final = False
        input_text = ""
        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
        except Exception as err:
            ten_env.log_info(
                f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL} failed, err: {err}"
            )

        try:
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        except Exception as err:
            ten_env.log_info(
                f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_TEXT} failed, err: {err}"
            )

        if not is_final:
            ten_env.log_info("ignore non-final input")
            return
        if not input_text:
            ten_env.log_info("ignore empty text")
            return

        ten_env.log_info(f"OnData input text: [{input_text}]")

        # Start an asynchronous task for handling chat completion
        message = LLMChatCompletionUserMessageParam(role="user", content=input_text)
        await self.queue_input_item(False, messages=[message])

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        pass

    async def on_video_frame(
        self, ten_env: AsyncTenEnv, video_frame: VideoFrame
    ) -> None:
        pass

    async def _send_text(self, text: str) -> None:
        data = Data.create("text_data")
        data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, True)
        asyncio.create_task(self.ten_env.send_data(data))

    async def _stream_chat(
        self, messages: List[Any], tools: List[Any]
    ) -> AsyncGenerator[dict, None]:
        async with aiohttp.ClientSession() as session:
            try:
                payload = {
                    "messages": messages,
                    "tools": tools,
                    "tools_choice": "auto" if tools else "none",
                    "model": "gpt-3.5-turbo",
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    "ssml_enabled": self.config.ssml_enabled,
                }
                if self.config.context_enabled:
                    payload["context"] = {**self.config.extra_context}
                self.ten_env.log_info(f"payload before sending: {json.dumps(payload)}")
                headers = {
                    "Authorization": f"Bearer {self.config.token}",
                    "Content-Type": "application/json",
                }

                start_time = time.time()
                async with session.post(
                    self.config.api_url, json=payload, headers=headers
                ) as response:
                    if response.status != 200:
                        r = await response.json()
                        self.ten_env.log_error(
                            f"Received unexpected status {r} from the server."
                        )
                        if self.config.failure_info:
                            await self._send_text(self.config.failure_info)
                        return
                    end_time = time.time()
                    self.connect_times.append(end_time - start_time)

                    async for line in response.content:
                        if line:
                            l = line.decode("utf-8").strip()
                            if l.startswith("data:"):
                                content = l[5:].strip()
                                if content == "[DONE]":
                                    break
                                self.ten_env.log_debug(f"content: {content}")
                                yield json.loads(content)
            except Exception as e:
                traceback.print_exc()
                self.ten_env.log_error(f"Failed to handle {e}")
            finally:
                await session.close()
                session = None

    async def _update_usage(self, usage: LLMUsage) -> None:
        if not self.config.rtm_enabled:
            return

        self.total_usage.completion_tokens += usage.completion_tokens
        self.total_usage.prompt_tokens += usage.prompt_tokens
        self.total_usage.total_tokens += usage.total_tokens

        if self.total_usage.completion_tokens_details is None:
            self.total_usage.completion_tokens_details = LLMCompletionTokensDetails()
        if self.total_usage.prompt_tokens_details is None:
            self.total_usage.prompt_tokens_details = LLMPromptTokensDetails()

        if usage.completion_tokens_details:
            self.total_usage.completion_tokens_details.accepted_prediction_tokens += (
                usage.completion_tokens_details.accepted_prediction_tokens
            )
            self.total_usage.completion_tokens_details.audio_tokens += (
                usage.completion_tokens_details.audio_tokens
            )
            self.total_usage.completion_tokens_details.reasoning_tokens += (
                usage.completion_tokens_details.reasoning_tokens
            )
            self.total_usage.completion_tokens_details.rejected_prediction_tokens += (
                usage.completion_tokens_details.rejected_prediction_tokens
            )

        if usage.prompt_tokens_details:
            self.total_usage.prompt_tokens_details.audio_tokens += (
                usage.prompt_tokens_details.audio_tokens
            )
            self.total_usage.prompt_tokens_details.cached_tokens += (
                usage.prompt_tokens_details.cached_tokens
            )

        self.ten_env.log_info(f"total usage: {self.total_usage}")

        data = Data.create("llm_stat")
        data.set_property_from_json("usage", json.dumps(self.total_usage.model_dump()))
        if self.connect_times and self.completion_times and self.first_token_times:
            data.set_property_from_json(
                "latency",
                json.dumps(
                    {
                        "connection_latency_95": np.percentile(self.connect_times, 95),
                        "completion_latency_95": np.percentile(
                            self.completion_times, 95
                        ),
                        "first_token_latency_95": np.percentile(
                            self.first_token_times, 95
                        ),
                        "connection_latency_99": np.percentile(self.connect_times, 99),
                        "completion_latency_99": np.percentile(
                            self.completion_times, 99
                        ),
                        "first_token_latency_99": np.percentile(
                            self.first_token_times, 99
                        ),
                    }
                ),
            )
        asyncio.create_task(self.ten_env.send_data(data))

    async def _on_memory_appended(self, message: dict) -> None:
        self.ten_env.log_info(f"Memory appended: {message}")
        if not self.config.enable_storage:
            return

        role = message.get("role")
        stream_id = self.remote_stream_id if role == "user" else 0
        try:
            d = Data.create("append")
            d.set_property_string("text", message.get("content"))
            d.set_property_string("role", role)
            d.set_property_int("stream_id", stream_id)
            asyncio.create_task(self.ten_env.send_data(d))
        except Exception as e:
            self.ten_env.log_error(f"Error send append_context data {message} {e}")
