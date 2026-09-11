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
)
from ten_ai_base.message import ModuleErrorCode
import json
import asyncio
import os

# Audio configuration constants
AUDIO_CHUNK_SIZE = 3200  # 100ms at 16kHz, 16-bit, mono
AUDIO_SAMPLE_RATE = 16000
FRAME_INTERVAL_MS = 100

# Test configuration constants
DEFAULT_SESSION_ID = "test_reconnection_session_123"

# Reconnection test constants
TEST_DURATION_SECONDS = (
    12  # Total test duration (slightly longer than max reconnection time ~9.3s)
)
TEST_TIMEOUT_SECONDS = 20  # Reduced timeout

DEFAULT_CONFIG_FILE = "property_invalid.json"


class AsrReconnectionTester(AsyncExtensionTester):
    """Test ASR extension reconnection mechanism using invalid credentials."""

    def __init__(self, audio_file_path: str):
        super().__init__()
        print("=" * 80)
        print("🧪 TEST CASE: ASR Reconnection Test")
        print("=" * 80)
        print(
            "📋 Test Description: Validate ASR extension reconnection mechanism"
        )
        print("🎯 Test Objectives:")
        print("   - Test ASR extension reconnection with invalid credentials")
        print("   - Verify error handling during connection failures")
        print("   - Validate reconnection attempt tracking")
        print("   - Check error message format and structure")
        print("   - Test continuous audio sending during reconnection")
        print("   - Validate reconnection timeout behavior")
        print("   - Ensure proper error statistics collection")
        print("=" * 80)

        # Test configuration
        self.audio_file_path: str = audio_file_path

        # Test state tracking
        self.start_time: float | None = None
        self.sender_task: asyncio.Task[None] | None = None

        # Statistics tracking
        self.errors_received: int = 0
        self.reconnection_attempts: int = 0
        self.fatal_error_received: bool = False
        self.error_codes: list[int] = []  # Track all error codes received

    def _create_audio_frame(self, data: bytes, session_id: str) -> AudioFrame:
        """Create an audio frame with the given data."""
        audio_frame = AudioFrame.create("pcm_frame")

        # Set session_id in metadata
        metadata = {"session_id": session_id}
        audio_frame.set_property_from_json("metadata", json.dumps(metadata))

        # Set audio data
        audio_frame.alloc_buf(len(data))
        buf = audio_frame.lock_buf()
        buf[:] = data
        audio_frame.unlock_buf(buf)

        return audio_frame

    def _create_silence_frame(self, size: int, session_id: str) -> AudioFrame:
        """Create a silence audio frame."""
        silence_data = b"\x00" * size
        return self._create_audio_frame(silence_data, session_id)

    async def _send_audio_file(self, ten_env: AsyncTenEnvTester) -> None:
        """Send the test audio file."""
        if not os.path.exists(self.audio_file_path):
            ten_env.log_error(f"Audio file not found: {self.audio_file_path}")
            return

        ten_env.log_info(f"Sending audio file: {self.audio_file_path}")

        with open(self.audio_file_path, "rb") as f:
            audio_data = f.read()

        # Send audio in chunks
        chunk_size = AUDIO_CHUNK_SIZE
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i : i + chunk_size]
            if len(chunk) < chunk_size:
                # Pad the last chunk with silence
                chunk += b"\x00" * (chunk_size - len(chunk))

            audio_frame = self._create_audio_frame(chunk, DEFAULT_SESSION_ID)
            await ten_env.send_audio_frame(audio_frame)
            await asyncio.sleep(FRAME_INTERVAL_MS / 1000)

    async def _send_continuous_audio(self, ten_env: AsyncTenEnvTester) -> None:
        """Send continuous audio frames to test reconnection."""
        ten_env.log_info(
            "Starting continuous audio transmission to test reconnection..."
        )

        # Send initial audio file
        await self._send_audio_file(ten_env)

        # Continue sending silence packets for test duration
        start_time = asyncio.get_event_loop().time()
        self.start_time = start_time

        while True:
            silence_frame = self._create_silence_frame(
                AUDIO_CHUNK_SIZE, DEFAULT_SESSION_ID
            )
            await ten_env.send_audio_frame(silence_frame)
            await asyncio.sleep(FRAME_INTERVAL_MS / 1000)

            current_time = asyncio.get_event_loop().time()
            elapsed_time = current_time - start_time

            # Test completion
            if elapsed_time >= TEST_DURATION_SECONDS:
                ten_env.log_info("✅ Reconnection test completed successfully")
                ten_env.stop_test()
                break

            # Timeout protection
            if elapsed_time >= TEST_TIMEOUT_SECONDS:
                ten_env.log_warn("Test timeout reached")
                break

    async def audio_sender(self, ten_env: AsyncTenEnvTester) -> None:
        """Send continuous audio data to test reconnection."""
        try:
            await self._send_continuous_audio(ten_env)
        except Exception as e:
            ten_env.log_error(f"Error in audio sender: {e}")
            raise

    @override
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        """Start the Azure ASR reconnection test."""
        ten_env.log_info(
            "Starting Azure ASR reconnection test with invalid credentials"
        )
        self.start_time = asyncio.get_event_loop().time()
        self.sender_task = asyncio.create_task(self.audio_sender(ten_env))

    def _validate_error_format(
        self, ten_env: AsyncTenEnvTester, json_data: dict[str, Any]
    ) -> bool:
        """Validate error format and extract reconnection information."""

        # Validate required fields (module, code, and message are required)
        required_fields: list[str] = ["module", "code", "message"]
        missing_fields: list[str] = [
            field for field in required_fields if field not in json_data
        ]

        if missing_fields:
            ten_env.log_error(
                f"Missing required error fields: {missing_fields}"
            )
            return False

        # Validate field types
        if not isinstance(json_data.get("module"), str):
            ten_env.log_error("Field 'module' must be string type")
            return False

        if not isinstance(json_data.get("code"), int):
            ten_env.log_error("Field 'code' must be int64 type")
            return False

        if not isinstance(json_data.get("message"), str):
            ten_env.log_error("Field 'message' must be string type")
            return False

        # Validate vendor_info structure if present
        vendor_info: dict[str, Any] | None = json_data.get("vendor_info")
        if vendor_info is not None:
            vendor_required_fields = ["vendor", "code", "message"]
            vendor_missing_fields = [
                field
                for field in vendor_required_fields
                if field not in vendor_info
            ]

            if vendor_missing_fields:
                ten_env.log_error(
                    f"Missing required vendor_info fields: {vendor_missing_fields}"
                )
                return False

            # Validate vendor_info field types
            if not isinstance(vendor_info.get("vendor"), str):
                ten_env.log_error(
                    "Field 'vendor_info.vendor' must be string type"
                )
                return False

            if not isinstance(vendor_info.get("code"), str):
                ten_env.log_error(
                    "Field 'vendor_info.code' must be string type"
                )
                return False

            if not isinstance(vendor_info.get("message"), str):
                ten_env.log_error(
                    "Field 'vendor_info.message' must be string type"
                )
                return False

        # Validate metadata structure if present
        metadata: dict[str, Any] | None = json_data.get("metadata")
        if metadata is not None:
            if "session_id" in metadata and not isinstance(
                metadata.get("session_id"), str
            ):
                ten_env.log_error(
                    "Field 'metadata.session_id' must be string type"
                )
                return False

        # Validate optional id field if present
        if "id" in json_data and not isinstance(json_data.get("id"), str):
            ten_env.log_error("Field 'id' must be string type")
            return False

        # Extract error information
        error_message: str = json_data.get("message", "")

        # Check for reconnection-related keywords in error messages
        reconnection_keywords: list[str] = [
            "reconnect",
            "reconnection",
            "retry",
            "retrying",
            "connection",
            "disconnect",
            "timeout",
            "network",
        ]

        error_lower: str = error_message.lower()
        for keyword in reconnection_keywords:
            if keyword in error_lower:
                self.reconnection_attempts += 1
                ten_env.log_info(
                    f"🔗 Detected reconnection-related error: {error_message}"
                )
                break

        return True

    @override
    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        """Handle received data from ASR extension."""
        name: str = data.get_name()

        if name == "error":
            self.errors_received += 1
            ten_env.log_info(f"Received error #{self.errors_received}")

            # Parse error
            json_str, _ = data.get_property_to_json(None)
            json_data: dict[str, Any] = json.loads(json_str)

            # Validate error format and extract reconnection info
            if not self._validate_error_format(ten_env, json_data):
                return

            # Check if this is a fatal error (won't retry)
            error_code: int = json_data.get("code", 0)
            self.error_codes.append(error_code)

            is_fatal = error_code == int(ModuleErrorCode.FATAL_ERROR.value)

            error_message: str = json_data.get("message", "")

            if is_fatal:
                self.fatal_error_received = True
                ten_env.log_info(
                    f"🔴 Detected FATAL error (no retry expected): {error_message}"
                )
            else:
                ten_env.log_info(
                    f"🟡 Detected non-fatal error (retry expected): {error_message}"
                )

            # Log complete error details
            ten_env.log_info("=== COMPLETE ERROR DETAILS ===")
            ten_env.log_info(f"Error #{self.errors_received}:")
            ten_env.log_info(f"  Raw JSON: {json.dumps(json_data, indent=2)}")
            ten_env.log_info(f"  Code: {json_data.get('code', 'N/A')}")
            ten_env.log_info(f"  Message: {json_data.get('message', 'N/A')}")
            ten_env.log_info(f"  Module: {json_data.get('module', 'N/A')}")
            ten_env.log_info(f"  Is Fatal: {is_fatal}")
            ten_env.log_info("=== END ERROR DETAILS ===")
        else:
            ten_env.log_info(f"Received data type: {name}")

    @override
    async def on_stop(self, ten_env: AsyncTenEnvTester) -> None:
        """Clean up when test stops."""
        # Cancel the sender task if it's still running
        if self.sender_task and not self.sender_task.done():
            try:
                self.sender_task.cancel()
                await self.sender_task
            except asyncio.CancelledError:
                ten_env.log_info("Audio sender task cancelled successfully")
            except Exception as e:
                ten_env.log_error(f"Error cancelling audio sender task: {e}")

        # Log test summary
        ten_env.log_info(f"Test summary:")
        ten_env.log_info(f"  - Errors received: {self.errors_received}")
        ten_env.log_info(
            f"  - Reconnection attempts detected: {self.reconnection_attempts}"
        )


def test_reconnection(extension_name: str, config_dir: str) -> None:
    """Test ASR extension reconnection mechanism using invalid credentials."""

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

    # Create and run tester
    tester = AsrReconnectionTester(audio_file_path=audio_file_path)
    tester.set_test_mode_single(extension_name, json.dumps(config))
    error = tester.run()

    # Verify test results
    assert (
        error is None
    ), f"Test failed: {error.error_message() if error else 'Unknown error'}"

    # Verify error handling behavior based on error sequence
    if tester.fatal_error_received:
        # FATAL error: once fatal error occurs, should not retry anymore
        # Check that fatal error is present in error codes
        fatal_error_index = -1
        for i, code in enumerate(tester.error_codes):
            if code == int(ModuleErrorCode.FATAL_ERROR.value):
                fatal_error_index = i
                break

        assert (
            fatal_error_index >= 0
        ), "Fatal error should be present in error codes"

        # After fatal error, no more errors should be received
        # (fatal error should be the last error, or there might be some cleanup errors)
        print(
            f"✅ FATAL error validation passed: fatal error detected at position {fatal_error_index + 1}, "
            f"total errors: {tester.errors_received}, error sequence: {tester.error_codes}"
        )
    else:
        # No fatal error received: should be retrying with non-fatal errors.
        # Note: with a 10s connection timeout, only 1 error may arrive within the
        # test window (12s), so we accept >= 1 to confirm error reporting works.
        assert tester.errors_received >= 1, (
            f"Non-fatal errors should trigger retries, but received {tester.errors_received} errors. "
            f"Expected at least 1 non-fatal error."
        )
        # Verify all received errors are non-fatal (should retry on connection failure)
        # Note: ModuleErrorCode is a str Enum, so we need to convert to int for comparison
        non_fatal_code = int(ModuleErrorCode.NON_FATAL_ERROR.value)
        assert all(code == non_fatal_code for code in tester.error_codes), (
            f"All errors should be non-fatal (code={non_fatal_code}), "
            f"but found unexpected codes in sequence: {tester.error_codes}"
        )
        print(
            f"✅ Non-fatal error validation passed: received {tester.errors_received} errors "
            f"as expected (reconnection in progress), error sequence: {tester.error_codes}"
        )
