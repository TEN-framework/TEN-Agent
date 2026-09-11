#!/usr/bin/env python3
#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import json
import os
from typing import Any

import pytest
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    TenError,
    TenErrorCode,
)
from typing_extensions import override


TTS_CONNECTION_STATUS_CONFIG_FILE = "property_basic_audio_setting1.json"
SUPPORTED_WEBSOCKET_TTS_EXTENSIONS = {
    "bytedance_tts",
    "bytedance_tts_duplex",
    "minimax_tts_websocket",
    "minimax_tts_websocket_python",
    "rime_tts",
}


class ConnectionStatusTester(AsyncExtensionTester):
    """Validate websocket TTS connection status events."""

    def __init__(
        self,
        extension_name: str,
        session_id: str = "test_connection_status_session_123",
        text: str = "",
    ):
        super().__init__()
        print("=" * 80)
        print("TEST CASE: TTS Connection Status Test")
        print("=" * 80)
        print("Test objective: validate websocket TTS connection status events")
        print("=" * 80)

        self.extension_name = extension_name
        self.session_id = session_id
        self.text = text
        self.request_id = "test_connection_status_request_id_1"
        self.status_events: list[dict[str, Any]] = []
        self.audio_end_received = False

    @override
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        """Send one TTS request to force the websocket connection path."""
        await self._send_tts_text_input(ten_env)

    async def _send_tts_text_input(self, ten_env: AsyncTenEnvTester) -> None:
        ten_env.log_info(f"Sending tts text input: {self.text}")
        tts_text_input = Data.create("tts_text_input")
        tts_text_input.set_property_string("text", self.text)
        tts_text_input.set_property_string("request_id", self.request_id)
        tts_text_input.set_property_bool("text_input_end", True)
        tts_text_input.set_property_from_json(
            "metadata",
            json.dumps({"session_id": self.session_id, "turn_id": 1}),
        )
        await ten_env.send_data(tts_text_input)
        ten_env.log_info("TTS text input sent")

    def _stop_test_with_error(
        self, ten_env: AsyncTenEnvTester, error_message: str
    ) -> None:
        ten_env.stop_test(
            TenError.create(TenErrorCode.ErrorCodeGeneric, error_message)
        )

    @override
    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        """Collect connection status events and finish after audio end."""
        name = data.get_name()
        json_str, _ = data.get_property_to_json("")
        ten_env.log_info(f"Received data {name}: {json_str}")

        if name == "error":
            self._stop_test_with_error(ten_env, "Received error data")
            return

        if name == "connection_status_changed":
            self._handle_connection_status(ten_env, json_str)
            return

        if name == "tts_audio_end":
            self.audio_end_received = True
            self._validate_connection_status_events(ten_env)
            ten_env.stop_test()

    def _handle_connection_status(
        self, ten_env: AsyncTenEnvTester, json_str: str
    ) -> None:
        if not json_str:
            self._stop_test_with_error(
                ten_env, "connection_status_changed has empty payload"
            )
            return

        try:
            payload = json.loads(json_str)
        except json.JSONDecodeError as exc:
            self._stop_test_with_error(
                ten_env,
                f"Invalid connection_status_changed JSON: {exc}",
            )
            return

        self.status_events.append(payload)
        ten_env.log_info(f"Collected connection status event: {payload}")

    def _validate_connection_status_events(
        self, ten_env: AsyncTenEnvTester
    ) -> None:
        if not self.status_events:
            self._stop_test_with_error(
                ten_env, "No connection_status_changed event received"
            )
            return

        statuses = [event.get("current") for event in self.status_events]
        if "connecting" not in statuses:
            self._stop_test_with_error(
                ten_env,
                f"Missing connecting status, received statuses: {statuses}",
            )
            return
        if "connected" not in statuses:
            self._stop_test_with_error(
                ten_env,
                f"Missing connected status, received statuses: {statuses}",
            )
            return
        if statuses.index("connecting") > statuses.index("connected"):
            self._stop_test_with_error(
                ten_env,
                f"connecting must be reported before connected: {statuses}",
            )
            return

        for event in self.status_events:
            self._validate_event_payload(ten_env, event)

        ten_env.log_info(
            "Connection status events validated successfully: " f"{statuses}"
        )

    def _validate_event_payload(
        self, ten_env: AsyncTenEnvTester, event: dict[str, Any]
    ) -> None:
        expected_fields = [
            "id",
            "module",
            "vendor_info",
            "current",
            "last",
        ]
        missing = [field for field in expected_fields if field not in event]
        if missing:
            self._stop_test_with_error(
                ten_env,
                f"connection_status_changed missing fields: {missing}",
            )
            return

        if event.get("module") != "tts":
            self._stop_test_with_error(
                ten_env,
                f"Expected module tts, received: {event.get('module')}",
            )
            return

        if event.get("current") not in {
            "connecting",
            "connected",
            "disconnected",
        }:
            self._stop_test_with_error(
                ten_env,
                f"Unexpected connection status: {event.get('current')}",
            )
            return

        vendor_info = event.get("vendor_info")
        if not isinstance(vendor_info, dict) or not vendor_info.get("vendor"):
            self._stop_test_with_error(
                ten_env, "Missing vendor_info.vendor in event"
            )


def test_connection_status(extension_name: str, config_dir: str) -> None:
    """Verify websocket TTS connection status reporting."""
    enable_connection_status = os.environ.get(
        "ENABLE_CONNECTION_STATUS", "False"
    )
    if enable_connection_status.lower() != "true":
        pytest.skip("connection status test is only enabled for websocket TTS")

    if extension_name not in SUPPORTED_WEBSOCKET_TTS_EXTENSIONS:
        pytest.skip(
            "connection status test supports only websocket TTS extensions: "
            f"{sorted(SUPPORTED_WEBSOCKET_TTS_EXTENSIONS)}, "
            f"got {extension_name}"
        )

    config_file_path = os.path.join(
        config_dir, TTS_CONNECTION_STATUS_CONFIG_FILE
    )
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")

    with open(config_file_path, "r", encoding="utf-8") as config_file:
        config: dict[str, Any] = json.load(config_file)

    tester = ConnectionStatusTester(
        extension_name=extension_name,
        text="hello world, hello agora, hello shanghai, nice to meet you!",
    )
    tester.set_test_mode_single(extension_name, json.dumps(config))
    error = tester.run()

    assert (
        error is None
    ), f"Test failed: {error.error_message() if error else 'Unknown error'}"
    assert tester.audio_end_received, "tts_audio_end was not received"
