"""Validate the FDB graph and exercise its TEN message path without providers."""

from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock, Mock

import pytest

from conftest import Message, Result, StatusCode

TENAPP = Path(__file__).resolve().parents[1] / "tenapp"
EXTENSIONS = TENAPP.parents[2] / "ten_packages/extension"


@pytest.fixture
def graph():
    app = json.loads((TENAPP / "property.json").read_text())
    graphs = {item["name"]: item for item in app["ten"]["predefined_graphs"]}
    assert graphs["voice_assistant"]["auto_start"] is True
    assert graphs["fdb_v3"]["auto_start"] is False
    return graphs["fdb_v3"]["graph"]


def edges(graph, kind):
    for connection in graph["connections"]:
        for route in connection.get(kind, []):
            for name in route.get("names", [route.get("name")]):
                for destination in route.get("dest", []):
                    yield connection["extension"], name, destination[
                        "extension"
                    ]


def test_fdb_nodes_dependencies_and_pcm_contract(graph):
    nodes = {node["name"]: node for node in graph["nodes"]}
    assert set(nodes) == {
        "websocket_server",
        "stt",
        "bridge",
        "agora_mind",
        "tts",
    }
    manifest = json.loads((TENAPP / "manifest.json").read_text())
    dependencies = []
    for dependency in manifest["dependencies"]:
        if "path" in dependency:
            package = TENAPP / dependency["path"] / "manifest.json"
            dependencies.append(json.loads(package.read_text())["name"])
        else:
            dependencies.append(dependency["name"])
    assert len(dependencies) == len(set(dependencies))
    assert {node["addon"] for node in nodes.values()} <= set(dependencies)
    assert {
        "type": "extension",
        "name": "agora_mind_extension_rust",
        "version": "0.1.0",
    } in manifest["dependencies"]
    socket = nodes["websocket_server"]["property"]
    assert (
        socket["sample_rate"],
        socket["channels"],
        socket["bytes_per_sample"],
    ) == (16000, 1, 2)
    assert socket["host"] == "0.0.0.0"
    assert nodes["stt"]["property"]["params"]["sample_rate"] == 16000
    assert nodes["stt"]["property"]["params"]["encoding"] == "linear16"
    assert nodes["tts"]["property"]["params"]["output_format"] == "pcm_16000"
    assert nodes["agora_mind"]["property"]["model"] == "custom"
    assert (
        nodes["agora_mind"]["property"]["endpoint"]
        == "${env:AGORA_MIND_ENDPOINT}"
    )
    assert "system_prompt" not in json.dumps(graph)


def test_routes_are_complete_and_do_not_duplicate_delivery(graph):
    names = {node["name"] for node in graph["nodes"]}
    for kind in ("cmd", "data", "audio_frame"):
        routes = list(edges(graph, kind))
        assert all(count == 1 for count in Counter(routes).values())
        assert all(
            source in names and target in names for source, _, target in routes
        )
    assert set(edges(graph, "audio_frame")) == {
        ("websocket_server", "pcm_frame", "stt"),
        ("tts", "pcm_frame", "websocket_server"),
    }
    data_routes = set(edges(graph, "data"))
    assert {
        ("stt", "asr_result", "bridge"),
        ("stt", "asr_result", "websocket_server"),
        ("agora_mind", "agora_mind_event", "bridge"),
        ("agora_mind", "agora_mind_event", "websocket_server"),
        ("tts", "tts_audio_end", "websocket_server"),
        ("tts", "tts_text_result", "websocket_server"),
        ("bridge", "error", "websocket_server"),
    } <= data_routes
    socket_api = json.loads(
        (EXTENSIONS / "websocket_server/manifest.json").read_text()
    )["api"]
    assert {
        name for _, name, target in data_routes if target == "websocket_server"
    } <= {item["name"] for item in socket_api["data_in"]}
    bridge_api = json.loads(
        (EXTENSIONS / "agora_mind_bridge_python/manifest.json").read_text()
    )["api"]
    assert set(edges(graph, "cmd")) == {
        ("websocket_server", command["name"], "bridge")
        for command in bridge_api["cmd_in"]
    }
    # The bridge already addresses TTS directly. A second route duplicates output.
    assert not any(
        source == "bridge" and name == "tts_text_input"
        for source, name, _ in data_routes
    )


def test_bridge_package_registers_its_addon(modules, monkeypatch):
    registered = []

    def register(name):
        def decorator(addon):
            registered.append((name, addon))
            return addon

        return decorator

    monkeypatch.setattr(modules.runtime, "Addon", object, raising=False)
    monkeypatch.setattr(
        modules.runtime, "register_addon_as_extension", register, raising=False
    )
    alias = "_fdb_test_registration"
    spec = importlib.util.spec_from_file_location(
        alias, EXTENSIONS / "agora_mind_bridge_python/__init__.py"
    )
    package = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, alias, package)
    spec.loader.exec_module(package)
    assert len(registered) == 1
    name, addon_class = registered[0]
    assert name == "agora_mind_bridge_python"
    ten = Mock()
    addon_class().on_create_instance(ten, "bridge", "context")
    instance, context = ten.on_create_instance_done.call_args.args
    assert instance.__class__.__name__ == "AgoraMindBridgeExtension"
    assert context == "context"


@pytest.mark.asyncio
async def test_graph_session_asr_turn_tts_and_cleanup(graph, modules):
    socket = modules.websocket.WebsocketServerExtension("websocket_server")
    socket.config = modules.websocket.WebSocketServerConfig()
    socket.ws_server = Mock(broadcast=AsyncMock())
    bridge = modules.bridge.AgoraMindBridgeExtension("bridge")
    bridge.config.example_id = "case-1"
    commands, tts_input = [], []
    instances = {"websocket_server": socket, "bridge": bridge}
    environments = {}

    async def send_data(source, message):
        destinations = [dest[2] for dest in message.destinations] or [
            target
            for origin, name, target in edges(graph, "data")
            if origin == source and name == message.name
        ]
        for target in destinations:
            if target == "tts":
                tts_input.append(message)
            else:
                await instances[target].on_data(environments[target], message)

    async def send_cmd(source, command):
        destinations = [dest[2] for dest in command.destinations] or [
            target
            for origin, name, target in edges(graph, "cmd")
            if origin == source and name == command.name
        ]
        assert len(destinations) == 1
        target = destinations[0]
        if target == "agora_mind":
            commands.append(command)
            response = (
                {"type": "session.created", "session_id": 7}
                if command.name == "create_session"
                else {"type": "ok"}
            )
            result = Result.create(StatusCode.OK, command)
            result.set_property_string("response_json", json.dumps(response))
            return result, None
        await bridge.on_cmd(environments["bridge"], command)
        return environments["bridge"].return_result.await_args.args[0], None

    for name, instance in instances.items():
        environment = Mock(return_result=AsyncMock())
        environment.send_cmd = lambda command, source=name: send_cmd(
            source, command
        )
        environment.send_data = lambda message, source=name: send_data(
            source, message
        )
        instance.ten_env = environments[name] = environment

    assert (
        await socket._on_cmd_received(
            "create_workspace", {"profile": "benchmark.fdb_v3"}
        )
    )["status"] == 0
    properties = {
        "model": "custom",
        "system_prompt_path": "prompts/fdb_v3.md",
        "input_merge_policy_json": '{"batch":"disabled","history_tail":"disabled"}',
        "input_format": "pure_text",
        "trigger_mode": "normal",
    }
    assert (await socket._on_cmd_received("create_session", properties))[
        "status"
    ] == 0
    assert bridge.session_id == 7
    assert commands[-1].properties == properties
    interim = Message("asr_result", {"text": "Book", "final": False})
    final = Message("asr_result", {"text": "Book the flight", "final": True})
    for message in (interim, final, final):
        await send_data("stt", message)
    assert [cmd.name for cmd in commands].count("submit_user_input") == 1
    assert (
        json.loads(commands[-1].properties["input_json"])["text"]
        == "Book the flight"
    )

    event = Message(
        "agora_mind_event",
        {
            "event_json": json.dumps(
                {
                    "type": "workspace.event",
                    "event": {
                        "type": "session_turn_completed",
                        "session_id": 7,
                        "source": {"type": "top_level"},
                        "input_sequence_range": {"first": 1, "last": 1},
                        "result": [{"type": "text", "text": "Flight booked."}],
                    },
                }
            )
        },
    )
    await send_data("agora_mind", event)
    await send_data("agora_mind", event)
    assert len(tts_input) == 1
    assert tts_input[0].name == "tts_text_input"
    assert tts_input[0].properties["text"] == "Flight booked."
    assert tts_input[0].properties["metadata"]["example_id"] == "case-1"
    # TEN's TTS interface requires a string Session ID in metadata, while
    # Agora Mind commands use a uint64 Session ID.
    assert tts_input[0].properties["metadata"]["session_id"] == "7"
    end = Message(
        "tts_audio_end",
        {
            "request_id": tts_input[0].properties["request_id"],
            "audio_duration": 100,
        },
    )
    await send_data("tts", end)
    assert socket.ws_server.broadcast.await_args.args[0] == {
        "type": "data",
        "name": "tts_audio_end",
        "data": end.properties,
    }
    await socket._on_cmd_received("delete_session", {"session_id": 7})
    assert bridge.session_id is None
