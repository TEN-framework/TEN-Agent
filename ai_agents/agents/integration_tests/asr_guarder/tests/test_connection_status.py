#!/usr/bin/env python3
#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from typing import Any, Callable
from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    AudioFrame,
    TenError,
    TenErrorCode,
)
from ten_ai_base.message import ModuleErrorCode
import json
import asyncio
import os
import pytest

from .test_reconnection import (
    AsrReconnectionTester,
    AUDIO_CHUNK_SIZE as RECONNECTION_AUDIO_CHUNK_SIZE,
    DEFAULT_CONFIG_FILE as RECONNECTION_CONFIG_FILE,
    DEFAULT_SESSION_ID as RECONNECTION_SESSION_ID,
    FRAME_INTERVAL_MS as RECONNECTION_FRAME_INTERVAL_MS,
)

# Constants for audio configuration
AUDIO_CHUNK_SIZE = 320
FRAME_INTERVAL_MS = 10

# Constants for test configuration
CONNECTION_STATUS_CONFIG_FILE = "property_en.json"
CONNECTION_STATUS_SESSION_ID = "test_connection_status_session_123"
CONNECTION_STATUS_TIMEOUT_SECONDS = 30
RECONNECTION_STATUS_TIMEOUT_SECONDS = 45

# Extensions that report connection_status_changed via ten_ai_base.
_EXTENSIONS_WITH_CONNECTION_STATUS = frozenset(
    {
        "azure_asr_python",
        "bytedance_llm_based_asr",
        "deepgram_asr_python",
        "smallest_asr_python",
        "soniox_asr_python",
        "tencent_asr_python",
    }
)

_CONNECTION_STATUSES = frozenset({"connecting", "connected", "disconnected"})


def is_valid_connection_transition(last: str, current: str) -> bool:
    if last == current:
        return False
    if current == "disconnected":
        return True
    if current == "connecting":
        return last in ("disconnected", "connected")
    if current == "connected":
        return last == "connecting"
    return False


def validate_status_payload(payload: dict[str, Any]) -> None:
    required_fields = [
        "id",
        "module",
        "vendor_info",
        "current",
        "last",
        "code",
        "message",
        "metadata",
    ]
    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        raise AssertionError(
            f"connection_status_changed missing fields: {missing_fields}"
        )

    if payload.get("module") != "asr":
        raise AssertionError(
            "connection_status_changed module should be 'asr', "
            f"got: {payload.get('module')}"
        )

    vendor_info = payload.get("vendor_info")
    if not isinstance(vendor_info, dict) or not vendor_info.get("vendor"):
        raise AssertionError(
            "connection_status_changed missing vendor_info.vendor: "
            f"{vendor_info}"
        )

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise AssertionError(
            f"connection_status_changed metadata should be dict: {metadata}"
        )

    vendor_metadata = metadata.get("vendor_metadata")
    if not isinstance(vendor_metadata, dict):
        raise AssertionError(
            "connection_status_changed metadata.vendor_metadata "
            f"should be dict: {vendor_metadata}"
        )

    current = payload.get("current")
    if current not in _CONNECTION_STATUSES:
        raise AssertionError(f"unexpected connection status current: {current}")


def assert_valid_connection_transitions(
    status_events: list[dict[str, Any]],
) -> None:
    for event in status_events:
        last = event["last"]
        current = event["current"]
        if not is_valid_connection_transition(last, current):
            raise AssertionError(
                "invalid connection transition: "
                f"{last} -> {current}; "
                f"sequence: {[event['current'] for event in status_events]}"
            )


def assert_initial_connection_status_sequence(
    status_events: list[dict[str, Any]],
) -> None:
    currents = [event["current"] for event in status_events]
    assert "connecting" in currents, (
        f"missing connecting status in sequence: {currents}"
    )
    assert "connected" in currents, (
        f"missing connected status in sequence: {currents}"
    )

    connecting_index = currents.index("connecting")
    connected_index = currents.index("connected")
    assert connecting_index < connected_index, (
        "connecting must appear before connected; "
        f"sequence: {currents}"
    )
    assert_valid_connection_transitions(status_events)


def assert_reconnection_status_sequence(
    status_events: list[dict[str, Any]],
    *,
    expect_retry: bool,
) -> None:
    assert status_events, "expected connection_status_changed events"
    assert_valid_connection_transitions(status_events)

    currents = [event["current"] for event in status_events]
    transitions = [(event["last"], event["current"]) for event in status_events]

    assert "connecting" in currents, (
        f"missing connecting status in reconnection sequence: {currents}"
    )
    assert "disconnected" in currents, (
        f"missing disconnected status in reconnection sequence: {currents}"
    )

    if expect_retry:
        assert currents.count("connecting") >= 2, (
            "reconnection should emit multiple connecting events; "
            f"sequence: {currents}"
        )
        assert ("disconnected", "connecting") in transitions, (
            "reconnection should include disconnected -> connecting transition; "
            f"transitions: {transitions}"
        )
    else:
        assert currents.count("connecting") >= 1, (
            f"expected at least one connecting event, got: {currents}"
        )


class ConnectionStatusAsrTester(AsyncExtensionTester):
    """Validate ASR extension connection_status_changed reporting."""

    def __init__(self, audio_file_path: str, session_id: str):
        super().__init__()
        print("=" * 80)
        print("🧪 TEST CASE: ASR Connection Status Test")
        print("=" * 80)
        print(
            "📋 Test Description: Validate connection_status_changed events from ASR extension"
        )
        print("🎯 Test Objectives:")
        print("   - Verify connecting -> connected status sequence")
        print("   - Validate connection_status_changed payload structure")
        print("   - Ensure vendor_info and vendor_metadata are present")
        print("=" * 80)

        self.audio_file_path = audio_file_path
        self.session_id = session_id
        self.status_events: list[dict[str, Any]] = []
        self.sender_task: asyncio.Task[None] | None = None
        self.timeout_task: asyncio.Task[None] | None = None
        self.stopped = False

    def _create_audio_frame(self, data: bytes, session_id: str) -> AudioFrame:
        audio_frame = AudioFrame.create("pcm_frame")
        metadata = {"session_id": session_id}
        audio_frame.set_property_from_json("metadata", json.dumps(metadata))
        audio_frame.alloc_buf(len(data))
        buf = audio_frame.lock_buf()
        buf[:] = data
        audio_frame.unlock_buf(buf)
        return audio_frame

    async def _send_audio_file(self, ten_env: AsyncTenEnvTester) -> None:
        ten_env.log_info(f"Sending audio file: {self.audio_file_path}")
        with open(self.audio_file_path, "rb") as audio_file:
            while not self.stopped:
                chunk = audio_file.read(AUDIO_CHUNK_SIZE)
                if not chunk:
                    break
                audio_frame = self._create_audio_frame(chunk, self.session_id)
                await ten_env.send_audio_frame(audio_frame)
                await asyncio.sleep(FRAME_INTERVAL_MS / 1000)

    async def _audio_sender(self, ten_env: AsyncTenEnvTester) -> None:
        try:
            await self._send_audio_file(ten_env)
            while not self.stopped:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def _timeout_handler(self, ten_env: AsyncTenEnvTester) -> None:
        await asyncio.sleep(CONNECTION_STATUS_TIMEOUT_SECONDS)
        self._stop_test_with_error(
            ten_env,
            (
                "Timed out waiting for connection_status_changed connected; "
                f"got: {self.status_events}"
            ),
        )

    @override
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        ten_env.log_info("Starting ASR connection status test")
        self.sender_task = asyncio.create_task(self._audio_sender(ten_env))
        self.timeout_task = asyncio.create_task(self._timeout_handler(ten_env))

    def _stop_test_with_error(
        self, ten_env: AsyncTenEnvTester, error_message: str
    ) -> None:
        ten_env.stop_test(
            TenError.create(TenErrorCode.ErrorCodeGeneric, error_message)
        )

    def _validate_status_payload(
        self,
        ten_env: AsyncTenEnvTester,
        payload: dict[str, Any],
    ) -> bool:
        try:
            validate_status_payload(payload)
        except AssertionError as exc:
            self._stop_test_with_error(ten_env, str(exc))
            return False
        return True

    def _validate_status_sequence(self, ten_env: AsyncTenEnvTester) -> bool:
        try:
            assert_initial_connection_status_sequence(self.status_events)
        except AssertionError as exc:
            self._stop_test_with_error(ten_env, str(exc))
            return False
        return True

    def _maybe_finish(self, ten_env: AsyncTenEnvTester) -> None:
        if not any(
            event.get("current") == "connected" for event in self.status_events
        ):
            return
        if not self._validate_status_sequence(ten_env):
            return

        ten_env.log_info(
            "✅ connection_status_changed sequence validated: "
            f"{[event['current'] for event in self.status_events]}"
        )
        self.stopped = True
        if self.timeout_task:
            self.timeout_task.cancel()
        if self.sender_task:
            self.sender_task.cancel()
        ten_env.stop_test()

    @override
    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        if data.get_name() != "connection_status_changed":
            return

        json_str, _ = data.get_property_to_json(None)
        payload: dict[str, Any] = json.loads(json_str)
        if not self._validate_status_payload(ten_env, payload):
            return

        self.status_events.append(payload)
        ten_env.log_info(
            "connection_status_changed: "
            f"{payload.get('last')} -> {payload.get('current')}, "
            f"vendor={payload.get('vendor_info', {}).get('vendor')}"
        )
        self._maybe_finish(ten_env)

    @override
    async def on_stop(self, ten_env: AsyncTenEnvTester) -> None:
        self.stopped = True
        if self.sender_task:
            self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass
        if self.timeout_task:
            self.timeout_task.cancel()
            try:
                await self.timeout_task
            except asyncio.CancelledError:
                pass
        ten_env.log_info("Test stopped")


class ConnectionStatusReconnectionTester(AsrReconnectionTester):
    """Validate connection_status_changed transitions during reconnection."""

    def __init__(self, audio_file_path: str):
        super().__init__(audio_file_path)
        print("=" * 80)
        print("🧪 TEST CASE: ASR Connection Status Reconnection Test")
        print("=" * 80)
        print(
            "📋 Test Description: Validate connection_status_changed during reconnection"
        )
        print("🎯 Test Objectives:")
        print("   - Reuse invalid-credential reconnection audio flow")
        print("   - Verify connecting/disconnected status transitions")
        print("   - Validate reconnect status sequence and payload structure")
        print("=" * 80)

        self.status_events: list[dict[str, Any]] = []

    def _stop_test_with_error(
        self, ten_env: AsyncTenEnvTester, error_message: str
    ) -> None:
        ten_env.stop_test(
            TenError.create(TenErrorCode.ErrorCodeGeneric, error_message)
        )

    def _reconnection_status_complete(self) -> bool:
        if not self.status_events:
            return False

        currents = [event["current"] for event in self.status_events]
        if "disconnected" not in currents:
            return False

        if self.fatal_error_received:
            return True

        transitions = [
            (event["last"], event["current"]) for event in self.status_events
        ]
        return (
            currents.count("connecting") >= 2
            and ("disconnected", "connecting") in transitions
        )

    async def _send_continuous_audio(self, ten_env: AsyncTenEnvTester) -> None:
        ten_env.log_info(
            "Starting continuous audio transmission for reconnection status test..."
        )

        await self._send_audio_file(ten_env)

        start_time = asyncio.get_event_loop().time()
        self.start_time = start_time

        while True:
            silence_frame = self._create_silence_frame(
                RECONNECTION_AUDIO_CHUNK_SIZE, RECONNECTION_SESSION_ID
            )
            await ten_env.send_audio_frame(silence_frame)
            await asyncio.sleep(RECONNECTION_FRAME_INTERVAL_MS / 1000)

            elapsed_time = asyncio.get_event_loop().time() - start_time
            if self._reconnection_status_complete():
                ten_env.log_info(
                    "✅ Reconnection status sequence complete: "
                    f"{[event['current'] for event in self.status_events]}"
                )
                ten_env.stop_test()
                break

            if elapsed_time >= RECONNECTION_STATUS_TIMEOUT_SECONDS:
                self._stop_test_with_error(
                    ten_env,
                    (
                        "Timed out waiting for reconnection status transitions; "
                        f"got: {[event['current'] for event in self.status_events]}, "
                        f"errors={self.error_codes}, "
                        f"fatal={self.fatal_error_received}"
                    ),
                )
                break

    def _record_connection_status(
        self,
        ten_env: AsyncTenEnvTester,
        payload: dict[str, Any],
        *,
        stop_on_invalid: Callable[[AsyncTenEnvTester, str], None],
    ) -> bool:
        try:
            validate_status_payload(payload)
        except AssertionError as exc:
            stop_on_invalid(ten_env, str(exc))
            return False

        self.status_events.append(payload)
        ten_env.log_info(
            "connection_status_changed: "
            f"{payload.get('last')} -> {payload.get('current')}, "
            f"vendor={payload.get('vendor_info', {}).get('vendor')}"
        )
        return True

    @override
    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        if data.get_name() == "connection_status_changed":
            json_str, _ = data.get_property_to_json(None)
            payload: dict[str, Any] = json.loads(json_str)
            if not self._record_connection_status(
                ten_env,
                payload,
                stop_on_invalid=self._stop_test_with_error,
            ):
                return
            if self._reconnection_status_complete():
                ten_env.log_info(
                    "✅ Reconnection status sequence complete: "
                    f"{[event['current'] for event in self.status_events]}"
                )
                ten_env.stop_test()
            return

        await super().on_data(ten_env, data)

    @override
    async def on_stop(self, ten_env: AsyncTenEnvTester) -> None:
        await super().on_stop(ten_env)
        ten_env.log_info(
            "connection_status_changed sequence: "
            f"{[event['current'] for event in self.status_events]}"
        )


def _load_test_config(config_dir: str, config_file: str) -> dict[str, Any]:
    config_file_path = os.path.join(config_dir, config_file)
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")

    with open(config_file_path, "r", encoding="utf-8") as config_file_handle:
        return json.load(config_file_handle)


def test_connection_status(extension_name: str, config_dir: str) -> None:
    """Verify ASR extension reports connection_status_changed on connect."""

    if extension_name not in _EXTENSIONS_WITH_CONNECTION_STATUS:
        pytest.skip(
            f"{extension_name} does not report connection_status_changed yet"
        )

    audio_file_path = os.path.join(
        os.path.dirname(__file__), "test_data/16k_en_us.pcm"
    )
    config = _load_test_config(config_dir, CONNECTION_STATUS_CONFIG_FILE)

    print(f"Using test configuration: {config}")
    print(f"Audio file path: {audio_file_path}")

    tester = ConnectionStatusAsrTester(
        audio_file_path=audio_file_path,
        session_id=CONNECTION_STATUS_SESSION_ID,
    )
    tester.set_test_mode_single(extension_name, json.dumps(config))
    error = tester.run()

    assert error is None, (
        f"Test failed: {error.error_message() if error else 'Unknown error'}"
    )
    assert_initial_connection_status_sequence(tester.status_events)


def test_connection_status_reconnection(
    extension_name: str, config_dir: str
) -> None:
    """Verify connection_status_changed transitions during reconnection."""

    if extension_name not in _EXTENSIONS_WITH_CONNECTION_STATUS:
        pytest.skip(
            f"{extension_name} does not report connection_status_changed yet"
        )

    audio_file_path = os.path.join(
        os.path.dirname(__file__), "test_data/16k_en_us.pcm"
    )
    config = _load_test_config(config_dir, RECONNECTION_CONFIG_FILE)

    print(f"Using test configuration: {config}")
    print(f"Audio file path: {audio_file_path}")

    tester = ConnectionStatusReconnectionTester(audio_file_path=audio_file_path)
    tester.set_test_mode_single(extension_name, json.dumps(config))
    error = tester.run()

    assert error is None, (
        f"Test failed: {error.error_message() if error else 'Unknown error'}"
    )

    expect_retry = not tester.fatal_error_received
    assert_reconnection_status_sequence(
        tester.status_events,
        expect_retry=expect_retry,
    )

    if tester.fatal_error_received:
        print(
            "✅ Reconnection status validation passed for fatal error path: "
            f"sequence={[event['current'] for event in tester.status_events]}"
        )
    else:
        non_fatal_code = int(ModuleErrorCode.NON_FATAL_ERROR.value)
        assert tester.errors_received >= 1, (
            "Non-fatal errors should trigger retries, but received "
            f"{tester.errors_received} errors."
        )
        assert all(
            code == non_fatal_code for code in tester.error_codes
        ), (
            f"All errors should be non-fatal (code={non_fatal_code}), "
            f"but found unexpected codes: {tester.error_codes}"
        )
        print(
            "✅ Reconnection status validation passed for retry path: "
            f"status={[event['current'] for event in tester.status_events]}, "
            f"errors={tester.error_codes}"
        )
