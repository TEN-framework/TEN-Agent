"""Tests for optional model routing without loading the native TEN runtime."""

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path

import pytest


PACKAGE = "main_jev_python_routing_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [
    str(
        Path(__file__).resolve().parents[1]
        / "tenapp/ten_packages/extension/main_jev_python"
    )
]
sys.modules.setdefault(PACKAGE, package)
config_module = importlib.import_module(f"{PACKAGE}.config")
routing_module = importlib.import_module(f"{PACKAGE}.routing")
ModelRoutingConfig = config_module.ModelRoutingConfig
resolve_destination = routing_module.resolve_destination


class FakeResult:
    def __init__(self, payload, status=0):
        self.payload = payload
        self.status = status

    def get_status_code(self):
        return self.status

    def get_property_to_json(self, _path):
        return json.dumps(self.payload), None


def decision(choice, confidence, request_id="turn-1"):
    return {
        "request_id": request_id,
        "answers": {
            "route": {
                "type": "choice",
                "choice": choice,
                "confidence": confidence,
            }
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer,expected,status",
    [
        (decision("fast", 0.9), "llm_fast", "selected_fast"),
        (decision("fast", 0.79), "llm_deep", "below_threshold"),
        (decision("deep", 0.99), "llm_deep", "selected_deep"),
        (decision("fast", 0.99, "old-turn"), "llm_fast", "stale_decision"),
        (decision("fast", True), "llm_deep", "below_threshold"),
    ],
)
async def test_route_selection(answer, expected, status):
    config = ModelRoutingConfig(enabled=True)

    async def send(payload):
        assert payload["questions"]["route"]["type"] == "choice"
        assert payload["state"]["latest_user_text"] == "Hello"
        return FakeResult(answer), None

    route = await resolve_destination(config, "Hello", "turn-1", send)
    assert route.destination == expected
    assert route.status == status
    assert route.latency_ms >= 0
    if status == "stale_decision":
        assert route.choice is None
    else:
        assert route.choice == answer["answers"]["route"]["choice"]
        assert route.confidence == (
            None
            if isinstance(answer["answers"]["route"]["confidence"], bool)
            else answer["answers"]["route"]["confidence"]
        )


@pytest.mark.asyncio
async def test_provider_error_and_timeout_fall_back_to_fast():
    config = ModelRoutingConfig(enabled=True, timeout_ms=1)

    async def failed(_payload):
        return None, RuntimeError("offline")

    async def slow(_payload):
        await asyncio.sleep(0.1)

    provider_error = await resolve_destination(
        config, "Hello", "turn-1", failed
    )
    assert provider_error.destination == "llm_fast"
    assert provider_error.status == "provider_error"
    timeout = await resolve_destination(config, "Hello", "turn-1", slow)
    assert timeout.destination == "llm_fast"
    assert timeout.status == "timeout"


@pytest.mark.asyncio
async def test_cancellation_never_starts_fallback_request():
    config = ModelRoutingConfig(enabled=True)
    started = asyncio.Event()

    async def pending(_payload):
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(
        resolve_destination(config, "Hello", "turn-1", pending)
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_routing_disabled_keeps_original_target():
    async def unexpected(_payload):
        pytest.fail("disabled routing must not call Jev")

    route = await resolve_destination(
        ModelRoutingConfig(), "Hello", "turn-1", unexpected
    )
    assert route.destination == "llm"
    assert route.status == "disabled"
