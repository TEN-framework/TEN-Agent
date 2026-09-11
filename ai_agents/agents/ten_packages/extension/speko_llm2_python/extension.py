#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
from ten_ai_base.llm2 import AsyncLLM2BaseExtension
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleMetricKey,
    ModuleMetrics,
    ModuleType,
)
from ten_ai_base.struct import (
    ImageContent,
    LLMMessageContent,
    LLMMessageFunctionCall,
    LLMMessageFunctionCallOutput,
    LLMRequest,
    LLMRequestRetrievePrompt,
    LLMResponse,
    LLMResponseMessageDelta,
    LLMResponseMessageDone,
    LLMResponseRetrievePrompt,
    LLMResponseToolCall,
    TextContent,
)
from ten_ai_base.types import LLMToolMetadata
from ten_runtime import AsyncTenEnv, Data

from .client import SpekoLLMClient, SpekoRouterError
from .config import SpekoLLM2Config


class SpekoLLM2Extension(AsyncLLM2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: SpekoLLM2Config | None = None
        self.client: SpekoLLMClient | None = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        try:
            config_json, error = await ten_env.get_property_to_json("")
            if error:
                raise RuntimeError(f"Failed to read configuration: {error}")
            self.config = SpekoLLM2Config.model_validate_json(config_json)
            self.config.validate_required()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            self.client = SpekoLLMClient(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout_sec=self.config.timeout_sec,
            )
        except Exception as error:
            self.config = None
            ten_env.log_error(
                f"invalid property: {error}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self._send_error(
                ModuleError(
                    module=ModuleType.LLM,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(error),
                    vendor_info=ModuleErrorVendorInfo(vendor="speko"),
                )
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        if self.client is not None:
            await self.client.close()
            self.client = None

    async def on_retrieve_prompt(
        self, ten_env: AsyncTenEnv, request: LLMRequestRetrievePrompt
    ) -> LLMResponseRetrievePrompt:
        del ten_env, request
        return LLMResponseRetrievePrompt(
            prompt=self.config.prompt if self.config else ""
        )

    async def on_call_chat_completion(
        self, ten_env: AsyncTenEnv, request: LLMRequest
    ) -> AsyncGenerator[LLMResponse, None]:
        if self.config is None or self.client is None:
            raise RuntimeError("Speko LLM extension is not configured")

        started_at = time.monotonic()
        response_id = request.request_id
        full_content = ""
        ttft_ms: int | None = None
        payload = self._build_payload(request)
        stream = request.streaming is not False
        payload["stream"] = stream
        idempotency_key = uuid.uuid4().hex

        ten_env.log_info(
            "Requesting Speko LLM response: "
            f"messages={len(request.messages)}, stream={stream}, "
            f"routing={payload.get('routing', {})}",
            category=LOG_CATEGORY_VENDOR,
        )

        try:
            if not stream:
                response = await self.client.complete(
                    payload, idempotency_key=idempotency_key
                )
                response_id = str(response.get("id", response_id))
                for item in response.get("output", []):
                    outputs, full_content = self._responses_for_item(
                        item,
                        response_id=response_id,
                        full_content=full_content,
                    )
                    for output in outputs:
                        yield output
                await self._send_metrics(
                    request,
                    response.get("usage", {}),
                    response.get("route", {}),
                    ttft_ms=None,
                )
                yield LLMResponseMessageDone(
                    response_id=response_id,
                    role="assistant",
                    content=full_content,
                    created=int(time.time()),
                )
                return

            async for event in self.client.stream(
                payload, idempotency_key=idempotency_key
            ):
                if event.name == "response.created":
                    response_id = str(
                        event.data.get("response_id", response_id)
                    )
                elif event.name == "response.text.delta":
                    delta = str(event.data.get("delta", ""))
                    if not delta:
                        continue
                    if ttft_ms is None:
                        ttft_ms = int((time.monotonic() - started_at) * 1000)
                    full_content += delta
                    yield LLMResponseMessageDelta(
                        response_id=response_id,
                        role="assistant",
                        content=full_content,
                        delta=delta,
                        created=int(time.time()),
                    )
                elif event.name == "response.item.completed":
                    item = event.data.get("item", {})
                    outputs, full_content = self._responses_for_item(
                        item,
                        response_id=response_id,
                        full_content=full_content,
                    )
                    for output in outputs:
                        yield output
                elif event.name == "response.completed":
                    await self._send_metrics(
                        request,
                        event.data.get("usage", {}),
                        self.client.route,
                        ttft_ms=ttft_ms,
                    )
                    yield LLMResponseMessageDone(
                        response_id=response_id,
                        role="assistant",
                        content=full_content,
                        created=int(time.time()),
                    )
        except SpekoRouterError as error:
            await self._report_router_error(error, request)
            raise RuntimeError(
                f"Speko Router request failed ({error.code}): {error.message}"
            ) from error

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        assert self.config is not None
        input_items: list[dict[str, Any]] = []
        prompt = request.prompt or self.config.prompt
        if prompt:
            input_items.append(self._message_item("system", prompt))
        input_items.extend(
            self._convert_message(item) for item in request.messages
        )

        parameters = dict(request.parameters or {})
        max_output_tokens = parameters.pop(
            "max_output_tokens",
            parameters.pop("max_tokens", self.config.max_output_tokens),
        )
        payload: dict[str, Any] = {
            "input": input_items,
            "max_output_tokens": max_output_tokens,
            "routing": self._routing_for_request(request, parameters),
        }
        tools = [self._convert_tool(tool) for tool in request.tools or []]
        if tools:
            payload["tools"] = tools

        temperature = parameters.pop("temperature", self.config.temperature)
        top_p = parameters.pop("top_p", self.config.top_p)
        response_format = parameters.pop("response_format", None)
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if response_format is not None:
            payload["response_format"] = response_format
        if parameters:
            self.ten_env.log_warn(
                "Ignoring unsupported Speko LLM parameters: "
                f"{sorted(parameters)}"
            )
        return payload

    def _routing_for_request(
        self, request: LLMRequest, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        assert self.config is not None
        override = parameters.pop("routing", None)
        routing = dict(override or self.config.routing)
        if not request.model:
            return routing
        if "/" in request.model:
            return {"mode": "explicit", "model": request.model}
        if routing.get("mode") == "explicit" and routing.get("provider"):
            routing["model"] = request.model
            return routing
        raise ValueError(
            "A bare TEN request model requires routing.provider; "
            "otherwise use provider/model"
        )

    @staticmethod
    def _message_item(role: str, text: str) -> dict[str, Any]:
        return {
            "type": "message",
            "role": role,
            "content": [{"type": "text", "text": text}],
        }

    def _convert_message(self, message: Any) -> dict[str, Any]:
        if isinstance(message, LLMMessageContent):
            if isinstance(message.content, str):
                text = message.content
            else:
                parts: list[str] = []
                for part in message.content:
                    if isinstance(part, TextContent):
                        parts.append(part.text)
                    elif isinstance(part, ImageContent):
                        raise ValueError(
                            "Speko Router LLM input currently supports text only"
                        )
                text = "".join(parts)
            return self._message_item(message.role, text)
        if isinstance(message, LLMMessageFunctionCall):
            return {
                "type": "function_call",
                "call_id": message.call_id,
                "name": message.name,
                "arguments": message.arguments,
            }
        if isinstance(message, LLMMessageFunctionCallOutput):
            return {
                "type": "function_result",
                "call_id": message.call_id,
                "result": message.output,
            }
        raise ValueError(f"Unsupported TEN LLM message: {type(message)}")

    @staticmethod
    def _convert_tool(tool: LLMToolMetadata) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for parameter in tool.parameters:
            properties[parameter.name] = {
                "type": parameter.type,
                "description": parameter.description,
            }
            if parameter.required:
                required.append(parameter.name)
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        }

    def _responses_for_item(
        self,
        item: Any,
        *,
        response_id: str,
        full_content: str,
    ) -> tuple[list[LLMResponse], str]:
        if not isinstance(item, dict):
            return [], full_content
        item_type = item.get("type")
        created = int(time.time())
        if item_type == "function_call":
            arguments = json.loads(str(item.get("arguments", "{}")))
            return [
                LLMResponseToolCall(
                    response_id=response_id,
                    id=response_id,
                    tool_call_id=str(item.get("call_id", "")),
                    name=str(item.get("name", "")),
                    arguments=arguments,
                    created=created,
                )
            ], full_content

        if item_type == "structured_json":
            final_text = json.dumps(
                item.get("json"), separators=(",", ":"), ensure_ascii=False
            )
        elif item_type == "message":
            final_text = "".join(
                str(part.get("text", ""))
                for part in item.get("content", [])
                if isinstance(part, dict) and part.get("type") == "text"
            )
        else:
            return [], full_content

        if final_text == full_content:
            return [], full_content
        delta = (
            final_text[len(full_content) :]
            if final_text.startswith(full_content)
            else final_text
        )
        return [
            LLMResponseMessageDelta(
                response_id=response_id,
                role="assistant",
                content=final_text,
                delta=delta,
                created=created,
            )
        ], final_text

    async def _send_metrics(
        self,
        request: LLMRequest,
        usage: Any,
        route: Any,
        *,
        ttft_ms: int | None,
    ) -> None:
        metrics: dict[str, Any] = {"usage": usage or {}}
        if ttft_ms is not None:
            metrics[ModuleMetricKey.LLM_TTFT] = ttft_ms
        data = Data.create("metrics")
        data.set_property_from_json(
            None,
            ModuleMetrics(
                id=uuid.uuid4().hex,
                module=ModuleType.LLM,
                vendor="speko",
                metrics=metrics,
                metadata={
                    "request_id": request.request_id,
                    "route": route or {},
                },
            ).model_dump_json(),
        )
        await self.ten_env.send_data(data)

    async def _report_router_error(
        self, error: SpekoRouterError, request: LLMRequest
    ) -> None:
        self.ten_env.log_error(
            f"vendor_error: code={error.code}, message={error.message}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._send_error(
            ModuleError(
                id=request.request_id,
                module=ModuleType.LLM,
                code=self._module_error_code(error).value,
                message=error.message,
                vendor_info=ModuleErrorVendorInfo(
                    vendor="speko",
                    code=error.code,
                    message=error.message,
                ),
            )
        )

    async def _send_error(self, error: ModuleError) -> None:
        data = Data.create("error")
        data.set_property_from_json(None, error.model_dump_json())
        await self.ten_env.send_data(data)

    @staticmethod
    def _module_error_code(error: SpekoRouterError) -> ModuleErrorCode:
        fatal_codes = {"authentication_failed", "insufficient_credit"}
        if error.code in fatal_codes:
            return ModuleErrorCode.FATAL_ERROR
        return ModuleErrorCode.NON_FATAL_ERROR
