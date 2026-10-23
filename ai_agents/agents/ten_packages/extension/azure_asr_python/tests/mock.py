#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from types import SimpleNamespace
import pytest
from unittest.mock import MagicMock, patch


def trigger_vendor_live(event_handlers: dict, session_id: str = "123") -> None:
    """Simulate Azure transport + recognizer session ready (matches production ordering)."""
    event = SimpleNamespace(session_id=session_id)
    connected = event_handlers.get("connected")
    if connected is not None:
        connected(event)
    event_handlers["session_started"](event)


@pytest.fixture(scope="function")
def patch_azure_ws():
    patch_target = "ten_packages.extension.azure_asr_python.extension.speechsdk.SpeechRecognizer"

    with patch(patch_target) as MockRecognizer, patch(
        "ten_packages.extension.azure_asr_python.extension.speechsdk.SpeechConfig"
    ) as MockSpeechConfig, patch(
        "ten_packages.extension.azure_asr_python.extension.speechsdk.audio.AudioConfig"
    ) as MockAudioConfig, patch(
        "ten_packages.extension.azure_asr_python.extension.speechsdk.audio.PushAudioInputStream"
    ) as MockStream, patch(
        "ten_packages.extension.azure_asr_python.extension.speechsdk.audio.AudioStreamFormat"
    ) as MockStreamFormat, patch(
        "ten_packages.extension.azure_asr_python.extension.speechsdk.Connection"
    ) as MockConnection:
        recognizer_instance = MagicMock()
        event_handlers = {}
        patch_azure_ws.event_handlers = event_handlers

        def connect_recognized_mock(callback):
            print(f"connect_recognized_mock: {callback}")
            event_handlers["recognized"] = callback

        def connect_recognizing_mock(callback):
            print(f"connect_recognizing_mock: {callback}")
            event_handlers["recognizing"] = callback

        def connect_session_started_mock(callback):
            print(f"connect_session_started_mock: {callback}")
            event_handlers["session_started"] = callback

        def connect_session_stopped_mock(callback):
            print(f"connect_session_stopped_mock: {callback}")
            event_handlers["session_stopped"] = callback

        def connect_canceled_mock(callback):
            print(f"connect_canceled_mock: {callback}")
            event_handlers["canceled"] = callback

        def connect_speech_start_detected_mock(callback):
            print(f"connect_speech_start_detected_mock: {callback}")
            event_handlers["speech_start_detected"] = callback

        def connect_speech_end_detected_mock(callback):
            print(f"connect_speech_end_detected_mock: {callback}")
            event_handlers["speech_end_detected"] = callback

        def connect_connected_mock(callback):
            print(f"connect_connected_mock: {callback}")
            event_handlers["connected"] = callback

        def connect_disconnected_mock(callback):
            print(f"connect_disconnected_mock: {callback}")
            event_handlers["disconnected"] = callback

        recognizer_instance.recognized.connect.side_effect = (
            connect_recognized_mock
        )
        recognizer_instance.recognizing.connect.side_effect = (
            connect_recognizing_mock
        )
        recognizer_instance.session_started.connect.side_effect = (
            connect_session_started_mock
        )
        recognizer_instance.session_stopped.connect.side_effect = (
            connect_session_stopped_mock
        )
        recognizer_instance.canceled.connect.side_effect = connect_canceled_mock
        recognizer_instance.speech_start_detected.connect.side_effect = (
            connect_speech_start_detected_mock
        )
        recognizer_instance.speech_end_detected.connect.side_effect = (
            connect_speech_end_detected_mock
        )

        MockRecognizer.return_value = recognizer_instance
        MockSpeechConfig.return_value = MagicMock()
        MockAudioConfig.return_value = MagicMock()
        MockStream.return_value = MagicMock()
        MockStreamFormat.return_value = MagicMock()

        connection_instance = MagicMock()
        connection_instance.connected.connect.side_effect = (
            connect_connected_mock
        )
        connection_instance.disconnected.connect.side_effect = (
            connect_disconnected_mock
        )

        MockConnection.from_recognizer.return_value = connection_instance

        fixture_obj = SimpleNamespace(
            recognizer_instance=recognizer_instance,
            event_handlers=event_handlers,
        )

        yield fixture_obj
