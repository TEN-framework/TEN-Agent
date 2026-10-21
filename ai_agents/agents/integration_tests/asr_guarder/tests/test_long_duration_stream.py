#!/usr/bin/env python3
#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from typing import Any
from unittest.mock import AsyncMock, Mock, patch
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
import math
import asyncio
import os
import time

# Constants for audio configuration
AUDIO_CHUNK_SIZE = 320
AUDIO_SAMPLE_RATE = 16000
FRAME_INTERVAL_MS = 10

# Constants for test configuration
DEFAULT_CONFIG_FILE = "property_en.json"
DEFAULT_SESSION_ID = "test_long_duration_session_123"
DEFAULT_EXPECTED_LANGUAGE = "en-US"

# Long duration test configuration
LONG_DURATION_TEST_MINUTES = 5  # Test for 5 minutes to trigger stream restart
LONG_DURATION_TEST_SECONDS = LONG_DURATION_TEST_MINUTES * 60
AUDIO_REPEAT_INTERVAL = 30  # Repeat audio every 30 seconds


class LongDurationAsrExtensionTester(AsyncExtensionTester):
    """Test class for long duration ASR extension integration testing."""

    def __init__(
        self,
        audio_file_path: str,
        session_id: str = DEFAULT_SESSION_ID,
        expected_language: str = DEFAULT_EXPECTED_LANGUAGE,
        test_duration_minutes: int = LONG_DURATION_TEST_MINUTES,
    ):
        super().__init__()
        print("=" * 80)
        print("🧪 TEST CASE: Long Duration ASR Stream Integration Test")
        print("=" * 80)
        print(
            "📋 Test Description: Validate ASR extension handles long duration streams (>5 minutes)"
        )
        print("🎯 Test Objectives:")
        print("   - Test ASR extension for extended periods (>5 minutes)")
        print(
            "   - Verify stream duration monitoring and auto-restart functionality"
        )
        print(
            "   - Validate continuous audio processing without 5-minute timeout"
        )
        print(
            "   - Check that results are still generated after stream restarts"
        )
        print("   - Ensure no 409 Max duration errors occur")
        print(f"   - Test duration: {test_duration_minutes} minutes")
        print("=" * 80)

        self.audio_file_path: str = audio_file_path
        self.session_id: str = session_id
        self.expected_language: str = expected_language
        self.test_duration_seconds: int = test_duration_minutes * 60

        # Track test state
        self.start_time: float | None = None
        self.test_completed: bool = False
        self.result_count: int = 0
        self.final_results: list[dict[str, Any]] = []
        self.stream_restart_count: int = 0
        self.last_result_time: float | None = None
        self.completion_time: float | None = None
        self.final_finalize_id: str | None = None
        self.finalize_count: int = 0
        self.audio_sent_ms: float = 0
        self.last_audio_batch_start_ms: float | None = None
        self.last_final_audio_end_ms: float | None = None
        self.failed: bool = False

    def _create_audio_frame(self, data: bytes, session_id: str) -> AudioFrame:
        """Create an audio frame with the given data and session ID."""
        audio_frame = AudioFrame.create("pcm_frame")

        # Set session_id in metadata according to API specification
        metadata = {"session_id": session_id}
        audio_frame.set_property_from_json("metadata", json.dumps(metadata))

        audio_frame.alloc_buf(len(data))
        buf = audio_frame.lock_buf()
        buf[:] = data
        audio_frame.unlock_buf(buf)
        return audio_frame

    async def _send_audio_file_once(self, ten_env: AsyncTenEnvTester) -> None:
        """Send audio file data once to ASR extension."""
        ten_env.log_info(f"Sending audio file: {self.audio_file_path}")

        batch_start_ms = self.audio_sent_ms
        batch_started = False
        with open(self.audio_file_path, "rb") as audio_file:
            while True:
                chunk = audio_file.read(AUDIO_CHUNK_SIZE)
                if not chunk:
                    break

                audio_frame = self._create_audio_frame(chunk, self.session_id)
                try:
                    # Add timeout to prevent blocking indefinitely
                    await asyncio.wait_for(
                        ten_env.send_audio_frame(audio_frame),
                        timeout=5.0,  # 5 second timeout
                    )
                except asyncio.TimeoutError:
                    ten_env.log_error(
                        "Timeout sending audio frame, skipping..."
                    )
                    break
                except Exception as e:
                    ten_env.log_error(f"Error sending audio frame: {e}")
                    break

                if not batch_started:
                    self.last_audio_batch_start_ms = batch_start_ms
                    batch_started = True
                self.audio_sent_ms += (
                    len(chunk) / (AUDIO_SAMPLE_RATE * 2) * 1000
                )
                await asyncio.sleep(FRAME_INTERVAL_MS / 1000)

    async def _send_finalize_signal(
        self,
        ten_env: AsyncTenEnvTester,
        session_id: str | None = None,
        *,
        final: bool = False,
    ) -> None:
        """Send asr_finalize signal to trigger finalization."""
        ten_env.log_info("Sending asr_finalize signal...")

        # Use provided session_id or default to self.session_id
        target_session_id = session_id if session_id else self.session_id

        # Create finalize data according to protocol
        self.finalize_count += 1
        finalize_data = {
            "finalize_id": f"finalize_{target_session_id}_{self.finalize_count}",
            "metadata": {"session_id": target_session_id},
        }
        if final:
            # The acknowledgement can arrive before send_data returns.
            self.final_finalize_id = finalize_data["finalize_id"]

        # Create Data object for asr_finalize
        finalize_data_obj = Data.create("asr_finalize")
        finalize_data_obj.set_property_from_json(
            None, json.dumps(finalize_data)
        )

        # Send the finalize signal
        try:
            # Add timeout to prevent blocking indefinitely
            await asyncio.wait_for(
                ten_env.send_data(finalize_data_obj),
                timeout=3.0,  # 3 second timeout
            )
        except asyncio.TimeoutError:
            ten_env.log_error("Timeout sending finalize signal, skipping...")
            return
        except Exception as e:
            ten_env.log_error(f"Error sending finalize signal: {e}")
            return

        ten_env.log_info(
            f"✅ asr_finalize signal sent with ID: {finalize_data['finalize_id']}"
        )

    async def long_duration_audio_sender(
        self, ten_env: AsyncTenEnvTester
    ) -> None:
        """Send audio data continuously for extended duration."""
        try:
            self.start_time = time.time()
            ten_env.log_info("=== Starting long duration audio send ===")
            ten_env.log_info(
                f"Test duration: {self.test_duration_seconds} seconds"
            )
            ten_env.log_info(f"Using session_id: {self.session_id}")

            # Calculate how many times to repeat the audio file
            # Estimate audio file duration based on file size and sample rate
            file_size = os.path.getsize(self.audio_file_path)
            estimated_audio_duration = file_size / (
                AUDIO_SAMPLE_RATE * 2
            )  # 16-bit = 2 bytes per sample

            ten_env.log_info(
                f"Estimated audio file duration: {estimated_audio_duration:.2f} seconds"
            )

            # Send audio continuously for the test duration
            elapsed_time = 0
            audio_repeat_count = 0

            while (
                elapsed_time < self.test_duration_seconds
                and not self.test_completed
            ):
                # Safety check: force stop if we exceed test duration significantly
                if (
                    elapsed_time > self.test_duration_seconds + 30
                ):  # 30 seconds buffer
                    ten_env.log_warn(
                        f"Test duration exceeded by {elapsed_time - self.test_duration_seconds:.1f}s, forcing stop"
                    )
                    break
                cycle_start_time = time.time()

                ten_env.log_info(
                    f"=== Audio cycle {audio_repeat_count + 1} (elapsed: {elapsed_time:.1f}s) ==="
                )

                # Send audio file
                await self._send_audio_file_once(ten_env)

                # Send finalize signal every 10 cycles to reduce frequency and avoid unnecessary restarts
                if (audio_repeat_count + 1) % 10 == 0:
                    try:
                        ten_env.log_info(
                            f"=== Sending finalize signal for cycle {audio_repeat_count + 1} ==="
                        )
                        await self._send_finalize_signal(ten_env)
                        # Wait longer after finalize to allow processing
                        await asyncio.sleep(2.0)
                    except Exception as e:
                        ten_env.log_error(f"Error sending finalize signal: {e}")
                        # Continue with next cycle even if finalize fails
                        await asyncio.sleep(1.0)
                else:
                    # Wait a bit between audio sends
                    await asyncio.sleep(1.0)

                # Calculate elapsed time
                elapsed_time = time.time() - self.start_time
                audio_repeat_count += 1

                # Log progress every 30 seconds
                if int(elapsed_time) % 30 == 0:
                    ten_env.log_info(
                        f"Progress: {elapsed_time:.1f}s / {self.test_duration_seconds}s ({elapsed_time/self.test_duration_seconds*100:.1f}%)"
                    )

                # Check if we should stop
                if elapsed_time >= self.test_duration_seconds:
                    break

            # Wait for final processing
            ten_env.log_info("=== Waiting for final processing ===")
            await asyncio.sleep(5.0)

            # Mark test as completed
            self.test_completed = True
            ten_env.log_info(
                f"=== Long duration test completed after {time.time() - self.start_time:.1f} seconds ==="
            )

            # Send final finalize signal to ensure we get final results
            try:
                ten_env.log_info("=== Sending final finalize signal ===")
                await self._send_finalize_signal(ten_env, final=True)
                ten_env.log_info(
                    "=== Final finalize signal sent successfully ==="
                )

                # Wait a bit for finalize to take effect
                await asyncio.sleep(2.0)
            except Exception as e:
                ten_env.log_error(f"Error sending final finalize signal: {e}")
                # Continue anyway, the test completion logic will handle it

        except Exception as e:
            ten_env.log_error(f"Error in long duration audio sender: {e}")
            raise

    @override
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        """Start the long duration ASR integration test."""
        ten_env.log_info("Starting long duration ASR integration test")

        # Verify audio file exists
        if not os.path.exists(self.audio_file_path):
            ten_env.log_error(f"Audio file not found: {self.audio_file_path}")
            self.test_completed = True
            ten_env.stop_test()
            return

        ten_env.log_info(f"Audio file verified: {self.audio_file_path}")

        # Start audio sender task
        audio_task = asyncio.create_task(
            self.long_duration_audio_sender(ten_env)
        )

        # Add a safety timeout to ensure test completes
        try:
            await asyncio.wait_for(
                audio_task, timeout=self.test_duration_seconds + 60
            )  # 60 seconds buffer
        except asyncio.TimeoutError:
            self.test_completed = True
            self._stop_test_with_error(
                ten_env, "Long duration audio sender timed out"
            )
        except Exception as e:
            ten_env.log_error(f"Error in audio sender task: {e}")
            self.test_completed = True
            ten_env.stop_test()

    def _stop_test_with_error(
        self, ten_env: AsyncTenEnvTester, error_message: str
    ) -> None:
        """Stop test with error message."""
        if self.failed:
            return
        self.failed = True
        ten_env.stop_test(
            TenError.create(TenErrorCode.ErrorCodeGeneric, error_message)
        )

    def _validate_required_fields(
        self, ten_env: AsyncTenEnvTester, json_data: dict[str, Any]
    ) -> bool:
        """Validate that all required fields exist in ASR result."""
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

    def _validate_language(
        self, ten_env: AsyncTenEnvTester, json_data: dict[str, Any]
    ) -> bool:
        """Validate language matches expected language."""
        language: str = json_data.get("language", "")
        if language != self.expected_language:
            self._stop_test_with_error(
                ten_env,
                f"Language mismatch, expected: {self.expected_language}, actual: {language}",
            )
            return False
        return True

    def _validate_session_id(
        self, ten_env: AsyncTenEnvTester, metadata: dict[str, Any] | None
    ) -> bool:
        """Validate session_id in metadata."""
        if (
            not metadata
            or not isinstance(metadata, dict)
            or "session_id" not in metadata
        ):
            self._stop_test_with_error(
                ten_env, "Missing session_id field in metadata"
            )
            return False

        actual_session_id: str = metadata["session_id"]
        expected_session_id = self.session_id

        if actual_session_id != expected_session_id:
            self._stop_test_with_error(
                ten_env,
                f"session_id mismatch, expected: {expected_session_id}, actual: {actual_session_id}",
            )
            return False
        return True

    def _complete_test(self, ten_env: AsyncTenEnvTester) -> None:
        """Finish only after the full duration and validated recognition output."""
        if self.failed or self.completion_time is not None:
            return
        if not self.result_count or not self.final_results:
            self._stop_test_with_error(
                ten_env, "Stream completed without validated final ASR results"
            )
            return

        current_time = time.time()
        elapsed_time = (
            current_time - self.start_time if self.start_time is not None else 0
        )
        if elapsed_time < self.test_duration_seconds:
            self._stop_test_with_error(
                ten_env,
                f"Stream completed too early: {elapsed_time:.1f}s / "
                f"{self.test_duration_seconds}s",
            )
            return

        if (
            self.last_audio_batch_start_ms is None
            or self.last_final_audio_end_ms is None
            or self.last_final_audio_end_ms <= self.last_audio_batch_start_ms
        ):
            self._stop_test_with_error(
                ten_env,
                "No validated final transcript covers the last audio batch",
            )
            return

        self.completion_time = current_time
        ten_env.log_info("✅ Long duration ASR test completed successfully")
        ten_env.log_info(f"Total results received: {self.result_count}")
        ten_env.log_info(f"Final results received: {len(self.final_results)}")
        ten_env.log_info(f"Test duration: {elapsed_time:.1f} seconds")
        ten_env.stop_test()

    @override
    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        """Handle received data from ASR extension."""
        name: str = data.get_name()
        if self.failed:
            return
        if name == "error":
            self._stop_test_with_error(
                ten_env, "ASR error received during long-duration recognition"
            )
            return

        if name == "asr_finalize_end":
            if not self.test_completed or self.final_finalize_id is None:
                return
            json_str, _ = data.get_property_to_json(None)
            finalize_end_data: dict[str, Any] = json.loads(json_str)
            if finalize_end_data.get("finalize_id") != self.final_finalize_id:
                # A delayed periodic finalize must not complete the final drain.
                return
            if not self._validate_session_id(
                ten_env, finalize_end_data.get("metadata")
            ):
                return
            # An empty final turn emits an acknowledgement, not another
            # transcript. A validated final must cover the latest audio batch.
            self._complete_test(ten_env)
            return

        if name != "asr_result":
            ten_env.log_info(f"Received non-ASR data: {name}")
            return

        # Parse ASR result
        json_str, _ = data.get_property_to_json(None)
        json_data: dict[str, Any] = json.loads(json_str)

        # Validate required fields first
        if not self._validate_required_fields(ten_env, json_data):
            return
        metadata_dict: dict[str, Any] | None = json_data.get("metadata")
        if not self._validate_language(ten_env, json_data):
            return
        if not self._validate_session_id(ten_env, metadata_dict):
            return

        timing = [json_data["start_ms"], json_data["duration_ms"]]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in timing
        ):
            self._stop_test_with_error(ten_env, "Invalid ASR result timing")
            return

        # Track result
        current_time = time.time()
        self.result_count += 1
        self.last_result_time = current_time

        # Check if this is a final result
        is_final: bool = json_data.get("final", False)
        result_id: str = json_data.get("id", "")

        elapsed_time = current_time - self.start_time if self.start_time else 0

        ten_env.log_info(
            f"Received ASR result #{self.result_count} - final: {is_final}, id: {result_id}, elapsed: {elapsed_time:.1f}s"
        )

        # Store final results
        if is_final:
            if (
                not isinstance(json_data["text"], str)
                or not json_data["text"].strip()
            ):
                self._stop_test_with_error(
                    ten_env, "Empty final ASR transcript"
                )
                return
            self.last_final_audio_end_ms = max(
                self.last_final_audio_end_ms or 0, sum(timing)
            )
            self.final_results.append(json_data)
            ten_env.log_info(
                f"✅ Final ASR result #{len(self.final_results)} received"
            )

        # Results can still be arriving during the final drain. Only its
        # matching acknowledgement can establish that transcript coverage is
        # complete; the unchanged hard timeout fails a missing acknowledgement.

    @override
    async def on_stop(self, ten_env: AsyncTenEnvTester) -> None:
        """Clean up resources when test stops."""
        ten_env.log_info("Long duration test stopped")


def test_long_duration_stream(extension_name: str, config_dir: str) -> None:
    """Verify ASR extension handles long duration streams without 5-minute timeout."""

    # Audio file path
    audio_file_path = os.path.join(
        os.path.dirname(__file__), "test_data/16k_en_us.pcm"
    )

    # Get config file path
    config_file_path = os.path.join(config_dir, DEFAULT_CONFIG_FILE)
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")

    # Load config file
    with open(config_file_path, "r") as f:
        config: dict[str, Any] = json.load(f)

    # Expected test results
    expected_result = {
        "language": DEFAULT_EXPECTED_LANGUAGE,
        "session_id": DEFAULT_SESSION_ID,
    }

    # Log test configuration
    print(f"Using test configuration: {config}")
    print(f"Audio file path: {audio_file_path}")
    print(f"Test duration: {LONG_DURATION_TEST_MINUTES} minutes")
    print(
        f"Expected results: language='{expected_result['language']}', session_id='{expected_result['session_id']}'"
    )

    print("\n" + "=" * 60)
    print("Long Duration Stream Test")
    print("=" * 60)

    tester = LongDurationAsrExtensionTester(
        audio_file_path=audio_file_path,
        session_id=expected_result["session_id"],
        expected_language=expected_result["language"],
        test_duration_minutes=LONG_DURATION_TEST_MINUTES,
    )

    tester.set_test_mode_single(extension_name, json.dumps(config))
    tester.set_timeout(6 * 60 * 1000 * 1000)
    error = tester.run()

    # Verify test results
    assert (
        error is None
    ), f"Long duration test failed: {error.error_message() if error else 'Unknown error'}"

    # Verify we received results
    assert (
        tester.result_count > 0
    ), "No ASR results received during long duration test"
    assert (
        len(tester.final_results) > 0
    ), "No final ASR results received during long duration test"
    assert (
        tester.completion_time is not None
    ), "Stream did not complete normally"
    assert tester.start_time is not None, "Stream did not start"
    assert (
        tester.completion_time - tester.start_time
        >= tester.test_duration_seconds
    ), "Stream completed before the requested test duration"

    # Verify test duration
    if tester.start_time and tester.last_result_time:
        actual_duration = tester.last_result_time - tester.start_time
        print(f"✅ Test completed successfully")
        print(f"   - Total results: {tester.result_count}")
        print(f"   - Final results: {len(tester.final_results)}")
        print(f"   - Test duration: {actual_duration:.1f} seconds")
        print(f"   - No 5-minute timeout errors occurred")
    else:
        raise AssertionError("Test timing information not available")

    print("✅ Long duration ASR integration test passed")


def _completion_test_data(name: str, payload: dict[str, Any]) -> Mock:
    data = Mock()
    data.get_name.return_value = name
    data.get_property_to_json.return_value = (json.dumps(payload), None)
    return data


def _completion_test_result() -> dict[str, Any]:
    return {
        "id": "result-1",
        "text": "A validated transcript.",
        "final": True,
        "start_ms": 0,
        "duration_ms": 1000,
        "language": DEFAULT_EXPECTED_LANGUAGE,
        "metadata": {"session_id": DEFAULT_SESSION_ID},
    }


def _completion_test_setup() -> tuple[LongDurationAsrExtensionTester, Mock]:
    tester = LongDurationAsrExtensionTester("unused.pcm")
    tester.start_time = 100.0
    tester.audio_sent_ms = 1000
    tester.last_audio_batch_start_ms = 0
    return tester, Mock()


def test_long_duration_stream_completion_ack_before_send_returns() -> None:
    """An empty final drain can acknowledge without emitting another result."""
    tester, env = _completion_test_setup()

    async def acknowledge(data: Data) -> None:
        payload, _ = data.get_property_to_json(None)
        await tester.on_data(
            env, _completion_test_data("asr_finalize_end", json.loads(payload))
        )

    env.send_data = AsyncMock(side_effect=acknowledge)

    async def run() -> None:
        await tester.on_data(
            env, _completion_test_data("asr_result", _completion_test_result())
        )
        await tester._send_finalize_signal(env)
        env.stop_test.assert_not_called()
        tester.test_completed = True
        await tester._send_finalize_signal(env, final=True)

    with patch.object(time, "time", return_value=405.0):
        asyncio.run(run())
    env.stop_test.assert_called_once_with()
    assert tester.result_count == 1
    assert len(tester.final_results) == 1
    assert tester.completion_time == 405.0
    sent_ids = [
        json.loads(call.args[0].get_property_to_json(None)[0])["finalize_id"]
        for call in env.send_data.call_args_list
    ]
    assert len(set(sent_ids)) == 2
    assert tester.final_finalize_id == sent_ids[-1]


def test_long_duration_stream_completion_ignores_stale_ack() -> None:
    tester, env = _completion_test_setup()
    tester.final_finalize_id = "final-drain"
    ack = {
        "finalize_id": "periodic",
        "metadata": {"session_id": tester.session_id},
    }
    with patch.object(time, "time", return_value=405.0):
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
        tester.test_completed = True
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
    env.stop_test.assert_not_called()
    assert tester.completion_time is None


def test_long_duration_stream_completion_rejects_unvalidated_results() -> None:
    for invalid_field, value in (
        ("language", "wrong"),
        ("metadata", {}),
        ("id", None),
    ):
        tester, env = _completion_test_setup()
        result = _completion_test_result()
        if value is None:
            del result[invalid_field]
        else:
            result[invalid_field] = value
        with patch.object(time, "time", return_value=405.0):
            asyncio.run(
                tester.on_data(env, _completion_test_data("asr_result", result))
            )
        env.stop_test.assert_called_once()
        assert env.stop_test.call_args.args
        assert tester.result_count == 0
        assert tester.final_results == []
        assert tester.last_result_time is None


def test_long_duration_stream_completion_requires_final_result() -> None:
    tester, env = _completion_test_setup()
    result = _completion_test_result()
    result["final"] = False
    with patch.object(time, "time", return_value=405.0):
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_result", result))
        )
        tester.test_completed = True
        tester.final_finalize_id = "final-drain"
        ack = {"finalize_id": "final-drain", "metadata": result["metadata"]}
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
    env.stop_test.assert_called_once()
    assert env.stop_test.call_args.args
    assert tester.completion_time is None


def test_long_duration_stream_completion_validates_ack_session() -> None:
    tester, env = _completion_test_setup()
    with patch.object(time, "time", return_value=405.0):
        asyncio.run(
            tester.on_data(
                env,
                _completion_test_data("asr_result", _completion_test_result()),
            )
        )
        tester.test_completed = True
        tester.final_finalize_id = "final-drain"
        ack = {
            "finalize_id": "final-drain",
            "metadata": {"session_id": "wrong"},
        }
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
    env.stop_test.assert_called_once()
    assert env.stop_test.call_args.args
    assert tester.completion_time is None


def test_long_duration_stream_completion_requires_full_duration() -> None:
    tester, env = _completion_test_setup()
    with patch.object(time, "time", return_value=399.0):
        asyncio.run(
            tester.on_data(
                env,
                _completion_test_data("asr_result", _completion_test_result()),
            )
        )
        tester.test_completed = True
        tester.final_finalize_id = "final-drain"
        ack = {
            "finalize_id": "final-drain",
            "metadata": {"session_id": tester.session_id},
        }
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
    env.stop_test.assert_called_once()
    assert env.stop_test.call_args.args
    assert tester.completion_time is None


def test_long_duration_stream_completion_rejects_only_early_recognition() -> (
    None
):
    tester, env = _completion_test_setup()
    with patch.object(time, "time", return_value=110.0):
        asyncio.run(
            tester.on_data(
                env,
                _completion_test_data("asr_result", _completion_test_result()),
            )
        )
    tester.audio_sent_ms = 3000
    tester.last_audio_batch_start_ms = 2000
    tester.test_completed = True
    tester.final_finalize_id = "final-drain"
    ack = {
        "finalize_id": "final-drain",
        "metadata": {"session_id": tester.session_id},
    }
    with patch.object(time, "time", return_value=405.0):
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
    env.stop_test.assert_called_once()
    assert env.stop_test.call_args.args
    assert tester.completion_time is None


def test_long_duration_stream_completion_requires_latest_batch_coverage() -> (
    None
):
    tester, env = _completion_test_setup()
    tester.audio_sent_ms = 3000
    tester.last_audio_batch_start_ms = 2000
    final = _completion_test_result()
    final.update(start_ms=2000, duration_ms=900)
    with patch.object(time, "time", return_value=405.0):
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_result", final))
        )
        tester.test_completed = True
        tester.final_finalize_id = "final-drain"
        ack = {"finalize_id": "final-drain", "metadata": final["metadata"]}
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
    env.stop_test.assert_called_once_with()
    assert tester.completion_time == 405.0


def test_long_duration_stream_completion_rejects_error_then_ack() -> None:
    tester, env = _completion_test_setup()
    with patch.object(time, "time", return_value=405.0):
        asyncio.run(
            tester.on_data(
                env,
                _completion_test_data("asr_result", _completion_test_result()),
            )
        )
        asyncio.run(
            tester.on_data(
                env,
                _completion_test_data(
                    "error", {"message": "recognition failed"}
                ),
            )
        )
        tester.test_completed = True
        tester.final_finalize_id = "final-drain"
        ack = {
            "finalize_id": "final-drain",
            "metadata": {"session_id": tester.session_id},
        }
        asyncio.run(
            tester.on_data(env, _completion_test_data("asr_finalize_end", ack))
        )
    env.stop_test.assert_called_once()
    assert env.stop_test.call_args.args
    assert tester.completion_time is None


def test_long_duration_stream_completion_waits_for_drain_after_interim() -> (
    None
):
    tester, env = _completion_test_setup()
    tester.audio_sent_ms = 3000
    tester.last_audio_batch_start_ms = 2000
    tester.test_completed = True
    tester.final_finalize_id = "final-drain"
    older = _completion_test_result()
    interim = _completion_test_result()
    interim.update(final=False, start_ms=2000, duration_ms=200)
    latest = _completion_test_result()
    latest.update(start_ms=2000, duration_ms=900)
    ack = {"finalize_id": "final-drain", "metadata": latest["metadata"]}

    async def run() -> None:
        # Even an interim before the first final, and a delayed older final,
        # must leave the final drain pending rather than fail its coverage.
        for result in (interim, older, latest):
            await tester.on_data(
                env, _completion_test_data("asr_result", result)
            )
            env.stop_test.assert_not_called()
            assert not tester.failed
            assert tester.completion_time is None
        await tester.on_data(
            env, _completion_test_data("asr_finalize_end", ack)
        )

    with patch.object(time, "time", return_value=405.0):
        asyncio.run(run())
    env.stop_test.assert_called_once_with()
    assert tester.completion_time == 405.0


def test_long_duration_stream_completion_requires_ack_after_latest_final() -> (
    None
):
    tester, env = _completion_test_setup()
    tester.test_completed = True
    tester.final_finalize_id = "final-drain"
    with patch.object(time, "time", return_value=405.0):
        asyncio.run(
            tester.on_data(
                env,
                _completion_test_data("asr_result", _completion_test_result()),
            )
        )
    env.stop_test.assert_not_called()
    assert not tester.failed
    assert tester.completion_time is None


def test_long_duration_stream_completion_sender_timeout_is_failure() -> None:
    tester, env = _completion_test_setup()
    tester.long_duration_audio_sender = AsyncMock()
    with (
        patch.object(os.path, "exists", return_value=True),
        patch.object(
            asyncio, "wait_for", new=AsyncMock(side_effect=asyncio.TimeoutError)
        ),
    ):
        asyncio.run(tester.on_start(env))
    env.stop_test.assert_called_once()
    assert env.stop_test.call_args.args
    assert tester.failed
    assert tester.completion_time is None
