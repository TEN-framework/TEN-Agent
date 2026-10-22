"""Fast tests for the WebSocket boundary used by the FDB graph."""

import asyncio
import base64
import json
from unittest.mock import AsyncMock, Mock

import pytest
import websockets

from conftest import Message, Result, StatusCode


@pytest.mark.asyncio
async def test_socket_accepts_pcm_and_correlates_command_results(modules, env):
    manager_module = modules.websocket.WebSocketServerManager
    audio = AsyncMock()
    command = AsyncMock(return_value={"status": 0, "data": {"ok": True}})
    server = manager_module("127.0.0.1", 0, env, audio, command)
    await server.start()
    try:
        port = server.server.sockets[0].getsockname()[1]
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            pcm = b"\x00\x00\xff\x7f" * 160
            await client.send(
                json.dumps({"audio": base64.b64encode(pcm).decode()})
            )
            await client.send(
                json.dumps(
                    {
                        "type": "cmd",
                        "name": "create_session",
                        "request_id": "case-1",
                        "data": {"system_prompt_path": "prompts/fdb_v3.md"},
                    }
                )
            )
            reply = json.loads(await asyncio.wait_for(client.recv(), 1))
            assert reply == {
                "type": "cmd_result",
                "name": "create_session",
                "request_id": "case-1",
                "status": 0,
                "data": {"ok": True},
            }
            assert audio.await_args.args[0].pcm_data == pcm
            command.assert_awaited_once_with(
                "create_session", {"system_prompt_path": "prompts/fdb_v3.md"}
            )
            async with websockets.connect(f"ws://127.0.0.1:{port}") as second:
                assert json.loads(await second.recv())["type"] == "error"
    finally:
        await server.stop()
    assert server.get_client_count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,properties",
    [
        ("create_workspace", {"profile": "fdb"}),
        ("create_session", {"model": "custom"}),
        ("flush_session", {"session_id": 7}),
        ("set_session_debug", {"session_id": 7, "enabled": True}),
        ("delete_session", {"session_id": 7}),
    ],
)
async def test_all_session_control_commands_preserve_properties(
    modules, env, name, properties
):
    command = AsyncMock(return_value={"status": 0, "data": {"ok": True}})
    server = modules.websocket.WebSocketServerManager(
        "127.0.0.1", 0, env, on_cmd_callback=command
    )
    await server.start()
    try:
        port = server.server.sockets[0].getsockname()[1]
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            await client.send(
                json.dumps(
                    {
                        "type": "cmd",
                        "name": name,
                        "request_id": f"request-{name}",
                        "data": properties,
                    }
                )
            )
            result = json.loads(await asyncio.wait_for(client.recv(), 1))
            assert result["type"] == "cmd_result"
            assert result["name"] == name
            assert result["request_id"] == f"request-{name}"
            assert result["status"] == 0
            command.assert_awaited_once_with(name, properties)
    finally:
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"type": "cmd", "name": ""},
        {"type": "cmd", "name": "create_session", "data": []},
    ],
)
async def test_malformed_messages_do_not_reach_ten(modules, env, payload):
    command = AsyncMock()
    server = modules.websocket.WebSocketServerManager(
        "127.0.0.1", 0, env, on_cmd_callback=command
    )
    client = Mock(send=AsyncMock())
    await server._process_message(json.dumps(payload), client, "client")
    assert json.loads(client.send.await_args.args[0])["type"] == "error"
    command.assert_not_awaited()


@pytest.mark.asyncio
async def test_ten_command_result_and_timeout_are_returned(modules, env):
    extension = modules.websocket.WebsocketServerExtension("websocket_server")
    extension.ten_env = env
    extension.config = modules.websocket.WebSocketServerConfig(
        command_timeout_ms=10
    )
    result = Result.create(StatusCode.OK, Message("create_session"))
    result.properties = {
        "response_json": '{"type":"session.created","session_id":7}'
    }
    env.send_cmd.return_value = result, None
    reply = await extension._on_cmd_received(
        "create_session", {"model": "custom"}
    )
    assert reply == {"status": 0, "data": result.properties}
    assert env.send_cmd.await_args.args[0].properties == {"model": "custom"}
    assert env.send_cmd.await_args.args[0].destinations == []

    async def pending(_cmd):
        await asyncio.Event().wait()

    env.send_cmd.side_effect = pending
    reply = await extension._on_cmd_received("create_session", {})
    assert reply["status"] == StatusCode.ERROR
    assert reply["data"]["error"] == "command timed out"
    env.send_cmd.side_effect = None
    env.send_cmd.return_value = None, "unrouted command"
    assert (await extension._on_cmd_received("unknown", {}))[
        "status"
    ] == StatusCode.ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    ["text_data", "asr_result", "agora_mind_event", "tts_audio_end", "error"],
)
async def test_graph_data_reaches_websocket_without_conversion(
    modules, env, name
):
    extension = modules.websocket.WebsocketServerExtension("websocket_server")
    extension.ws_server = Mock(broadcast=AsyncMock())
    payload = {"text": "已完成", "metadata": {"example_id": "case-1"}}
    await extension.on_data(env, Message(name, payload))
    extension.ws_server.broadcast.assert_awaited_once_with(
        {"type": "data", "name": name, "data": payload}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "channels,sample_width,pcm",
    [(1, 2, b""), (1, 2, b"\x00"), (2, 2, b"\x00\x00"), (1, 4, b"\x00\x00")],
)
async def test_incomplete_pcm_is_rejected_before_frame_allocation(
    modules, env, channels, sample_width, pcm
):
    extension = modules.websocket.WebsocketServerExtension("websocket_server")
    extension.ten_env = env
    extension.config = modules.websocket.WebSocketServerConfig(
        channels=channels, bytes_per_sample=sample_width
    )
    frame = Mock()
    frame.lock_buf.return_value = bytearray(len(pcm))
    modules.runtime.AudioFrame.create.return_value = frame
    audio = modules.websocket.AudioData(pcm, "client", {})
    with pytest.raises(ValueError, match="complete PCM sample frames"):
        await extension._on_audio_received(audio)
    modules.runtime.AudioFrame.create.assert_not_called()
    env.send_audio_frame.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_base64_is_rejected_before_audio_callback(modules, env):
    callback = AsyncMock()
    server = modules.websocket.WebSocketServerManager(
        "127.0.0.1", 0, env, on_audio_callback=callback
    )
    client = Mock(send=AsyncMock())
    await server._process_message(
        json.dumps({"audio": "%%%="}), client, "client"
    )
    error = json.loads(client.send.await_args.args[0])
    assert error["type"] == "error"
    assert "Invalid base64 audio data" in error["error"]
    callback.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [None, [], "case-1", 7])
async def test_non_object_metadata_is_rejected_before_audio_callback(
    modules, env, metadata
):
    callback = AsyncMock()
    server = modules.websocket.WebSocketServerManager(
        "127.0.0.1", 0, env, on_audio_callback=callback
    )
    client = Mock(send=AsyncMock())
    await server._process_message(
        json.dumps(
            {
                "audio": base64.b64encode(b"\x00\x00").decode(),
                "metadata": metadata,
            }
        ),
        client,
        "client",
    )
    error = json.loads(client.send.await_args.args[0])
    assert error["type"] == "error"
    assert "metadata must be a JSON object" in error["error"]
    callback.assert_not_awaited()
