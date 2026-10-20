#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import base64
import json
import socket

import websockets

from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Cmd,
    StatusCode,
    LogLevel,
    TenError,
    TenErrorCode,
    CmdResult,
    Data,
)


class ExtensionTesterBasic(AsyncExtensionTester):
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        new_cmd = Cmd.create("hello_world")

        ten_env.log(LogLevel.DEBUG, "send hello_world")
        result, err = await ten_env.send_cmd(new_cmd)
        if (
            err is not None
            or result is None
            or result.get_status_code() != StatusCode.OK
        ):
            ten_env.stop_test(
                TenError.create(
                    TenErrorCode.ErrorCodeGeneric,
                    "Failed to send hello_world",
                )
            )
        else:
            ten_env.stop_test()

        ten_env.log(LogLevel.DEBUG, "tester on_start_done")


def test_basic():
    tester = ExtensionTesterBasic()
    tester.set_test_mode_single("websocket_server")
    err = tester.run()
    if err is not None:
        assert False, err.error_message()


class ExtensionTesterWebSocket(AsyncExtensionTester):
    """Exercise commands, data and PCM through the real TEN boundary."""

    def __init__(self, port):
        super().__init__()
        self.port = port

    async def on_cmd(self, ten_env, cmd):
        assert cmd.get_name() == "create_session"
        assert cmd.get_property_string("model")[0] == "custom"
        event = Data.create("tts_audio_end")
        event.set_property_string("request_id", "case-1-tts")
        await ten_env.send_data(event)
        result = CmdResult.create(StatusCode.OK, cmd)
        result.set_property_string("response_json", '{"session_id":7}')
        await ten_env.return_result(result)

    async def on_audio_frame(self, ten_env, frame):
        assert frame.get_sample_rate() == 16000
        assert frame.get_number_of_channels() == 1
        assert frame.get_bytes_per_sample() == 2
        await ten_env.send_audio_frame(frame)

    async def on_start(self, ten_env):
        try:
            await asyncio.wait_for(self.exchange(), 5)
        except Exception as error:
            ten_env.stop_test(
                TenError.create(TenErrorCode.ErrorCodeGeneric, str(error))
            )
            return
        ten_env.stop_test()

    async def exchange(self):
        # The tester and extension can start concurrently.
        for attempt in range(100):
            try:
                client = await websockets.connect(f"ws://127.0.0.1:{self.port}")
                break
            except OSError:
                if attempt == 99:
                    raise
                await asyncio.sleep(0.01)
        async with client:
            await client.send(
                json.dumps(
                    {
                        "type": "cmd",
                        "name": "create_session",
                        "request_id": "case-1",
                        "data": {"model": "custom"},
                    }
                )
            )
            messages = [json.loads(await client.recv()) for _ in range(2)]
            reply = next(msg for msg in messages if msg["type"] == "cmd_result")
            assert reply["request_id"] == "case-1"
            assert reply["status"] == 0
            assert json.loads(reply["data"]["response_json"])["session_id"] == 7
            event = next(msg for msg in messages if msg["type"] == "data")
            assert event["name"] == "tts_audio_end"
            pcm = b"\x00\x00\xff\x7f" * 160
            await client.send(
                json.dumps(
                    {
                        "audio": base64.b64encode(pcm).decode(),
                        "metadata": {"example_id": "case-1"},
                    }
                )
            )
            audio = json.loads(await client.recv())
            assert audio["type"] == "audio"
            assert base64.b64decode(audio["audio"]) == pcm
            assert audio["metadata"]["example_id"] == "case-1"
            assert audio["metadata"]["sample_rate"] == 16000


def test_websocket_ten_roundtrip():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    tester = ExtensionTesterWebSocket(port)
    tester.set_test_mode_single("websocket_server", json.dumps({"port": port}))
    error = tester.run()
    assert error is None, error.error_message() if error else ""
