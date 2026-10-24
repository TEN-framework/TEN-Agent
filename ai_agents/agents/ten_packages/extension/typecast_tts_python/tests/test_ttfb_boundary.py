"""Verify typecast tts python TTFB at the public provider boundary."""

import pytest

import json
import threading
import time
import asyncio
import base64
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


EXTENSION_NAME = "typecast_tts_python"


def test_ttfb_measured_before_output_processing():
    times = {}
    import io
    import wave

    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(32000)
        audio.writeframes(b"\x01\x00" * 1600)

    class Provider:
        async def __aenter__(self):
            await asyncio.sleep(0.15)
            return self

        async def __aexit__(self, *args):
            pass

        async def text_to_speech_stream(self, request, chunk_size):
            times["sent"] = time.monotonic_ns()
            await asyncio.sleep(0.02)
            times["received"] = time.monotonic_ns()
            yield output.getvalue()

    target = (
        "ten_packages.extension.typecast_tts_python.typecast_tts.AsyncTypecast"
    )
    replacement = lambda **kwargs: Provider()
    config = {
        "params": {"api_key": "mock", "voice_id": "tc_62a31c3b13e7a00007f0b7de"}
    }
    with patch(target, replacement):
        tester = TimingTester()
        try:
            tester.set_test_mode_single(EXTENSION_NAME, json.dumps(config))
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
