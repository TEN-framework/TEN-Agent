"""Verify oracle tts python TTFB at the public provider boundary."""

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


def test_ttfb_uses_first_provider_audio_not_complete_body():
    times = {}

    class AudioBody:
        def __init__(self):
            self._content = None

        def iter_content(self, chunk_size=65536):
            time.sleep(0.03)
            times["received"] = time.monotonic_ns()
            yield b"\x01\x00" * 1600
            time.sleep(0.12)
            yield b"\x02\x00" * 1600

        @property
        def content(self):
            if self._content is None:
                self._content = b"".join(self.iter_content())
            return self._content

    class Provider:
        def synthesize_speech(self, **kwargs):
            times["sent"] = time.monotonic_ns()
            return SimpleNamespace(data=AudioBody())

    config = {
        "params": dict.fromkeys(
            (
                "tenancy",
                "user",
                "fingerprint",
                "key_file",
                "compartment_id",
            ),
            "mock",
        )
    }
    with patch("oci.config.validate_config"), patch(
        "oci.ai_speech.AIServiceSpeechClient",
        return_value=Provider(),
    ):
        tester = TimingTester()
        try:
            tester.set_test_mode_single("oracle_tts_python", json.dumps(config))
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
