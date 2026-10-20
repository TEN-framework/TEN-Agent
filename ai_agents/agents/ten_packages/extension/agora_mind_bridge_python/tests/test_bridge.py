"""Regression tests for the Agora Mind message translations."""

import asyncio
import json
import sys
import types
from enum import IntEnum

import pytest


class StatusCode(IntEnum):
    OK = 0
    ERROR = 1


class FakeCmd:
    def __init__(self, name):
        self.name = name
        self.properties = {}
        self.destinations = []

    @classmethod
    def create(cls, name):
        return cls(name)

    def get_name(self):
        return self.name

    def get_property_to_json(self, _path):
        return json.dumps(self.properties), None

    def set_property_from_json(self, _path, payload):
        self.properties = json.loads(payload)

    def set_dests(self, destinations):
        self.destinations = destinations


class FakeData:
    def __init__(self, name, payload):
        self.name = name
        self.payload = payload
        self.destinations = []

    @classmethod
    def create(cls, name):
        return cls(name, {})

    def get_name(self):
        return self.name

    def get_property_to_json(self, _path):
        return json.dumps(self.payload), None

    def set_property_from_json(self, _path, payload):
        self.payload = json.loads(payload)

    def set_dests(self, destinations):
        self.destinations = destinations


class FakeResult:
    def __init__(self, status=StatusCode.OK, response=None):
        self.status = status
        self.response = response or {"type": "session.user_input.accepted"}

    def get_status_code(self):
        return self.status

    def get_property_string(self, name):
        if name != "response_json":
            return None, None
        return json.dumps(self.response), None

    def set_property_string(self, name, value):
        if name == "response_json":
            self.response_json = value


class FakeEnv:
    def __init__(self):
        self.commands = []
        self.data = []

    async def send_cmd(self, command):
        self.commands.append(command)
        response = {"type": f"{command.name}.completed"}
        if command.name == "create_session":
            response = {"type": "session.created", "session_id": 7}
        return FakeResult(response=response), None

    async def send_data(self, data):
        self.data.append(data)

    def log_debug(self, _message):
        pass

    def log_warn(self, _message):
        pass

    def log_error(self, _message):
        pass


runtime = types.ModuleType("ten_runtime")
runtime.Addon = object
runtime.register_addon_as_extension = lambda _name: lambda addon: addon
runtime.AsyncExtension = type(
    "AsyncExtension", (), {"__init__": lambda self, _name: None}
)
runtime.AsyncTenEnv = type("AsyncTenEnv", (), {})
runtime.Cmd = FakeCmd
runtime.CmdResult = type(
    "CmdResult",
    (),
    {
        "create": classmethod(
            lambda cls, status, _cmd: FakeResult(status=status)
        )
    },
)
runtime.Data = FakeData
runtime.Loc = lambda *parts: parts
runtime.StatusCode = StatusCode
sys.modules["ten_runtime"] = runtime

from ten_packages.extension.agora_mind_bridge_python.extension import (  # noqa: E402
    AgoraMindBridgeExtension,
)
from ten_packages.extension.agora_mind_bridge_python.protocol import (  # noqa: E402
    turn_text_from_event,
)


def bridge_with_session(session_id=7):
    bridge = AgoraMindBridgeExtension("bridge")
    bridge.ten_env = FakeEnv()
    bridge.session_id = session_id
    bridge.config.example_id = "case-1"
    return bridge


def test_turn_text_ignores_monitoring_events_and_collects_text_items():
    event = {
        "type": "workspace.event",
        "event": {
            "type": "session_turn_completed",
            "session_id": 7,
            "source": {"type": "top_level"},
            "result": [
                {"type": "text", "text": "Done"},
                {"type": "action", "name": "ignored"},
                {"type": "text", "text": "."},
            ],
        },
    }
    assert turn_text_from_event(json.dumps(event), 7) == (7, "Done.")
    event["event"]["source"] = {"type": "monitoring"}
    assert turn_text_from_event(json.dumps(event), 7) is None


@pytest.mark.asyncio
async def test_duplicate_asr_final_is_submitted_once():
    bridge = bridge_with_session()
    data = FakeData(
        "asr_result",
        {"text": "Book the flight", "final": True, "metadata": {}},
    )

    await bridge.on_data(bridge.ten_env, data)
    await bridge.on_data(bridge.ten_env, data)

    assert len(bridge.ten_env.commands) == 1
    command = bridge.ten_env.commands[0]
    assert command.name == "submit_user_input"
    assert command.properties["session_id"] == 7
    assert json.loads(command.properties["input_json"])["text"] == (
        "Book the flight"
    )


@pytest.mark.asyncio
async def test_same_text_is_allowed_again_after_turn_completion():
    bridge = bridge_with_session()
    asr = FakeData("asr_result", {"text": "Yes", "final": True, "metadata": {}})
    event = {
        "type": "workspace.event",
        "event": {
            "type": "session_turn_completed",
            "session_id": 7,
            "source": {"type": "top_level"},
            "input_sequence_range": {"first": 1, "last": 1},
            "result": [{"type": "text", "text": "Done"}],
        },
    }

    await bridge.on_data(bridge.ten_env, asr)
    await bridge.on_data(
        bridge.ten_env,
        FakeData("agora_mind_event", {"event_json": json.dumps(event)}),
    )
    await bridge.on_data(bridge.ten_env, asr)

    assert [command.name for command in bridge.ten_env.commands] == [
        "submit_user_input",
        "submit_user_input",
    ]


@pytest.mark.asyncio
async def test_turn_completion_is_sent_to_tts_once_with_case_metadata():
    bridge = bridge_with_session()
    event = {
        "type": "workspace.event",
        "event": {
            "type": "session_turn_completed",
            "session_id": 7,
            "source": {"type": "top_level"},
            "input_sequence_range": {"first": 1, "last": 1},
            "result": [{"type": "text", "text": "Flight booked."}],
        },
    }
    data = FakeData("agora_mind_event", {"event_json": json.dumps(event)})

    await bridge.on_data(bridge.ten_env, data)
    await bridge.on_data(bridge.ten_env, data)

    assert len(bridge.ten_env.data) == 1
    output = bridge.ten_env.data[0]
    assert output.name == "tts_text_input"
    assert output.destinations == [("", "", "tts")]
    assert output.payload["text"] == "Flight booked."
    assert output.payload["text_input_end"] is True
    assert output.payload["metadata"]["example_id"] == "case-1"


@pytest.mark.asyncio
async def test_create_session_response_sets_session_id():
    bridge = AgoraMindBridgeExtension("bridge")
    bridge.ten_env = FakeEnv()
    command = FakeCmd("create_session")
    command.properties = {
        "model": "custom",
        "input_merge_policy_json": '{"batch":"disabled"}',
    }

    returned = []

    async def return_result(result):
        returned.append(result)

    bridge.ten_env.return_result = return_result
    await bridge.on_cmd(bridge.ten_env, command)

    assert bridge.session_id == 7
    assert len(returned) == 1
    assert returned[0].status == StatusCode.OK
    assert bridge.ten_env.commands[0].properties == command.properties


@pytest.mark.asyncio
async def test_delete_session_clears_cached_session():
    bridge = bridge_with_session()
    command = FakeCmd("delete_session")
    command.properties = {"session_id": 7}

    async def return_result(_result):
        return None

    bridge.ten_env.return_result = return_result
    await bridge.on_cmd(bridge.ten_env, command)

    assert bridge.session_id is None


@pytest.mark.asyncio
async def test_disconnect_event_clears_cached_session():
    bridge = bridge_with_session()
    event = {"type": "extension.connection_state", "state": "disconnected"}

    await bridge.on_data(
        bridge.ten_env,
        FakeData("agora_mind_event", {"event_json": json.dumps(event)}),
    )

    assert bridge.session_id is None


@pytest.mark.asyncio
async def test_forwarded_command_timeout_is_reported():
    bridge = bridge_with_session()
    bridge.config.command_timeout_ms = 1

    async def never_returns(_command):
        await asyncio.sleep(1)

    bridge.ten_env.send_cmd = never_returns
    result, error = await bridge._send_command(
        "flush_session", {"session_id": 7}
    )

    assert result is None
    assert isinstance(error, TimeoutError)
