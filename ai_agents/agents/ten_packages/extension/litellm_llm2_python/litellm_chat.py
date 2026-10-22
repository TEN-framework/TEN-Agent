#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import json
import random
from typing import Any, AsyncGenerator, List
from pydantic import BaseModel
import litellm

from ten_ai_base.struct import (
    ImageContent,
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
    TextContent,
)
from ten_ai_base.types import LLMToolMetadata
from ten_runtime.async_ten_env import AsyncTenEnv

from .think_parser import ThinkParser


@dataclass
class LiteLLMConfig(BaseModel):
    api_key: str = ""
    # Empty by default: LiteLLM routes by the model prefix (e.g.
    # "anthropic/claude-3-5-sonnet", "gpt-4o", "gemini/gemini-1.5-pro") and
    # resolves credentials from each provider's own env var. Set base_url only
    # to target a LiteLLM proxy / OpenAI-compatible endpoint.
    base_url: str = ""
    model: str = "gpt-4o"
    proxy_url: str = ""
    temperature: float = 0.7
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    max_tokens: int = 4096
    seed: int = random.randint(0, 1000000)
    prompt: str = "You are a helpful assistant."
    custom_headers: dict[str, Any] = field(default_factory=dict)
    black_list_params: List[str] = field(
        default_factory=lambda: ["messages", "tools", "stream", "n", "model"]
    )

    def is_black_list_params(self, key: str) -> bool:
        return key in self.black_list_params


class ReasoningMode(str, Enum):
    ModeV1 = "v1"


class LiteLLMChat:
    def __init__(self, ten_env: AsyncTenEnv, config: LiteLLMConfig):
        self.config = config
        self.ten_env = ten_env
        ten_env.log_info(f"LiteLLMChat initialized with model: {config.model}")

        # LiteLLM is called through its SDK function (litellm.acompletion),
        # not a persistent client. These call-time kwargs are merged into
        # every request. Credentials/base_url are forwarded only when set so
        # LiteLLM's provider-env fallback keeps working.
        self.completion_kwargs: dict[str, Any] = {
            # Silently drop per-provider-unsupported params (e.g. Anthropic
            # rejecting seed/frequency_penalty, Gemini rejecting OpenAI-schema
            # response params) instead of erroring.
            "drop_params": True,
        }
        if config.api_key:
            self.completion_kwargs["api_key"] = config.api_key
        if config.base_url:
            self.completion_kwargs["api_base"] = config.base_url

        extra_headers: dict[str, str] = {}
        for key, value in config.custom_headers.items():
            if isinstance(value, (dict, list)):
                ten_env.log_warn(
                    f"Skipping custom header '{key}':"
                    f" value must be a scalar, got {type(value).__name__}"
                )
                continue
            extra_headers[str(key)] = str(value)
        if extra_headers:
            self.completion_kwargs["extra_headers"] = extra_headers

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
                json_dict["function"]["parameters"]["required"].append(
                    param.name
                )
            if param.type == "array":
                json_dict["function"]["parameters"]["properties"][param.name][
                    "items"
                ] = param.items

        return json_dict

    async def get_chat_completions(
        self, request_input: LLMRequest
    ) -> AsyncGenerator[LLMResponse, None]:
        messages = request_input.messages
        tools = None
        parsed_messages = []
        system_prompt = request_input.prompt or self.config.prompt

        self.ten_env.log_info(
            f"get_chat_completions: {len(messages)} messages, streaming: {request_input.streaming}"
        )

        for message in messages:
            match message:
                case LLMMessageContent():
                    role = message.role
                    content = message.content
                    if isinstance(content, str):
                        parsed_messages.append(
                            {"role": role, "content": content}
                        )
                    elif isinstance(content, list):
                        # Assuming content is a list of objects
                        content_items = []
                        for item in content:
                            match item:
                                case TextContent():
                                    content_items.append(
                                        {"type": "text", "text": item.text}
                                    )
                                case ImageContent():
                                    content_items.append(
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": item.image_url.url
                                            },
                                        }
                                    )
                        parsed_messages.append(
                            {"role": role, "content": content_items}
                        )
                case LLMMessageFunctionCall():
                    # Handle function call messages
                    parsed_messages.append(
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": message.call_id,
                                    "type": "function",
                                    "function": {
                                        "name": message.name,
                                        "arguments": message.arguments,
                                    },
                                }
                            ],
                        }
                    )
                case LLMMessageFunctionCallOutput():
                    # Handle function call output messages
                    parsed_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": message.call_id,
                            "content": message.output,
                        }
                    )

        for tool in request_input.tools or []:
            if tools is None:
                tools = []
            tools.append(self._convert_tools_to_dict(tool))

        # Check if model is a reasoning model (gpt-5.x) that requires different parameters
        is_reasoning_model = (
            self.config.model and self.config.model.lower().startswith("gpt-5")
        )

        # Build request
        req = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *parsed_messages,
            ],
            "tools": tools,
            "stream": request_input.streaming,
            "n": 1,  # Assuming single response for now
        }

        # GPT-5.x models use max_completion_tokens and don't support sampling parameters
        if is_reasoning_model:
            req["max_completion_tokens"] = self.config.max_tokens
        else:
            req["max_tokens"] = self.config.max_tokens
            req["temperature"] = self.config.temperature
            req["top_p"] = self.config.top_p
            req["presence_penalty"] = self.config.presence_penalty
            req["frequency_penalty"] = self.config.frequency_penalty
            req["seed"] = self.config.seed

        # Add additional parameters if they are not in the black list
        for key, value in (request_input.parameters or {}).items():
            # Check if it's a valid option and not in black list
            if not self.config.is_black_list_params(key):
                self.ten_env.log_debug(f"set litellm param: {key} = {value}")
                req[key] = value

        self.ten_env.log_info(f"Requesting chat completions with: {req}")

        try:
            # LiteLLM returns OpenAI-shaped chunks, so the streaming/parsing
            # below is identical to the OpenAI extension.
            response = await litellm.acompletion(
                **req, **self.completion_kwargs
            )

            full_content = ""
            # Check for tool calls
            tool_calls_dict = defaultdict(
                lambda: {
                    "id": None,
                    "function": {"arguments": "", "name": None},
                    "type": None,
                }
            )

            parser = ThinkParser()
            reasoning_mode = None
            reasoning_full_content = ""

            last_chat_completion = None

            async for chat_completion in response:
                self.ten_env.log_debug(f"Chat completion: {chat_completion}")
                if chat_completion is None or len(chat_completion.choices) == 0:
                    continue
                last_chat_completion = chat_completion
                choice = chat_completion.choices[0]
                delta = choice.delta

                self.ten_env.log_debug(f"Processing choice: {choice}")

                content = delta.content if delta and delta.content else ""
                raw_reasoning_content = (
                    delta.reasoning_content
                    if delta and hasattr(delta, "reasoning_content")
                    else None
                )
                reasoning_content = raw_reasoning_content or ""

                if reasoning_mode is None and raw_reasoning_content is not None:
                    reasoning_mode = ReasoningMode.ModeV1

                if reasoning_mode == ReasoningMode.ModeV1:
                    if reasoning_content:
                        for (
                            event_type,
                            event_value,
                        ) in parser.process_reasoning_content(
                            reasoning_content
                        ):
                            if event_type == "reasoning_delta":
                                # Use a local accumulator instead of parser state
                                # because parser.think_content can be reset when
                                # reasoning_done is emitted in the same cycle.
                                reasoning_full_content += event_value
                                yield LLMResponseReasoningDelta(
                                    response_id=chat_completion.id,
                                    role="assistant",
                                    content=reasoning_full_content,
                                    delta=event_value,
                                    created=chat_completion.created,
                                )
                    elif parser.state == "THINK":
                        for (
                            event_type,
                            event_value,
                        ) in parser.process_reasoning_content(""):
                            if event_type == "reasoning_done":
                                yield LLMResponseReasoningDone(
                                    response_id=chat_completion.id,
                                    role="assistant",
                                    content=event_value,
                                    created=chat_completion.created,
                                )
                                reasoning_full_content = ""

                    if content:
                        full_content += content
                        yield LLMResponseMessageDelta(
                            response_id=chat_completion.id,
                            role="assistant",
                            content=full_content,
                            delta=content,
                            created=chat_completion.created,
                        )
                elif content:
                    for event_type, event_value in parser.process_content(
                        content
                    ):
                        if event_type == "message_delta":
                            full_content += event_value
                            yield LLMResponseMessageDelta(
                                response_id=chat_completion.id,
                                role="assistant",
                                content=full_content,
                                delta=event_value,
                                created=chat_completion.created,
                            )
                        elif event_type == "reasoning_delta":
                            # Keep reasoning delta content cumulative and stable.
                            reasoning_full_content += event_value
                            yield LLMResponseReasoningDelta(
                                response_id=chat_completion.id,
                                role="assistant",
                                content=reasoning_full_content,
                                delta=event_value,
                                created=chat_completion.created,
                            )
                        elif event_type == "reasoning_done":
                            yield LLMResponseReasoningDone(
                                response_id=chat_completion.id,
                                role="assistant",
                                content=event_value,
                                created=chat_completion.created,
                            )
                            reasoning_full_content = ""

                if delta.tool_calls:
                    try:
                        for tool_call in delta.tool_calls:
                            self.ten_env.log_info(f"Tool call: {tool_call}")
                            if tool_call.index not in tool_calls_dict:
                                tool_calls_dict[tool_call.index] = {
                                    "id": None,
                                    "function": {"arguments": "", "name": None},
                                    "type": None,
                                }

                            if tool_call.id:
                                tool_calls_dict[tool_call.index][
                                    "id"
                                ] = tool_call.id

                            # If the function name is not None, set it
                            if tool_call.function.name:
                                tool_calls_dict[tool_call.index]["function"][
                                    "name"
                                ] = tool_call.function.name

                            # Append the arguments if not None
                            if tool_call.function.arguments:
                                tool_calls_dict[tool_call.index]["function"][
                                    "arguments"
                                ] += tool_call.function.arguments

                            # If the type is not None, set it
                            if tool_call.type:
                                tool_calls_dict[tool_call.index][
                                    "type"
                                ] = tool_call.type
                    except Exception as e:
                        import traceback

                        traceback.print_exc()
                        self.ten_env.log_error(
                            f"Error processing tool call: {e} {tool_calls_dict}"
                        )

            if last_chat_completion is None:
                self.ten_env.log_info("No chat completion choices found.")
                return

            for event_type, event_value in parser.finalize():
                if event_type == "message_delta":
                    full_content += event_value
                    yield LLMResponseMessageDelta(
                        response_id=last_chat_completion.id,
                        role="assistant",
                        content=full_content,
                        delta=event_value,
                        created=last_chat_completion.created,
                    )
                elif event_type == "reasoning_delta":
                    # Keep reasoning delta content cumulative and stable.
                    reasoning_full_content += event_value
                    yield LLMResponseReasoningDelta(
                        response_id=last_chat_completion.id,
                        role="assistant",
                        content=reasoning_full_content,
                        delta=event_value,
                        created=last_chat_completion.created,
                    )
                elif event_type == "reasoning_done":
                    yield LLMResponseReasoningDone(
                        response_id=last_chat_completion.id,
                        role="assistant",
                        content=event_value,
                        created=last_chat_completion.created,
                    )
                    reasoning_full_content = ""

            # Convert the dictionary to a list
            tool_calls_list = list(tool_calls_dict.values())

            # Emit tool calls event (fire-and-forget)
            if tool_calls_list:
                for tool_call in tool_calls_list:
                    arguements = json.loads(tool_call["function"]["arguments"])
                    self.ten_env.log_info(
                        f"Tool call22: {choice.delta.model_dump_json()}"
                    )
                    yield LLMResponseToolCall(
                        response_id=last_chat_completion.id,
                        id=last_chat_completion.id,
                        tool_call_id=tool_call["id"],
                        name=tool_call["function"]["name"],
                        arguments=arguements,
                        created=last_chat_completion.created,
                    )

            # Emit content finished event after the loop completes
            yield LLMResponseMessageDone(
                response_id=last_chat_completion.id,
                role="assistant",
                content=full_content,
                created=last_chat_completion.created,
            )
        except Exception as e:
            raise RuntimeError(f"CreateChatCompletion failed, err: {e}") from e
