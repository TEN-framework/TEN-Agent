"""Verify cosy tts python TTFB at the public provider boundary."""

import pytest

import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from ten_runtime import Data, ExtensionTester, TenError, TenErrorCode


class TimingTester(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.reported = []
        self.audio = False
        self.timer = None
        self.stage = "warmup"

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
        text = Data.create("tts_text_input")
        text.set_property_from_json(
            "",
            json.dumps(
                {
                    "request_id": "warmup",
                    "text": "Warm up.",
                    "text_input_end": False,
                }
            ),
        )
        env.send_data(text)
        env.on_start_done()

    def on_data(self, env, data):
        if data.get_name() == "tts_flush_end":
            self.stage = "measured"
            self.reported.clear()
            self.audio = False
            text = Data.create("tts_text_input")
            text.set_property_from_json(
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
            env.send_data(text)
            return
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
        if self.stage == "warmup" and frame.get_buf():
            self.stage = "flushing"
            flush = Data.create("tts_flush")
            flush.set_property_from_json(
                "", json.dumps({"flush_id": "before-request"})
            )
            env.send_data(flush)
            return
        if self.stage != "measured":
            return
        if frame.get_buf():
            self.audio = True
            self.complete(env)

    def complete(self, env):
        if self.audio and self.reported:
            self.timer.cancel()
            env.stop_test()


def test_ttfb_excludes_sdk_setup_and_callback_queue_wait():
    times = {}

    class Provider:
        def __init__(self, callback, **kwargs):
            time.sleep(0.15)
            self.callback = callback

        def streaming_call(self, text):
            times["sent"] = time.monotonic_ns()

            def audio():
                times["received"] = time.monotonic_ns()
                self.callback.on_data(b"\x01\x00" * 1600)

            threading.Timer(0.02, audio).start()

        def get_last_request_id(self):
            return "mock-task"

        def async_streaming_complete(self):
            pass

        def streaming_cancel(self):
            pass

    with patch(
        "ten_packages.extension.cosy_tts_python.cosy_tts.SpeechSynthesizer",
        Provider,
    ):
        tester = TimingTester()
        try:
            tester.set_test_mode_single(
                "cosy_tts_python", json.dumps({"params": {"api_key": "mock"}})
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
