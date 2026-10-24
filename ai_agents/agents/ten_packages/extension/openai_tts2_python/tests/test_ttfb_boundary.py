"""Verify openai tts2 python TTFB at the public provider boundary."""

import pytest

import json
import threading
import time
import asyncio
import httpx
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


def test_ttfb_excludes_connection_and_tail_audio_wait():
    times = {}

    class AudioStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.03)
            times["received"] = time.monotonic_ns()
            yield b"\x01\x00" * 1600
            await asyncio.sleep(0.1)
            yield b"\x02\x00" * 1600

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            await asyncio.sleep(0.15)
            times["sent"] = time.monotonic_ns()
            trace = request.extensions.get("trace")
            if trace:
                await trace("http11.send_request_body.started", {})
            return httpx.Response(200, stream=AudioStream())

    real_client = httpx.AsyncClient
    with patch(
        "ten_packages.extension.openai_tts2_python.openai_tts.AsyncClient",
        side_effect=lambda **kwargs: real_client(transport=Transport()),
    ):
        tester = TimingTester()
        try:
            tester.set_test_mode_single(
                "openai_tts2_python",
                json.dumps({"params": {"api_key": "mock"}}),
            )
            error = tester.run()
            assert error is None, error.error_message()
            expected = (times["received"] - times["sent"]) / 1_000_000
            assert len(tester.reported) == 1
            assert abs(tester.reported[0] - expected) <= 5, (
                tester.reported,
                expected,
            )
        finally:
            if tester.timer:
                tester.timer.cancel()


pytestmark = pytest.mark.api
