#
# Copyright © 2024 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import json

from ten_ai_base.struct import TTSTextInput
from ten_runtime import (
    Data,
    ExtensionTester,
    TenEnvTester,
)
from ..cosy_tts import (
    AsyncIteratorCallback,
    CosyTTSClient,
    MESSAGE_TYPE_PCM,
    MESSAGE_TYPE_CMD_COMPLETE,
)
from .mock_client import MockClientStream


def test_ttfb_uses_first_text_send_and_first_audio_callback() -> None:
    callback = AsyncIteratorCallback(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        "request-id",
    )
    callback._put = MagicMock()
    synthesizer = MagicMock()
    active = SimpleNamespace(
        callback=callback,
        lease=SimpleNamespace(synthesizer=synthesizer),
    )

    with patch(
        "cosy_tts_python.cosy_tts.time.perf_counter_ns",
        side_effect=[1_000_000_000, 1_607_000_000],
    ):
        CosyTTSClient._send_text(active, "first")
        CosyTTSClient._send_text(active, "second")
        callback.on_data(b"audio")

    assert synthesizer.streaming_call.call_count == 2
    assert callback.first_request_sent_ns == 1_000_000_000
    assert callback.first_audio_ns == 1_607_000_000
    assert callback._put.call_args.args[0].ttfb_ms == 607


# ================ test metrics ================
class ExtensionTesterMetrics(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.ttfb_received = False
        self.ttfb_value = -1
        self.audio_frame_received = False
        self.audio_end_received = False
        self.request_event_interval_ms = -1

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        """Called when test starts, sends a TTS request."""
        ten_env_tester.log_info("Metrics test started, sending TTS request.")

        tts_input = TTSTextInput(
            request_id="tts_request_for_metrics",
            text="hello, this is a metrics test.",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        ten_env.log_info(f"on_data name: {name}")
        if name == "metrics":
            json_str, _ = data.get_property_to_json(None)
            ten_env.log_info(f"Received metrics: {json_str}")
            metrics_data = json.loads(json_str)

            # According to the new structure, 'ttfb' is nested inside a 'metrics' object.
            nested_metrics = metrics_data.get("metrics", {})
            if "ttfb" in nested_metrics:
                self.ttfb_received = True
                self.ttfb_value = nested_metrics.get("ttfb", -1)
                ten_env.log_info(
                    f"Received TTFB metric with value: {self.ttfb_value}"
                )

        elif name == "tts_audio_end":
            self.audio_end_received = True
            json_str, _ = data.get_property_to_json(None)
            payload = json.loads(json_str)
            self.request_event_interval_ms = payload.get(
                "request_event_interval_ms", -1
            )
            # Stop the test only after both TTFB and audio end are received
            if self.ttfb_received:
                ten_env.log_info("Received tts_audio_end, stopping test.")
                ten_env.stop_test()

    def on_audio_frame(self, ten_env: TenEnvTester, audio_frame):
        """Receives audio frames and confirms the stream is working."""
        if not self.audio_frame_received:
            self.audio_frame_received = True
            ten_env.log_info("First audio frame received.")


@patch("cosy_tts_python.extension.CosyTTSClient")
def test_ttfb_metric_is_sent(MockCosyTTSClient):
    """
    Tests that a TTFB (Time To First Byte) metric is correctly sent after
    receiving the first audio chunk from the TTS service.
    """
    print("Starting test_ttfb_metric_is_sent with mock...")

    # --- Mock Configuration ---
    mock_instance = MockCosyTTSClient.return_value
    stream = MockClientStream(
        lambda _text, _request_id: [
            (MESSAGE_TYPE_PCM, b"\x11\x22\x33", 0.6),
            (MESSAGE_TYPE_PCM, b"\x44\x55\x66", 0.05),
            (MESSAGE_TYPE_PCM, b"\x77\x88\x99", 0.05),
            (MESSAGE_TYPE_CMD_COMPLETE, None, 0.05),
        ]
    )
    stream.configure(mock_instance)

    # --- Test Setup ---
    # A minimal config is needed for the extension to initialize correctly.
    metrics_config = {
        "params": {
            "api_key": "a_valid_key",
        }
    }
    tester = ExtensionTesterMetrics()
    tester.set_test_mode_single("cosy_tts_python", json.dumps(metrics_config))

    print("Running TTFB metrics test...")
    tester.run()
    print("TTFB metrics test completed.")

    # --- Assertions ---
    assert tester.audio_frame_received, "Did not receive any audio frame."
    assert tester.audio_end_received, "Did not receive the tts_audio_end event."
    assert tester.ttfb_received, "TTFB metric was not received."
    assert (
        tester.request_event_interval_ms >= 0
    ), "tts_audio_end did not include request_event_interval_ms."

    # Check if the TTFB value is reasonable. The larger delay keeps it well
    # above the post-first-chunk interval despite scheduling variability.
    assert (
        tester.ttfb_value >= 500
    ), f"Expected TTFB to be >= 500ms, but got {tester.ttfb_value}ms."
    assert tester.request_event_interval_ms < tester.ttfb_value, (
        "request_event_interval_ms should start at the first audio chunk and "
        "exclude TTFB."
    )

    print(f"✅ TTFB metric test passed. Received TTFB: {tester.ttfb_value}ms.")
