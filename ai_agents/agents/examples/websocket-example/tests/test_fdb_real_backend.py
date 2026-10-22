"""Opt-in integration with a compiled Agora Mind server and its FDB tools."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
from types import SimpleNamespace

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from test_fdb_runtime import (
    IMAGE,
    PCM,
    command,
    command_result,
    eventually,
    http,
    runtime,
    send_audio,
)

AGORA_ROOT = os.environ.get("FDB_AGORA_MIND_ROOT")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not IMAGE or not AGORA_ROOT,
        reason="set FDB_RUNTIME_IMAGE and FDB_AGORA_MIND_ROOT for real-backend tests",
    ),
]


class ModelProxy(BaseHTTPRequestHandler):
    """Script only model replies; the real server executes the FDB action."""

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.requests.append(json.loads(body))
        output = (
            [
                {
                    "type": "action",
                    "name": "book_flight",
                    "arguments": {"passenger_name": "测试乘客"},
                }
            ]
            if len(self.server.requests) == 1
            else [{"type": "text", "text": "Flight booked."}]
        )
        response = json.dumps(
            {
                "choices": [
                    {
                        "message": {"content": json.dumps(output)},
                        "finish_reason": "stop",
                    }
                ]
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args):
        pass


@pytest_asyncio.fixture
async def agora_backend():
    root = Path(AGORA_ROOT).resolve()
    binary = root / "target/debug/agora-mind-web-server"
    profiles = root / "examples/fdb_workspace_profiles.json"
    assert binary.is_file(), f"build {binary} before running this test"
    assert profiles.is_file(), profiles
    assert json.loads(profiles.read_text())["default_profile"] == "fdb"

    # The server derives its writable runtime location from its executable.
    # Keep its copy, databases and temporary prompt inside this checkout.
    cache = Path(__file__).resolve().parents[4] / ".cache"
    cache.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="fdb-real-", dir=cache) as temporary:
        work = Path(temporary)
        executable = work / binary.name
        shutil.copy2(binary, executable)
        prompt = work / "resources/prompts/runtime-test.md"
        prompt.parent.mkdir(parents=True)
        prompt.write_text("Runtime graph integration fixture.")

        proxy = ThreadingHTTPServer(("127.0.0.1", 0), ModelProxy)
        proxy.requests = []
        thread = Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        with socket.socket() as reserve:
            reserve.bind(("127.0.0.1", 0))
            port = reserve.getsockname()[1]
        environment = os.environ.copy()
        for key in list(environment):
            if key.lower() in {
                "http_proxy",
                "https_proxy",
                "all_proxy",
                "no_proxy",
            }:
                environment.pop(key)
        proxy_url = f"http://127.0.0.1:{proxy.server_address[1]}"
        environment.update(
            HTTP_PROXY=proxy_url,
            HTTPS_PROXY=proxy_url,
            NO_PROXY="localhost,127.0.0.1",
            OTEL_SDK_DISABLED="true",
            AGORA_MIND_MODEL_IO_CAPTURE="off",
            AGORA_MIND_WORKSPACE_PROFILES_CONFIG=str(profiles),
            AGORA_MIND_FDB_EXAMPLE_ID="fdb-real-case",
            AGORA_MIND_RESOURCES_ROOT=str(work / "resources"),
        )
        with (work / "server.log").open("wb") as logs:
            process = subprocess.Popen(
                [str(executable), "--bind", f"127.0.0.1:{port}"],
                cwd=work,
                env=environment,
                stdout=logs,
                stderr=subprocess.STDOUT,
            )
            try:

                async def ready():
                    assert process.poll() is None, (
                        work / "server.log"
                    ).read_text()
                    _, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.close()
                    await writer.wait_closed()

                await eventually(ready)
                yield SimpleNamespace(
                    endpoint=f"ws://127.0.0.1:{port}", requests=proxy.requests
                )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                proxy.shutdown()
                proxy.server_close()
                thread.join(timeout=2)
                print((work / "server.log").read_text())


async def test_real_fdb_profile_tool_and_tts(runtime, agora_backend):
    api, port, services_endpoint, _ = runtime
    example_id = "fdb-real-case"

    async def exercise():
        started = await http(
            api,
            "/start",
            {
                "request_id": example_id,
                "channel_name": example_id,
                "graph_name": "fdb_v3",
                "properties": {
                    "websocket_server": {"port": port},
                    "bridge": {"example_id": example_id},
                    "agora_mind": {"endpoint": agora_backend.endpoint},
                    "stt": {"params": {"url": services_endpoint + "/asr"}},
                    "tts": {"params": {"base_url": services_endpoint + "/tts"}},
                },
            },
        )
        assert started["code"] == "0", started
        try:
            client = await eventually(lambda: connect(f"ws://127.0.0.1:{port}"))
            async with client:
                wrong = await command_result(
                    client, "create_workspace", {"profile": "benchmark.fdb_v3"}
                )
                assert wrong["status"] != 0, wrong
                await command(client, "create_workspace", {"profile": "fdb"})
                properties = {
                    "model": "custom",
                    "system_prompt_path": "prompts/missing.md",
                    "model_action_scope_json": json.dumps(
                        {"type": "only", "actions": ["book_flight"]}
                    ),
                    "input_merge_policy_json": json.dumps(
                        {"batch": "disabled", "history_tail": "disabled"}
                    ),
                    "input_format": "pure_text",
                    "trigger_mode": "normal",
                }
                missing = await command_result(
                    client, "create_session", properties
                )
                assert missing["status"] != 0, missing
                properties["system_prompt_path"] = "prompts/runtime-test.md"
                session = await command(client, "create_session", properties)
                session_id = session["session_id"]
                await send_audio(client, example_id)
                output = bytearray()
                transcript_seen = False
                while True:
                    event = json.loads(await client.recv())
                    if event["type"] == "audio":
                        assert event["metadata"]["session_id"] == str(
                            session_id
                        )
                        assert event["metadata"]["example_id"] == example_id
                        output.extend(
                            __import__("base64").b64decode(event["audio"])
                        )
                    elif event["type"] == "data":
                        if event["name"] == "agora_mind_event":
                            payload = json.loads(event["data"]["event_json"])
                            completed = payload.get("event", {})
                            if (
                                completed.get("type")
                                == "session_turn_completed"
                            ):
                                assert completed["result"] == [
                                    {"type": "text", "text": "Flight booked."}
                                ]
                                transcript_seen = True
                        if event["name"] == "tts_audio_end":
                            assert event["data"]["reason"] == 1
                            break
                assert output == PCM
                assert transcript_seen
                assert len(agora_backend.requests) == 2
                assert "Runtime graph integration fixture." in json.dumps(
                    agora_backend.requests[0]
                )
                assert "B789" in json.dumps(agora_backend.requests[1])
                assert "测试乘客" in json.dumps(
                    agora_backend.requests[1], ensure_ascii=False
                )
                await command(
                    client, "delete_session", {"session_id": session_id}
                )
        finally:
            stopped = await http(
                api,
                "/stop",
                {"request_id": example_id, "channel_name": example_id},
            )
            assert stopped["code"] == "0", stopped

    await asyncio.wait_for(exercise(), 30)
