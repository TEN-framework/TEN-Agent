#!/usr/bin/env python3
#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from typing import Any
from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    AudioFrame,
    TenError,
    TenErrorCode,
)
import json
import asyncio
import os
import glob
import time

TTS_METRICS_CONFIG_FILE="property_basic_audio_setting1.json"
AUDIO_DURATION_TOLERANCE_MS = 50

class MetricsTester(AsyncExtensionTester):
    """Test class for TTS extension metrics"""

    def __init__(
        self,
        session_id: str = "test_metric_session_123",
        text: str = "",
    ):
        super().__init__()
        print("=" * 80)
        print("🧪 TEST CASE: TTS Metrics Test")
        print("=" * 80)
        print(
            "📋 Test Description: Validate TTS Metrics"
        )
        print("🎯 Test Objectives:")
        print("   - Verify metrics is generated")
        print("=" * 80)

        self.session_id: str = session_id
        self.text: str = text
        self.receive_metircs = False
        self.sent_metadata = None  # Store sent metadata for validation
        self.request_id = "test_metric_request_id_1"
        self.audio_start_time = None  # Store tts_audio_start timestamp
        self.total_audio_bytes = 0  # Track total audio bytes received
        self.sample_rate = 0  # Store sample rate

    def _calculate_pcm_audio_duration_ms(self) -> int:
        """Calculate PCM audio duration in milliseconds based on received audio bytes"""
        if self.total_audio_bytes == 0 or self.sample_rate == 0:
            return 0
        
        # PCM format: 16-bit (2 bytes per sample), mono (1 channel)
        bytes_per_sample = 2
        channels = 1
        
        # Calculate duration in seconds, then convert to milliseconds
        duration_sec = self.total_audio_bytes / (self.sample_rate * bytes_per_sample * channels)
        return int(duration_sec * 1000)

    async def _send_finalize_signal(self, ten_env: AsyncTenEnvTester) -> None:
        """Send tts_finalize signal to trigger finalization."""
        ten_env.log_info("Sending tts_finalize signal...")

        # Create finalize data according to protocol
        finalize_data = {
            "finalize_id": f"finalize_{self.session_id}_{int(asyncio.get_event_loop().time())}",
            "metadata": {"session_id": self.session_id},
        }

        # Create Data object for tts_finalize
        finalize_data_obj = Data.create("tts_finalize")
        finalize_data_obj.set_property_from_json(
            None, json.dumps(finalize_data)
        )

        # Send the finalize signal
        await ten_env.send_data(finalize_data_obj)

        ten_env.log_info(
            f"✅ tts_finalize signal sent with ID: {finalize_data['finalize_id']}"
        )

    @override
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        """Start the TTS invalid required params test."""
        ten_env.log_info("Starting TTS invalid required params test")
        await self._send_tts_text_input(ten_env, self.text)

    async def _send_tts_text_input(self, ten_env: AsyncTenEnvTester, text: str) -> None:
        """Send tts text input to TTS extension."""
        ten_env.log_info(f"Sending tts text input: {text}")
        tts_text_input_obj = Data.create("tts_text_input")
        tts_text_input_obj.set_property_string("text", text)
        tts_text_input_obj.set_property_string("request_id", "test_metric_request_id_1")
        tts_text_input_obj.set_property_bool("text_input_end", True)
        metadata = {
            "session_id": "test_metric_session_123",
            "turn_id": 1,
        }
        # Store sent metadata for validation
        self.sent_metadata = metadata
        tts_text_input_obj.set_property_from_json("metadata", json.dumps(metadata))
        await ten_env.send_data(tts_text_input_obj)
        ten_env.log_info(f"✅ tts text input sent: {text}")

    def _stop_test_with_error(
        self, ten_env: AsyncTenEnvTester, error_message: str
    ) -> None:
        """Stop test with error message."""
        ten_env.stop_test(
            TenError.create(TenErrorCode.ErrorCodeGeneric, error_message)
        )

    def _log_tts_result_structure(
        self,
        ten_env: AsyncTenEnvTester,
        json_str: str,
        metadata: Any,
    ) -> None:
        """Log complete TTS result structure for debugging."""
        ten_env.log_info("=" * 80)
        ten_env.log_info("RECEIVED TTS RESULT - COMPLETE STRUCTURE:")
        ten_env.log_info("=" * 80)
        ten_env.log_info(f"Raw JSON string: {json_str}")
        ten_env.log_info(f"Metadata: {metadata}")
        ten_env.log_info(f"Metadata type: {type(metadata)}")
        ten_env.log_info("=" * 80)

    def _validate_required_fields(
        self, ten_env: AsyncTenEnvTester, json_data: dict[str, Any]
    ) -> bool:
        """Validate that all required fields exist in TTS result."""
        required_fields = [
            "id",
            "text",
            "final",
            "start_ms",
            "duration_ms",
            "language",
        ]
        missing_fields = [
            field for field in required_fields if field not in json_data
        ]

        if missing_fields:
            self._stop_test_with_error(
                ten_env, f"Missing required fields: {missing_fields}"
            )
            return False
        return True

    @override
    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        """Handle received data from TTS extension."""
        name: str = data.get_name()
        json_str, _ = data.get_property_to_json("")
        ten_env.log_info(f"test extension Received data {name} as: {json_str}")

        if name == "error":
            self._stop_test_with_error(ten_env, f"Received error data")
            return
        elif name == "metrics":
            self.receive_metircs = True
        elif name == "tts_audio_start":
            ten_env.log_info("Received tts_audio_start")
            self.audio_start_time = time.time()
            
            # Validate request_id
            received_request_id, _ = data.get_property_string("request_id")
            if received_request_id != self.request_id:
                self._stop_test_with_error(ten_env, f"Request ID mismatch in tts_audio_start. Expected: {self.request_id}, Received: {received_request_id}")
                return
            
            # Validate metadata (Base class implementation only contains session_id and turn_id in tts_audio_start)
            metadata_str, _ = data.get_property_to_json("metadata")
            if metadata_str:
                try:
                    received_metadata = json.loads(metadata_str)
                    expected_metadata = {
                        "session_id": self.sent_metadata.get("session_id", ""),
                        "turn_id": self.sent_metadata.get("turn_id", -1)
                    }
                    if any(
                        key not in received_metadata
                        or received_metadata[key] != value
                        for key, value in expected_metadata.items()
                    ):
                        self._stop_test_with_error(ten_env, f"Metadata mismatch in tts_audio_start. Expected: {expected_metadata}, Received: {received_metadata}")
                        return
                except json.JSONDecodeError:
                    self._stop_test_with_error(ten_env, f"Invalid JSON in tts_audio_start metadata: {metadata_str}")
                    return
            else:
                self._stop_test_with_error(ten_env, f"Missing metadata in tts_audio_start response")
                return
            
            ten_env.log_info(f"✅ tts_audio_start received with correct request_id and metadata")
            return
        elif name == "tts_audio_end":
            # Validate request_id
            received_request_id, _ = data.get_property_string("request_id")
            if received_request_id != self.request_id:
                self._stop_test_with_error(ten_env, f"Request ID mismatch. Expected: {self.request_id}, Received: {received_request_id}")
                return
            
            # Validate metadata (Base class implementation only contains session_id and turn_id in tts_audio_end)
            metadata_str, _ = data.get_property_to_json("metadata")
            if metadata_str:
                try:
                    received_metadata = json.loads(metadata_str)
                    expected_metadata = {
                        "session_id": self.sent_metadata.get("session_id", ""),
                        "turn_id": self.sent_metadata.get("turn_id", -1)
                    }
                    if any(
                        key not in received_metadata
                        or received_metadata[key] != value
                        for key, value in expected_metadata.items()
                    ):
                        self._stop_test_with_error(ten_env, f"Metadata mismatch in tts_audio_end. Expected: {expected_metadata}, Received: {received_metadata}")
                        return
                except json.JSONDecodeError:
                    self._stop_test_with_error(ten_env, f"Invalid JSON in tts_audio_end metadata: {metadata_str}")
                    return
            else:
                self._stop_test_with_error(ten_env, f"Missing metadata in tts_audio_end response")
                return
            
            # Validate audio duration
            if self.audio_start_time is not None:
                current_time = time.time()
                actual_duration_ms = (current_time - self.audio_start_time) * 1000
                
                # Get request_total_audio_duration_ms (actual audio duration)
                received_audio_duration_ms, _ = data.get_property_int("request_total_audio_duration_ms")
                
                # Validate audio duration: request_total_audio_duration_ms should be consistent with the length calculated from the PCM file
                pcm_audio_duration_ms = self._calculate_pcm_audio_duration_ms()
                if pcm_audio_duration_ms > 0 and received_audio_duration_ms > 0:
                    audio_duration_diff = abs(received_audio_duration_ms - pcm_audio_duration_ms)
                    if audio_duration_diff > AUDIO_DURATION_TOLERANCE_MS:  # Allow AUDIO_DURATION_TOLERANCE_MS ms error
                        self._stop_test_with_error(ten_env, f"Audio duration mismatch. PCM calculated: {pcm_audio_duration_ms}ms, Reported: {received_audio_duration_ms}ms, Diff: {audio_duration_diff}ms")
                        return
                    ten_env.log_info(f"✅ Audio duration validation passed. PCM: {pcm_audio_duration_ms}ms, Reported: {received_audio_duration_ms}ms, Diff: {audio_duration_diff}ms")
                else:
                    ten_env.log_info(f"Skipping audio duration validation - PCM: {pcm_audio_duration_ms}ms, Reported: {received_audio_duration_ms}ms")
                
                # Record actual elapsed time (for debugging)
                ten_env.log_info(f"Actual event duration: {actual_duration_ms:.2f}ms")
            else:
                ten_env.log_warn("tts_audio_start not received before tts_audio_end")
            
            ten_env.log_info(f"✅ tts_audio_end received with correct request_id and metadata")
            
            if not self.receive_metircs:
                self._stop_test_with_error(ten_env, f"no metrics data before tts_audio_end")
            else:
                ten_env.stop_test()

    @override
    async def on_audio_frame(
        self, ten_env: AsyncTenEnvTester, audio_frame: AudioFrame
    ) -> None:
        """Handle received audio frame from TTS extension."""
        # Check sample_rate
        sample_rate = audio_frame.get_sample_rate()
        ten_env.log_info(f"Received audio frame with sample_rate: {sample_rate}")

        # Store current test sample_rate
        if self.sample_rate == 0:
            self.sample_rate = sample_rate
            ten_env.log_info(f"First audio frame received with sample_rate: {sample_rate}")

        # Accumulate audio bytes for duration calculation
        try:
            audio_data = audio_frame.get_buf()
            if audio_data:
                self.total_audio_bytes += len(audio_data)
                ten_env.log_info(f"Audio frame size: {len(audio_data)} bytes, Total: {self.total_audio_bytes} bytes")
        except Exception as e:
            ten_env.log_warn(f"Failed to get audio data: {e}")


def test_metrics(extension_name: str, config_dir: str) -> None:
    """Verify TTS result metrics."""

    # Get config file path
    config_file_path = os.path.join(config_dir, TTS_METRICS_CONFIG_FILE)
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")

    # Load config file
    with open(config_file_path, "r") as f:
        config: dict[str, Any] = json.load(f)

    # Create and run tester
    tester = MetricsTester(
        session_id="test_metric_session_123",
        text="hello world, hello agora, hello shanghai, nice to meet you!",
    )

    tester.set_test_mode_single(extension_name, json.dumps(config))
    error = tester.run()

    # Verify test results
    assert (
        error is None
    ), f"Test failed: {error.error_message() if error else 'Unknown error'}"


class SequentialTTFBTester(AsyncExtensionTester):
    """Check reported TTFB against first audio received for two requests."""

    def __init__(self):
        super().__init__()
        self.request_ids = ("ttfb_streamed", "ttfb_single_final")
        self.sent_at: dict[str, float] = {}
        self.first_audio_at: dict[str, float] = {}
        self.reported_ttfb: dict[str, float] = {}
        self.audio_request_id: str | None = None
        self.finished: set[str] = set()
        self.watchdog: asyncio.Task | None = None

    async def _send(self, ten_env, request_id, text, final):
        data = Data.create("tts_text_input")
        data.set_property_from_json(
            "",
            json.dumps(
                {
                    "request_id": request_id,
                    "text": text,
                    "text_input_end": final,
                    "metadata": {
                        "session_id": "ttfb_guarder",
                        "turn_id": self.request_ids.index(request_id) + 1,
                    },
                }
            ),
        )
        if text and request_id not in self.sent_at:
            self.sent_at[request_id] = time.monotonic()
        await ten_env.send_data(data)

    @override
    async def on_start(self, ten_env):
        async def timeout():
            await asyncio.sleep(20)
            ten_env.stop_test(
                TenError.create(
                    TenErrorCode.ErrorCodeGeneric,
                    "Timed out waiting for both requests' audio and TTFB metrics",
                )
            )

        self.watchdog = asyncio.create_task(timeout())
        await self._send(ten_env, self.request_ids[0], "Hello world.", False)
        await self._send(ten_env, self.request_ids[0], "", True)

    def _check(self, ten_env):
        for request_id in self.request_ids:
            if (
                request_id not in self.first_audio_at
                or request_id not in self.reported_ttfb
            ):
                continue
            elapsed_ms = (
                self.first_audio_at[request_id] - self.sent_at[request_id]
            ) * 1000
            ttfb = self.reported_ttfb[request_id]
            if not 0 <= ttfb <= elapsed_ms:
                ten_env.stop_test(
                    TenError.create(
                        TenErrorCode.ErrorCodeGeneric,
                        f"{request_id}: reported TTFB {ttfb}ms exceeds observed first-audio delay {elapsed_ms:.1f}ms",
                    )
                )
                return
        if all(
            request_id in self.finished
            and request_id in self.first_audio_at
            and request_id in self.reported_ttfb
            for request_id in self.request_ids
        ):
            ten_env.stop_test()

    @override
    async def on_data(self, ten_env, data):
        payload_str, _ = data.get_property_to_json("")
        payload = json.loads(payload_str)
        match data.get_name():
            case "error":
                ten_env.stop_test(
                    TenError.create(TenErrorCode.ErrorCodeGeneric, "TTS returned error")
                )
            case "tts_audio_start":
                self.audio_request_id = payload["request_id"]
            case "metrics":
                if "ttfb" in payload.get("metrics", {}):
                    turn_id = payload.get("metadata", {}).get("turn_id")
                    if turn_id not in (1, 2):
                        ten_env.stop_test(
                            TenError.create(
                                TenErrorCode.ErrorCodeGeneric,
                                "TTFB has no matching turn_id",
                            )
                        )
                        return
                    request_id = self.request_ids[turn_id - 1]
                    if request_id in self.reported_ttfb:
                        ten_env.stop_test(
                            TenError.create(
                                TenErrorCode.ErrorCodeGeneric, "Duplicate request TTFB"
                            )
                        )
                        return
                    self.reported_ttfb[request_id] = payload["metrics"]["ttfb"]
                self._check(ten_env)
            case "tts_audio_end":
                request_id = payload["request_id"]
                self.finished.add(request_id)
                if request_id == self.request_ids[0]:
                    # Separate the requests enough to expose reuse of the old start.
                    await asyncio.sleep(0.15)
                    await self._send(ten_env, self.request_ids[1], "Hello again.", True)
                self._check(ten_env)

    @override
    async def on_audio_frame(self, ten_env, frame):
        if frame.get_buf() and self.audio_request_id is not None:
            self.first_audio_at.setdefault(self.audio_request_id, time.monotonic())
            self._check(ten_env)

    @override
    async def on_stop(self, ten_env):
        if self.watchdog is not None:
            self.watchdog.cancel()


def test_sequential_requests_ttfb(extension_name: str, config_dir: str):
    """A single final text after a streamed request has its own TTFB clock."""
    with open(os.path.join(config_dir, TTS_METRICS_CONFIG_FILE)) as config_file:
        config = json.load(config_file)
    tester = SequentialTTFBTester()
    tester.set_test_mode_single(extension_name, json.dumps(config))
    error = tester.run()
    assert error is None, error.error_message() if error else ""
