"""Verify Google TTFB against an independent SDK request/response reference."""

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


def test_ttfb_ends_at_first_nonempty_sdk_audio():
    times = {}

    class Provider:
        def streaming_synthesize(self, requests):
            def responses():
                # The SDK consumes the request iterator after returning the response iterator.
                for request in requests:
                    if request.input.text:
                        times["sent"] = time.monotonic_ns()
                yield SimpleNamespace(audio_content=b"")
                time.sleep(0.05)
                times["received"] = time.monotonic_ns()
                yield SimpleNamespace(audio_content=b"\x01\x00" * 1600)

            return responses()

    credentials = json.dumps(
        dict.fromkeys(
            (
                "type",
                "project_id",
                "private_key_id",
                "private_key",
                "client_email",
                "client_id",
            ),
            "mock",
        )
    )
    config = {
        "params": {
            "credentials": credentials,
            "AudioConfig": {"sample_rate_hertz": 16000},
        }
    }
    with patch(
        "google.oauth2.service_account.Credentials.from_service_account_info",
        return_value=object(),
    ), patch(
        "google.cloud.texttospeech.TextToSpeechClient",
        return_value=Provider(),
    ):
        tester = TimingTester()
        try:
            tester.set_test_mode_single("google_tts_python", json.dumps(config))
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
