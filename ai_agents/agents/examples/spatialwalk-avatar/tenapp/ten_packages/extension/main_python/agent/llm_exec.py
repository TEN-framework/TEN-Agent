#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
import traceback
from typing import Awaitable, Callable, Literal, Optional
from ten_ai_base.const import CMD_PROPERTY_RESULT
from ten_ai_base.helper import AsyncQueue
from ten_ai_base.struct import (
    LLMMessage,
    LLMMessageContent,
    LLMMessageFunctionCall,
    LLMMessageFunctionCallOutput,
    LLMRequest,
    LLMResponse,
    LLMResponseMessageDelta,
    LLMResponseMessageDone,
    LLMResponseReasoningDelta,
    LLMResponseReasoningDone,
    LLMResponseToolCall,
    parse_llm_response,
)
from ten_ai_base.types import LLMToolMetadata, LLMToolResult
from ..helper import _send_cmd, _send_cmd_ex
from ten_runtime import AsyncTenEnv, Loc, StatusCode
import uuid


class LLMExec:
    """
    Context for LLM operations, including ASR and TTS.
    This class handles the interaction with the LLM, including processing commands and data.
    """

    def __init__(self, ten_env: AsyncTenEnv):
        self.ten_env = ten_env
        self.input_queue = AsyncQueue()
        self.stopped = False
        self.on_response: Optional[
            Callable[[AsyncTenEnv, str, str, bool], Awaitable[None]]
        ] = None
        self.on_reasoning_response: Optional[
            Callable[[AsyncTenEnv, str, str, bool], Awaitable[None]]
        ] = None
        self.on_tool_call: Optional[
            Callable[[AsyncTenEnv, LLMToolMetadata], Awaitable[None]]
        ] = None
        self.current_task: Optional[asyncio.Task] = None
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._process_input_queue())
        self.available_tools: list[LLMToolMetadata] = []
        self.tool_registry: dict[str, str] = {}
        self.available_tools_lock = (
            asyncio.Lock()
        )  # Lock to ensure thread-safe access
        self.contexts: list[LLMMessage] = []
        self.current_request_id: Optional[str] = None
        self.current_text = None

    async def queue_input(self, item: str) -> None:
        await self.input_queue.put(item)

    async def flush(self) -> None:
        """
        Flush the input queue to ensure all items are processed.
        This is useful for ensuring that all pending inputs are handled before stopping.
        """
        await self.input_queue.flush()
        if self.current_request_id:
            request_id = self.current_request_id
            self.current_request_id = None
            await _send_cmd(
                self.ten_env, "abort", "llm", {"request_id": request_id}
            )
        if self.current_task:
            self.current_task.cancel()

    async def stop(self) -> None:
        """
        Stop the LLMExec processing.
        This will stop the input queue processing and any ongoing tasks.
        """
        self.stopped = True
        await self.flush()
        if self.current_task:
            self.current_task.cancel()

    async def register_tool(self, tool: LLMToolMetadata, source: str) -> None:
        """
        Register tools with the LLM.
        This method sends a command to register the provided tools.
        """
        async with self.available_tools_lock:
            self.available_tools.append(tool)
            self.tool_registry[tool.name] = source

    async def _process_input_queue(self):
        """
        Process the input queue for commands and data.
        This method runs in a loop, processing items from the queue.
        """
        while not self.stopped:
            try:
                text = await self.input_queue.get()
                new_message = LLMMessageContent(role="user", content=text)
                self.current_task = self.loop.create_task(
                    self._send_to_llm(self.ten_env, new_message)
                )
                await self.current_task
            except asyncio.CancelledError:
                self.ten_env.log_info("LLMExec processing cancelled.")
                text = self.current_text
                self.current_text = None
                if self.on_response and text:
                    await self.on_response(self.ten_env, "", text, True)
            except Exception as e:
                self.ten_env.log_error(
                    f"Error processing input queue: {traceback.format_exc()}"
                )
            finally:
                self.current_task = None

    async def _queue_context(
        self, ten_env: AsyncTenEnv, new_message: LLMMessage
    ) -> None:
        """
        Queue a new message to the LLM context.
        This method appends the new message to the existing context and sends it to the LLM.
        """
        ten_env.log_info(f"_queue_context: {new_message}")
        self.contexts.append(new_message)

    async def _write_context(
        self,
        ten_env: AsyncTenEnv,
        role: Literal["user", "assistant"],
        content: str,
    ) -> None:
        last_context = self.contexts[-1] if self.contexts else None
        if last_context and last_context.role == role:
            # If the last context has the same role, append to its content
            last_context.content = content
        else:
            # Otherwise, create a new context message
            new_message = LLMMessageContent(role=role, content=content)
            await self._queue_context(ten_env, new_message)

    async def _send_to_llm(
        self, ten_env: AsyncTenEnv, new_message: LLMMessage
    ) -> None:
        messages = self.contexts.copy()
        messages.append(new_message)
        request_id = str(uuid.uuid4())
        self.current_request_id = request_id
        llm_input = LLMRequest(
            request_id=request_id,
            messages=messages,
            streaming=True,
            parameters={"temperature": 0.7},
            tools=self.available_tools,
        )
        input_json = llm_input.model_dump()
        response = _send_cmd_ex(ten_env, "chat_completion", "llm", input_json)

        # Queue the new message to the context
        await self._queue_context(ten_env, new_message)

        async for cmd_result, _ in response:
            if cmd_result and cmd_result.is_final() is False:
                if cmd_result.get_status_code() == StatusCode.OK:
                    response_json, _ = cmd_result.get_property_to_json(None)
                    ten_env.log_info(
                        f"_send_to_llm: response_json {response_json}"
                    )
                    completion = parse_llm_response(response_json)
                    await self._handle_llm_response(completion)

    async def _handle_llm_response(self, llm_output: LLMResponse | None):
        self.ten_env.log_info(f"_handle_llm_response: {llm_output}")

        match llm_output:
            case LLMResponseMessageDelta():
                delta = llm_output.delta
                text = llm_output.content
                self.current_text = text
                if delta and self.on_response:
                    await self.on_response(self.ten_env, delta, text, False)
                if text:
                    await self._write_context(self.ten_env, "assistant", text)
            case LLMResponseMessageDone():
                text = llm_output.content
                self.current_text = None
                if self.on_response and text:
                    await self.on_response(self.ten_env, "", text, True)
            case LLMResponseReasoningDelta():
                delta = llm_output.delta
                text = llm_output.content
                if delta and self.on_reasoning_response:
                    await self.on_reasoning_response(
                        self.ten_env, delta, text, False
                    )
            case LLMResponseReasoningDone():
                text = llm_output.content
                if self.on_reasoning_response and text:
                    await self.on_reasoning_response(
                        self.ten_env, "", text, True
                    )
            case LLMResponseToolCall():
                self.ten_env.log_info(
                    f"_handle_llm_response: invoking tool call {llm_output.name}"
                )
                src_extension_name = self.tool_registry.get(llm_output.name)
                result, _ = await _send_cmd(
                    self.ten_env,
                    "tool_call",
                    src_extension_name,
                    {
                        "name": llm_output.name,
                        "arguments": llm_output.arguments,
                    },
                )

                if result.get_status_code() == StatusCode.OK:
                    r, _ = result.get_property_to_json(CMD_PROPERTY_RESULT)
                    tool_result: LLMToolResult = json.loads(r)

                    self.ten_env.log_info(f"tool_result: {tool_result}")

                    context_function_call = LLMMessageFunctionCall(
                        name=llm_output.name,
                        arguments=json.dumps(llm_output.arguments),
                        call_id=llm_output.tool_call_id,
                        id=llm_output.response_id,
                        type="function_call",
                    )
                    if tool_result["type"] == "llmresult":
                        result_content = tool_result["content"]
                        if isinstance(result_content, str):
                            await self._queue_context(
                                self.ten_env, context_function_call
                            )
                            await self._send_to_llm(
                                self.ten_env,
                                LLMMessageFunctionCallOutput(
                                    output=result_content,
                                    call_id=llm_output.tool_call_id,
                                    type="function_call_output",
                                ),
                            )
                        else:
                            self.ten_env.log_error(
                                f"Unknown tool result content: {result_content}"
                            )
                    elif tool_result["type"] == "requery":
                        pass
                        # self.memory_cache = []
                        # self.memory_cache.pop()
                        # result_content = tool_result["content"]
                        # nonlocal message
                        # new_message = {
                        #     "role": "user",
                        #     "content": self._convert_to_content_parts(
                        #         message["content"]
                        #     ),
                        # }
                        # new_message["content"] = new_message[
                        #     "content"
                        # ] + self._convert_to_content_parts(
                        #     result_content
                        # )
                        # await self.queue_input_item(
                        #     True, messages=[new_message], no_tool=True
                        # )
                else:
                    self.ten_env.log_error("Tool call failed")
