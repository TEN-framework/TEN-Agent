"""TEN command tests with a small runtime double."""

import asyncio
import json
import sys
import types
from enum import IntEnum

import pytest


class StatusCode(IntEnum):
    OK = 0
    ERROR = 1


class FakeResult:
    def __init__(self, status):
        self.status = status
        self.payload = None

    @classmethod
    def create(cls, status, _cmd):
        return cls(status)

    def set_property_from_json(self, _path, value):
        self.payload = json.loads(value)


runtime = types.ModuleType("ten_runtime")
runtime.AsyncExtension = type(
    "AsyncExtension", (), {"__init__": lambda self, name: None}
)
runtime.Addon = type("Addon", (), {})
runtime.AsyncTenEnv = type("AsyncTenEnv", (), {})
runtime.TenEnv = type("TenEnv", (), {})
runtime.Cmd = type("Cmd", (), {})
runtime.CmdResult = FakeResult
runtime.StatusCode = StatusCode
runtime.register_addon_as_extension = lambda _name: lambda cls: cls
sys.modules.setdefault("ten_runtime", runtime)

from ten_packages.extension.typesafe_jev_python import extension  # noqa: E402
from ten_packages.extension.typesafe_jev_python.config import (
    JevConfig,
)  # noqa: E402


class FakeCmd:
    def __init__(self, name, payload):
        self.name = name
        self.payload = payload

    def get_name(self):
        return self.name

    def get_property_to_json(self, _path):
        return json.dumps(self.payload), None


class FakeEnv:
    def __init__(self):
        self.results = []
        self.logs = []

    async def return_result(self, result):
        self.results.append(result)

    def log_error(self, message):
        self.logs.append(message)

    def log_info(self, message):
        self.logs.append(message)

    async def get_property_to_json(self, _path):
        return json.dumps({"params": {"api_key": ""}}), None


@pytest.mark.asyncio
async def test_abort_cancels_only_matching_request(monkeypatch):
    started = asyncio.Event()
    ongoing = asyncio.Event()

    async def fake_evaluate(_client, payload, _timeout):
        started.set()
        if payload["request_id"] == "one":
            await ongoing.wait()
        return {"request_id": payload["request_id"], "answers": {}}

    monkeypatch.setattr(extension, "evaluate", fake_evaluate)
    addon = extension.TypeSafeJevExtension("jev")
    env = FakeEnv()
    first = asyncio.create_task(
        addon.on_cmd(env, FakeCmd("decision_evaluate", {"request_id": "one"}))
    )
    await started.wait()
    await addon.on_cmd(env, FakeCmd("abort", {"request_id": "one"}))
    await first
    await addon.on_cmd(env, FakeCmd("decision_evaluate", {"request_id": "two"}))
    assert len(env.results) == 3
    assert env.results[0].payload == {"request_id": "one", "cancelled": True}
    assert env.results[1].payload == {
        "error_code": "cancelled",
        "request_id": "one",
    }
    assert env.results[2].status == StatusCode.OK
    assert env.results[2].payload["request_id"] == "two"


@pytest.mark.asyncio
async def test_parallel_calls_and_duplicate_id(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_evaluate(_client, payload, _timeout):
        started.set()
        await release.wait()
        return {"request_id": payload["request_id"], "answers": {}}

    monkeypatch.setattr(extension, "evaluate", fake_evaluate)
    addon = extension.TypeSafeJevExtension("jev")
    env = FakeEnv()
    first = asyncio.create_task(
        addon.on_cmd(env, FakeCmd("decision_evaluate", {"request_id": "one"}))
    )
    await started.wait()
    second = asyncio.create_task(
        addon.on_cmd(env, FakeCmd("decision_evaluate", {"request_id": "two"}))
    )
    await asyncio.sleep(0)
    await addon.on_cmd(env, FakeCmd("decision_evaluate", {"request_id": "one"}))
    assert env.results[0].payload["error_code"] == "duplicate_request_id"
    assert len(addon.pending) == 2
    release.set()
    await asyncio.gather(first, second)
    assert {result.payload["request_id"] for result in env.results[1:]} == {
        "one",
        "two",
    }


@pytest.mark.asyncio
async def test_invalid_command_returns_one_safe_error():
    addon = extension.TypeSafeJevExtension("jev")
    env = FakeEnv()
    await addon.on_cmd(env, FakeCmd("decision_evaluate", {"state": "secret"}))
    assert len(env.results) == 1
    assert env.results[0].status == StatusCode.ERROR
    assert env.results[0].payload == {"error_code": "invalid_request"}
    assert "secret" not in str(env.logs)


@pytest.mark.asyncio
async def test_missing_key_is_reported_without_echoing_config():
    addon = extension.TypeSafeJevExtension("jev")
    env = FakeEnv()
    await addon.on_start(env)
    await addon.on_cmd(
        env,
        FakeCmd(
            "decision_evaluate",
            {
                "request_id": "one",
                "state": "private user text",
                "questions": {
                    "route": {
                        "type": "noul",
                        "instructions": "Simple?",
                    }
                },
            },
        ),
    )
    assert env.results[0].payload["error_code"] == "not_configured"
    assert "private user text" not in str(env.logs)


def test_safe_config_summary_never_logs_secrets():
    config = JevConfig(
        params={
            "api_key": "secret-api-key",
            "base_url": "https://example.com/?token=secret-url-token",
        }
    )
    summary = config.safe_summary()
    assert "secret-api-key" not in summary
    assert "secret-url-token" not in summary
