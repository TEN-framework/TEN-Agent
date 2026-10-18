"""DeepSeek mode and reasoning tests without a network request."""

import importlib
import sys
import types
from pathlib import Path

import pytest


ROOT = (
    Path(__file__).resolve().parents[3]
    / "ten_packages/extension/deepseek_llm2_python"
)
PACKAGE = "deepseek_llm2_stream_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package


class FakeValue:
    def __init__(self, **values):
        self.__dict__.update(values)


base = types.ModuleType("ten_ai_base")
base.__path__ = []
sys.modules.setdefault("ten_ai_base", base)
struct = types.ModuleType("ten_ai_base.struct")
for name in (
    "ImageContent",
    "LLMMessageContent",
    "LLMMessageFunctionCall",
    "LLMMessageFunctionCallOutput",
    "LLMRequest",
    "LLMResponse",
    "LLMResponseMessageDelta",
    "LLMResponseMessageDone",
    "LLMResponseReasoningDelta",
    "LLMResponseReasoningDone",
    "LLMResponseToolCall",
    "TextContent",
):
    setattr(struct, name, type(name, (FakeValue,), {}))
sys.modules["ten_ai_base.struct"] = struct
base_types = types.ModuleType("ten_ai_base.types")
base_types.LLMToolMetadata = type("LLMToolMetadata", (), {})
sys.modules["ten_ai_base.types"] = base_types

runtime = sys.modules.get("ten_runtime") or types.ModuleType("ten_runtime")
runtime.__path__ = []
sys.modules.setdefault("ten_runtime", runtime)
async_env = types.ModuleType("ten_runtime.async_ten_env")
async_env.AsyncTenEnv = type("AsyncTenEnv", (), {})
sys.modules["ten_runtime.async_ten_env"] = async_env

DeepSeekChatClient = importlib.import_module(
    f"{PACKAGE}.client"
).DeepSeekChatClient


def chunk(*, content=None, reasoning_content=None):
    return types.SimpleNamespace(
        id="response-1",
        created=1,
        choices=[
            types.SimpleNamespace(
                delta=types.SimpleNamespace(
                    content=content,
                    reasoning_content=reasoning_content,
                    tool_calls=None,
                )
            )
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("thinking", [False, True])
async def test_mode_is_forwarded_and_reasoning_is_separate(thinking):
    logs = []
    captured = []

    async def stream():
        if thinking:
            yield chunk(reasoning_content="private reasoning")
        yield chunk(content="spoken answer", reasoning_content="")

    async def create(**kwargs):
        captured.append(kwargs)
        return stream()

    config = types.SimpleNamespace(
        api_key="secret-api-key",
        model="deepseek-flash",
        prompt="System prompt",
        max_tokens=8192,
        temperature=0.7,
        top_p=1.0,
        presence_penalty=0.0,
        frequency_penalty=0.0,
        seed=123,
        is_black_list_params=lambda _key: False,
    )
    client = object.__new__(DeepSeekChatClient)
    client.config = config
    client.ten_env = types.SimpleNamespace(
        log_info=logs.append,
        log_debug=logs.append,
        log_error=logs.append,
    )
    client.client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)
        )
    )
    parameters = {
        "extra_body": {
            "thinking": {"type": "enabled" if thinking else "disabled"}
        }
    }
    if thinking:
        parameters["reasoning_effort"] = "high"
    request = types.SimpleNamespace(
        messages=[],
        tools=[],
        prompt=None,
        streaming=True,
        parameters=parameters,
    )

    events = [event async for event in client.get_chat_completions(request)]

    assert captured[0]["model"] == "deepseek-flash"
    assert captured[0]["extra_body"] == parameters["extra_body"]
    assert captured[0].get("reasoning_effort") == ("high" if thinking else None)
    names = [type(event).__name__ for event in events]
    if thinking:
        assert names == [
            "LLMResponseReasoningDelta",
            "LLMResponseReasoningDone",
            "LLMResponseMessageDelta",
            "LLMResponseMessageDone",
        ]
        assert events[1].content == "private reasoning"
    else:
        assert names == [
            "LLMResponseMessageDelta",
            "LLMResponseMessageDone",
        ]
    assert events[-1].content == "spoken answer"
    assert "secret-api-key" not in str(logs)
    assert "private reasoning" not in str(logs)
    assert "spoken answer" not in str(logs)
