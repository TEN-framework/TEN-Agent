"""Controller tests for interruption and tool continuation targets."""

import asyncio
import importlib
import json
import sys
import types
from enum import IntEnum
from pathlib import Path

import pytest


ROOT = (
    Path(__file__).resolve().parents[1]
    / "tenapp/ten_packages/extension/main_jev_python"
)
PACKAGE = "main_jev_python_exec_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules.setdefault(PACKAGE, package)
agent_package = types.ModuleType(f"{PACKAGE}.agent")
agent_package.__path__ = [str(ROOT / "agent")]
sys.modules.setdefault(f"{PACKAGE}.agent", agent_package)


class FakeMessage:
    def __init__(self, **values):
        self.__dict__.update(values)


class FakeToolCall(FakeMessage):
    pass


class FakeQueue:
    async def flush(self):
        return None


base = types.ModuleType("ten_ai_base")
base.__path__ = []
sys.modules.setdefault("ten_ai_base", base)
constants = types.ModuleType("ten_ai_base.const")
constants.CMD_PROPERTY_RESULT = "result"
sys.modules.setdefault("ten_ai_base.const", constants)
helpers = types.ModuleType("ten_ai_base.helper")
helpers.AsyncQueue = FakeQueue
sys.modules.setdefault("ten_ai_base.helper", helpers)
struct = types.ModuleType("ten_ai_base.struct")
for name in (
    "LLMMessage",
    "LLMMessageContent",
    "LLMMessageFunctionCall",
    "LLMMessageFunctionCallOutput",
    "LLMRequest",
    "LLMResponse",
    "LLMResponseMessageDelta",
    "LLMResponseMessageDone",
    "LLMResponseReasoningDelta",
    "LLMResponseReasoningDone",
):
    setattr(struct, name, type(name, (FakeMessage,), {}))
struct.LLMResponseToolCall = FakeToolCall
struct.parse_llm_response = lambda value: value
sys.modules.setdefault("ten_ai_base.struct", struct)
base_types = types.ModuleType("ten_ai_base.types")
base_types.LLMToolMetadata = type("LLMToolMetadata", (), {})
base_types.LLMToolResult = dict
sys.modules.setdefault("ten_ai_base.types", base_types)


class StatusCode(IntEnum):
    OK = 0
    ERROR = 1


runtime = sys.modules.get("ten_runtime") or types.ModuleType("ten_runtime")
runtime.AsyncTenEnv = type("AsyncTenEnv", (), {})
runtime.StatusCode = StatusCode
sys.modules.setdefault("ten_runtime", runtime)

helper = types.ModuleType(f"{PACKAGE}.helper")
helper._send_cmd = None
helper._send_cmd_ex = None
sys.modules.setdefault(f"{PACKAGE}.helper", helper)
LLMExec = importlib.import_module(f"{PACKAGE}.agent.llm_exec").LLMExec
llm_module = sys.modules[f"{PACKAGE}.agent.llm_exec"]
ModelRoutingConfig = importlib.import_module(
    f"{PACKAGE}.config"
).ModelRoutingConfig


class FakeEnv:
    def log_info(self, _message):
        pass

    def log_error(self, _message):
        pass


@pytest.mark.asyncio
async def test_flush_aborts_jev_and_selected_llm(monkeypatch):
    calls = []

    async def send(_env, name, dest, payload):
        calls.append((name, dest, payload["request_id"]))
        return None, None

    monkeypatch.setattr(llm_module, "_send_cmd", send)
    executor = object.__new__(LLMExec)
    executor.ten_env = FakeEnv()
    executor.routing = ModelRoutingConfig(enabled=True)
    executor.input_queue = FakeQueue()
    executor.current_decision_request_id = "decision-1"
    executor.current_request_id = "llm-1"
    executor.current_llm_dest = "llm_fast"
    executor.current_task = asyncio.create_task(asyncio.sleep(10))

    await executor.flush()
    assert sorted(calls) == [
        ("abort", "jev", "decision-1"),
        ("abort", "llm_fast", "llm-1"),
    ]
    assert executor.current_task.cancelled()


@pytest.mark.asyncio
async def test_tool_continuation_keeps_selected_llm(monkeypatch):
    class ToolResult:
        def get_status_code(self):
            return StatusCode.OK

        def get_property_to_json(self, _path):
            return json.dumps({"type": "llmresult", "content": "sunny"}), None

    async def send(_env, _name, _dest, _payload):
        return ToolResult(), None

    monkeypatch.setattr(llm_module, "_send_cmd", send)
    executor = object.__new__(LLMExec)
    executor.ten_env = FakeEnv()
    executor.tool_registry = {"weather": "weather_tool"}
    executor.contexts = []
    continuation = []

    async def send_to_llm(_env, message, dest):
        continuation.append((message, dest))

    executor._send_to_llm = send_to_llm
    await executor._handle_llm_response(
        FakeToolCall(
            name="weather",
            arguments={},
            tool_call_id="call-1",
            response_id="response-1",
        ),
        "llm_fast",
    )
    assert len(continuation) == 1
    assert continuation[0][1] == "llm_fast"


@pytest.mark.asyncio
async def test_route_callback_precedes_llm_selection(monkeypatch):
    class DecisionResult:
        def get_status_code(self):
            return StatusCode.OK

        def get_property_to_json(self, _path):
            return (
                json.dumps(
                    {
                        "request_id": "decision-1",
                        "answers": {
                            "route": {
                                "type": "choice",
                                "choice": "fast",
                                "confidence": 0.92,
                            }
                        },
                    }
                ),
                None,
            )

    async def send(_env, name, dest, _payload):
        assert (name, dest) == ("decision_evaluate", "jev")
        return DecisionResult(), None

    monkeypatch.setattr(llm_module, "_send_cmd", send)
    executor = object.__new__(LLMExec)
    executor.ten_env = FakeEnv()
    executor.routing = ModelRoutingConfig(enabled=True)
    executor.current_decision_request_id = None
    observed = []

    async def on_route(_env, route):
        observed.append(route)

    executor.on_route = on_route
    monkeypatch.setattr(llm_module.uuid, "uuid4", lambda: "decision-1")
    destination = await executor._choose_llm_dest("Hello")
    assert destination == "llm_fast"
    assert len(observed) == 1
    assert observed[0].destination == destination
    assert observed[0].status == "selected_fast"
    assert executor.current_decision_request_id is None


@pytest.mark.asyncio
async def test_interrupted_decision_does_not_emit_route(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def send(_env, _name, _dest, _payload):
        started.set()
        await release.wait()
        return None, RuntimeError("stale")

    monkeypatch.setattr(llm_module, "_send_cmd", send)
    executor = object.__new__(LLMExec)
    executor.ten_env = FakeEnv()
    executor.routing = ModelRoutingConfig(enabled=True)
    executor.current_decision_request_id = None
    observed = []

    async def on_route(_env, route):
        observed.append(route)

    executor.on_route = on_route
    pending = asyncio.create_task(executor._choose_llm_dest("Hello"))
    await started.wait()
    executor.current_decision_request_id = None
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert observed == []


@pytest.mark.asyncio
async def test_cancelled_reply_does_not_emit_stale_final_text():
    started = asyncio.Event()

    class OneInputQueue:
        def __init__(self):
            self.sent = False

        async def get(self):
            if not self.sent:
                self.sent = True
                return "First request"
            await asyncio.Event().wait()

    executor = object.__new__(LLMExec)
    executor.ten_env = FakeEnv()
    executor.input_queue = OneInputQueue()
    executor.stopped = False
    executor.loop = asyncio.get_running_loop()
    executor.current_task = None
    executor.current_text = "partial stale answer"
    replies = []

    async def on_response(_env, _delta, text, _final):
        replies.append(text)

    async def pending_llm(_env, _message):
        started.set()
        await asyncio.Event().wait()

    executor.on_response = on_response
    executor._send_to_llm = pending_llm
    worker = asyncio.create_task(executor._process_input_queue())
    await started.wait()
    executor.current_task.cancel()
    await asyncio.sleep(0)
    executor.stopped = True
    worker.cancel()
    await worker
    assert replies == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,destination,thinking_type,effort",
    [
        (True, "llm_fast", "disabled", None),
        (True, "llm_deep", "enabled", "high"),
        (False, "llm", "disabled", None),
    ],
)
async def test_llm_request_uses_selected_thinking_mode(
    monkeypatch, enabled, destination, thinking_type, effort
):
    class Request(FakeMessage):
        def model_dump(self):
            return self.__dict__

    async def no_results():
        if False:
            yield None

    captured = []

    def send(_env, name, dest, payload):
        captured.append((name, dest, payload))
        return no_results()

    monkeypatch.setattr(llm_module, "LLMRequest", Request)
    monkeypatch.setattr(llm_module, "_send_cmd_ex", send)
    executor = object.__new__(LLMExec)
    executor.ten_env = FakeEnv()
    executor.routing = ModelRoutingConfig(enabled=enabled)
    executor.contexts = []
    executor.available_tools = []
    executor.current_request_id = None
    executor.current_llm_dest = None
    await executor._send_to_llm(
        executor.ten_env,
        FakeMessage(role="user", content="Hello"),
        destination,
    )
    assert len(captured) == 1
    name, dest, payload = captured[0]
    assert (name, dest) == ("chat_completion", destination)
    params = payload["parameters"]
    assert params["extra_body"]["thinking"]["type"] == thinking_type
    assert params.get("reasoning_effort") == effort
    assert payload["tools"] == []
