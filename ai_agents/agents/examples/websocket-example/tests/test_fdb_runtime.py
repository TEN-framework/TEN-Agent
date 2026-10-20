"""Run the packaged FDB graph against local service fixtures on Linux."""

import asyncio
import base64
import json
import os
import socket
import subprocess
import sys
import urllib.request
from uuid import uuid4

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

IMAGE = os.environ.get("FDB_RUNTIME_IMAGE")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not IMAGE or sys.platform != "linux",
        reason="set FDB_RUNTIME_IMAGE to test a local image on Linux",
    ),
]
PCM = b"\x00\x00\xff\x7f" * 1600
MERGE_POLICY = {"batch": "disabled", "history_tail": "disabled"}
ACTION_SCOPE = {"type": "only", "actions": ["book_flight"]}


def docker(*arguments):
    result = subprocess.run(
        ["docker", *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    return result.stdout


async def http(api, path, properties=None):
    def request():
        body = None if properties is None else json.dumps(properties).encode()
        message = urllib.request.Request(
            api + path,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(message, timeout=10) as response:
            return json.load(response)

    return await asyncio.to_thread(request)


async def eventually(operation):
    async def retry():
        while True:
            try:
                return await operation()
            except OSError:
                await asyncio.sleep(0.1)

    return await asyncio.wait_for(retry(), 15)


class Services:
    """Wire replies for the external services; the TEN addons remain real."""

    def __init__(self):
        self.commands = []

    async def handle(self, websocket):
        path = websocket.request.path
        async for raw in websocket:
            if path.startswith("/asr"):
                if isinstance(raw, bytes):
                    result = {
                        "type": "Results",
                        "is_final": True,
                        "speech_final": True,
                        "start": 0,
                        "duration": 0.02,
                        "channel": {
                            "alternatives": [
                                {"transcript": "Book the flight", "words": []}
                            ]
                        },
                    }
                    # Both finals describe the same input audio.
                    await websocket.send(json.dumps(result))
                    await websocket.send(json.dumps(result))
            elif path.startswith("/tts"):
                if json.loads(raw).get("text") == "":
                    await websocket.send(
                        json.dumps(
                            {
                                "audio": base64.b64encode(PCM).decode(),
                                "isFinal": True,
                            }
                        )
                    )
            else:
                await self.agora_mind(websocket, json.loads(raw))

    async def agora_mind(self, websocket, command):
        self.commands.append(command)
        name = command["type"]
        if name == "workspace.create":
            assert command["profile"] == "benchmark.fdb_v3"
            response = {"type": "workspace.created", "workspace_id": 1}
        elif name == "session.create":
            assert command["system_prompt_path"] == "prompts/fdb_v3.md"
            assert command["model_action_scope"] == ACTION_SCOPE
            assert command["input_merge_policy"] == MERGE_POLICY
            response = {
                "type": "session.created",
                "session_id": 7,
                "session_name": "runtime-test",
                "input_format": "pure_text",
                "trigger_mode": "normal",
                "input_merge_policy": MERGE_POLICY,
            }
        elif name == "session.user_input":
            assert command["session_id"] == 7
            assert command["input"]["text"] == "Book the flight"
            response = {
                "type": "session.user_input.accepted",
                "session_id": 7,
                "input_sequence": 1,
            }
        else:
            assert name == "session.delete", command
            response = {"type": "session.delete.completed", "session_id": 7}
        await websocket.send(json.dumps(response))
        if name == "session.user_input":
            event = {
                "type": "workspace.event",
                "event": {
                    "type": "session_turn_completed",
                    "session_id": 7,
                    "session_name": "runtime-test",
                    "source": {"type": "top_level"},
                    "input_sequence_range": {"first": 1, "last": 1},
                    "input_sources": [
                        {"input_sequence": 1, "text": "Book the flight"}
                    ],
                    "result": [{"type": "text", "text": "Flight booked."}],
                },
            }
            await websocket.send(json.dumps(event))
            await websocket.send(json.dumps(event))


@pytest_asyncio.fixture
async def runtime():
    name = f"ten-fdb-test-{uuid4().hex[:12]}"
    services = Services()
    with socket.socket() as api_socket, socket.socket() as audio_socket:
        api_socket.bind(("127.0.0.1", 0))
        audio_socket.bind(("127.0.0.1", 0))
        api_port = api_socket.getsockname()[1]
        audio_port = audio_socket.getsockname()[1]
    api = f"http://127.0.0.1:{api_port}"
    async with serve(services.handle, "127.0.0.1", 0) as server:
        endpoint = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        environment = {
            "SERVER_PORT": str(api_port),
            "LOG_PATH": "/tmp/ten-fdb",
            "LOG_STDOUT": "true",
            "WORKERS_MAX": "1",
            "WORKER_QUIT_TIMEOUT_SECONDS": "120",
            "AGORA_APP_ID": "0" * 32,
            "DEEPGRAM_API_KEY": "runtime-test",
            "ELEVENLABS_TTS_KEY": "runtime-test",
            "AGORA_MIND_ENDPOINT": endpoint + "/mind",
        }
        arguments = ["create", "--pull=never", "--name", name, "--network=host"]
        for key, value in environment.items():
            arguments.extend(["-e", f"{key}={value}"])
        docker(*arguments, IMAGE)
        try:
            docker("start", name)
            await eventually(lambda: http(api, "/health"))
            yield api, audio_port, endpoint, services
        finally:
            try:
                print(docker("logs", "--tail", "100", name))
            finally:
                docker("rm", "-f", name)


async def command(websocket, name, properties):
    await websocket.send(
        json.dumps(
            {
                "type": "cmd",
                "name": name,
                "request_id": name,
                "data": properties,
            }
        )
    )
    while True:
        result = json.loads(await websocket.recv())
        if result["type"] == "cmd_result":
            assert result["request_id"] == name
            assert result["status"] == 0, result
            return json.loads(result["data"]["response_json"])


async def run_case(runtime, example_id):
    api, port, endpoint, services = runtime
    first_command = len(services.commands)
    result = await http(
        api,
        "/start",
        {
            "request_id": example_id,
            "channel_name": example_id,
            "graph_name": "fdb_v3",
            "timeout": 120,
            "properties": {
                "websocket_server": {"port": port},
                "bridge": {"example_id": example_id},
                "stt": {"params": {"url": endpoint + "/asr"}},
                "tts": {"params": {"base_url": endpoint + "/tts"}},
            },
        },
    )
    assert result["code"] == "0", result
    client = await eventually(lambda: connect(f"ws://127.0.0.1:{port}"))
    async with client:
        await command(
            client, "create_workspace", {"profile": "benchmark.fdb_v3"}
        )
        session = await command(
            client,
            "create_session",
            {
                "model": "custom",
                "system_prompt_path": "prompts/fdb_v3.md",
                "model_action_scope_json": json.dumps(ACTION_SCOPE),
                "input_merge_policy_json": json.dumps(MERGE_POLICY),
                "input_format": "pure_text",
                "trigger_mode": "normal",
            },
        )
        assert session["session_id"] == 7
        await client.send(
            json.dumps(
                {
                    "audio": base64.b64encode(PCM[:640]).decode(),
                    "metadata": {"example_id": example_id},
                }
            )
        )
        output = bytearray()
        events = []
        while True:
            event = json.loads(await client.recv())
            if event["type"] == "audio":
                assert event["metadata"]["sample_rate"] == 16000
                assert event["metadata"]["channels"] == 1
                assert event["metadata"]["bytes_per_sample"] == 2
                assert event["metadata"]["session_id"] == "7"
                assert event["metadata"]["example_id"] == example_id
                output.extend(base64.b64decode(event["audio"]))
            elif event["type"] == "data":
                events.append(event["name"])
                if event["name"] == "tts_audio_end":
                    assert event["data"]["request_id"] == "fdb-tts-7-1"
                    assert event["data"]["reason"] == 1  # REQUEST_END
                    assert (
                        event["data"]["request_total_audio_duration_ms"] == 200
                    )
                    break
        assert output == PCM
        assert "asr_result" in events
        assert events.count("tts_audio_start") == 1
        await command(client, "delete_session", {"session_id": 7})
    stopped = await http(
        api,
        "/stop",
        {"request_id": example_id, "channel_name": example_id},
    )
    assert stopped["code"] == "0", stopped
    workers = await http(api, "/list")
    assert example_id not in json.dumps(workers), workers
    assert [cmd["type"] for cmd in services.commands[first_command:]] == [
        "workspace.create",
        "session.create",
        "session.user_input",
        "session.delete",
    ]


async def test_native_graph_pcm_roundtrip_and_case_isolation(runtime):
    async def exercise():
        graphs = await http(runtime[0], "/graphs")
        assert "fdb_v3" in json.dumps(graphs), graphs
        for example_id in ("fdb-native-1", "fdb-native-2"):
            await run_case(runtime, example_id)

    # Metrics and reconnect events must not extend the test indefinitely.
    await asyncio.wait_for(exercise(), 45)
