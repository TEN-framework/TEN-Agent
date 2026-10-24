"""Verify murf tts python TTFB at the public provider boundary."""

import pytest

import json
import threading
import time
import asyncio
import base64
import websockets
from types import SimpleNamespace
from unittest.mock import patch

from ten_runtime import Data, ExtensionTester, TenError, TenErrorCode


class TimingTester(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.reported = []
        self.audio = False
        self.timer = None

    def on_start(self, env):
        self.timer = threading.Timer(
            0.8,
            lambda: env.stop_test(
                TenError.create(
                    TenErrorCode.ErrorCodeGeneric, "Missing audio or TTFB"
                ),
            ),
        )
        self.timer.start()
        data = Data.create("tts_text_input")
        data.set_property_from_json(
            "",
            json.dumps(
                {
                    "request_id": "sdk-first-audio",
                    "text": "Hello.",
                    "text_input_end": True,
                    "metadata": {"turn_id": 1},
                }
            ),
        )
        env.send_data(data)
        env.on_start_done()

    def on_data(self, env, data):
        raw, _ = data.get_property_to_json("")
        payload = json.loads(raw)
        if data.get_name() == "error":
            env.stop_test(
                TenError.create(TenErrorCode.ErrorCodeGeneric, "Provider error")
            )
        if data.get_name() == "metrics" and "ttfb" in payload.get(
            "metrics", {}
        ):
            self.reported.append(payload["metrics"]["ttfb"])
            self.complete(env)

    def on_audio_frame(self, env, frame):
        if frame.get_buf():
            self.audio = True
            self.complete(env)

    def complete(self, env):
        if self.audio and self.reported:
            self.timer.cancel()
            env.stop_test()


def test_ttfb_timestamp_exists_while_send_is_in_flight():
    ready = threading.Event()
    port = []
    loop = asyncio.new_event_loop()
    times = {}

    async def provider(ws):
        async for raw in ws:
            message = json.loads(raw)
            if message.get("text"):
                times["sent"] = time.monotonic_ns()
                await asyncio.sleep(0.02)
                times["received"] = time.monotonic_ns()
                await ws.send(
                    json.dumps(
                        {
                            "context_id": message["context_id"],
                            "audio": base64.b64encode(
                                b"\x00" * 44 + b"\x01\x00" * 1600
                            ).decode(),
                        }
                    )
                )

    def run_server():
        asyncio.set_event_loop(loop)

        async def start():
            return await websockets.serve(provider, "127.0.0.1", 0)

        server = loop.run_until_complete(start())
        port.append(server.sockets[0].getsockname()[1])
        ready.set()
        loop.run_forever()
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    assert ready.wait(0.5)
    original_connect = websockets.connect
    base = websockets.ClientConnection

    class SlowSend(base):
        async def send(self, raw, *args, **kwargs):
            await super().send(raw, *args, **kwargs)
            if json.loads(raw).get("text"):
                await asyncio.sleep(0.1)

    def connect(*args, **kwargs):
        kwargs["create_connection"] = SlowSend
        return original_connect(*args, **kwargs)

    with patch(
        "ten_packages.extension.murf_tts_python.murf_tts.websockets.connect",
        connect,
    ):
        tester = TimingTester()
        try:
            tester.set_test_mode_single(
                "murf_tts_python",
                json.dumps(
                    {
                        "base_url": f"ws://127.0.0.1:{port[0]}",
                        "params": {"api_key": "mock", "voice_id": "mock"},
                    }
                ),
            )
            error = tester.run()
            assert error is None, error.error_message()
            assert len(tester.reported) == 1
            expected = (times["received"] - times["sent"]) / 1_000_000
            assert abs(tester.reported[0] - expected) <= 10, (
                tester.reported,
                expected,
            )
        finally:
            if tester.timer:
                tester.timer.cancel()
            loop.call_soon_threadsafe(loop.stop)
            thread.join(0.5)


pytestmark = pytest.mark.api
