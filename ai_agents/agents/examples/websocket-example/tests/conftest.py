"""Small TEN boundary doubles for the graph's credential-free tests."""

import importlib
import json
from pathlib import Path
import sys
import types
from enum import IntEnum
from unittest.mock import AsyncMock, Mock

import pytest

EXTENSIONS = Path(__file__).resolve().parents[3] / "ten_packages/extension"


class StatusCode(IntEnum):
    OK = 0
    ERROR = 1


class Message:
    def __init__(self, name, properties=None):
        self.name = name
        self.properties = properties or {}
        self.destinations = []

    @classmethod
    def create(cls, name):
        return cls(name)

    def get_name(self):
        return self.name

    def get_property_to_json(self, path):
        value = self.properties if path is None else self.properties.get(path)
        return json.dumps(value), None

    def set_property_from_json(self, path, value):
        if path is None:
            self.properties = json.loads(value)
        else:
            self.properties[path] = json.loads(value)

    def set_property_string(self, name, value):
        self.properties[name] = value

    def get_property_string(self, name):
        return self.properties.get(name), None

    def set_dests(self, destinations):
        self.destinations = destinations


class Result(Message):
    @classmethod
    def create(cls, status, cmd):
        result = cls(cmd.name)
        result.status = status
        return result

    def get_status_code(self):
        return self.status


@pytest.fixture
def modules(monkeypatch):
    runtime = types.ModuleType("ten_runtime")
    runtime.AsyncExtension = type(
        "AsyncExtension", (), {"__init__": lambda self, name: None}
    )
    runtime.AsyncTenEnv = Mock
    runtime.Cmd = runtime.Data = Message
    runtime.CmdResult = Result
    runtime.StatusCode = StatusCode
    runtime.Loc = lambda *parts: parts
    runtime.AudioFrame = Mock()
    runtime.VideoFrame = Mock
    runtime.AudioFrameDataFmt = Mock()
    monkeypatch.setitem(sys.modules, "ten_runtime", runtime)
    env_module = types.ModuleType("ten_runtime.async_ten_env")
    env_module.AsyncTenEnv = Mock
    monkeypatch.setitem(sys.modules, env_module.__name__, env_module)

    loaded = types.SimpleNamespace(runtime=runtime)
    for name, directory in (
        ("websocket", "websocket_server"),
        ("bridge", "agora_mind_bridge_python"),
    ):
        alias = f"_fdb_test_{name}"
        package = types.ModuleType(alias)
        package.__path__ = [str(EXTENSIONS / directory)]
        monkeypatch.setitem(sys.modules, alias, package)
        setattr(loaded, name, importlib.import_module(f"{alias}.extension"))
    yield loaded
    for name in list(sys.modules):
        if name.startswith("_fdb_test_"):
            sys.modules.pop(name)


@pytest.fixture
def env():
    ten_env = Mock()
    ten_env.send_cmd = AsyncMock()
    ten_env.send_data = AsyncMock()
    ten_env.send_audio_frame = AsyncMock()
    ten_env.return_result = AsyncMock()
    return ten_env
