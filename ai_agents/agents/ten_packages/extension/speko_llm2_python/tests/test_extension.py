import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ten_ai_base.struct import LLMRequest

from speko_llm2_python.client import SSEEvent
from speko_llm2_python.config import SpekoLLM2Config
from speko_llm2_python.extension import SpekoLLM2Extension


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_completion_interface_and_explicit_route(streaming):
    extension = SpekoLLM2Extension("speko")
    extension.config = SpekoLLM2Config(
        api_key="key",
        routing={
            "mode": "explicit",
            "objective": "balanced",
            "provider": "openai",
            "model": "test-model",
        },
    )
    extension.config.validate_required()
    extension.ten_env = MagicMock(send_data=AsyncMock())
    captured = []

    async def stream(payload, **_kwargs):
        captured.append(payload)
        yield SSEEvent("response.created", {"response_id": "response"})
        yield SSEEvent("response.text.delta", {"delta": "hello"})
        yield SSEEvent("response.completed", {"usage": {"output_tokens": 1}})

    async def complete(payload, **_kwargs):
        captured.append(payload)
        return {
            "id": "response",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hello"}],
                }
            ],
            "usage": {"output_tokens": 1},
        }

    extension.client = MagicMock(
        stream=stream, complete=complete, route={"provider": "openai"}
    )
    request = LLMRequest(request_id="request", messages=[], streaming=streaming)
    iterator = extension.on_call_chat_completion(extension.ten_env, request)
    assert inspect.isasyncgen(iterator)
    responses = [response async for response in iterator]
    assert responses[-1].content == "hello"
    assert responses[-1].response_id == "response"
    assert captured[0]["routing"] == {
        "mode": "explicit",
        "provider": "openai",
        "model": "test-model",
    }
    raw, _ = extension.ten_env.send_data.await_args.args[
        0
    ].get_property_to_json("")
    assert json.loads(raw)["metadata"]["request_id"] == "request"


@pytest.mark.asyncio
async def test_stop_cancels_base_before_closing_client_even_on_error():
    extension = SpekoLLM2Extension("speko")
    calls = []

    async def stop(_ten_env):
        calls.append("cancel")
        raise RuntimeError("base failure")

    async def close():
        calls.append("close")

    extension.client = MagicMock(close=AsyncMock(side_effect=close))
    with patch(
        "speko_llm2_python.extension.AsyncLLM2BaseExtension.on_stop",
        side_effect=stop,
    ):
        with pytest.raises(RuntimeError):
            await extension.on_stop(MagicMock())
    assert calls == ["cancel", "close"]
    assert extension.client is None


def test_config_log_redacts_url():
    config = SpekoLLM2Config(
        api_key="test-secret-key-long",
        base_url="https://user:password@example.com?signature=private",
    )
    config.validate_required()
    for secret in ("test-secret-key-long", "password", "private"):
        assert secret not in config.to_str()
