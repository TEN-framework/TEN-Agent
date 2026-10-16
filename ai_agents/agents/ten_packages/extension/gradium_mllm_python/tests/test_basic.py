"""
Drives the real extension lifecycle (via TEN's AsyncExtensionTester) with a
mocked GradiumS2SClient -- verifies setup, session-ready, translated text
and audio routing, and error propagation, without needing a live Gradium
connection or a real voice_id.
"""

import asyncio
import base64
import json
from unittest.mock import patch

from ten_runtime import AsyncExtensionTester, AsyncTenEnvTester, AudioFrame
from typing_extensions import override

from .gradium_mocks import make_streaming_mock_client

MOCK_CONFIG = {
    "api_key": "test_api_key",
    "voice_id": "test-voice-en",
    "target_language": "en",
}


class AudioSender:
    """Continuously sends silent PCM frames until stopped.

    Avoids racing against start_connection() completing (mirrors
    azure_asr_python's test pattern): if early frames arrive before the
    mocked connect() resolves, they're simply dropped by the base class's
    default buffer_strategy (discard) -- later frames still get through.
    """

    def __init__(self):
        self.stopped = False

    async def run(self, ten_env: AsyncTenEnvTester) -> None:
        while not self.stopped:
            frame = AudioFrame.create("pcm_frame")
            frame.set_property_from_json(
                "metadata", json.dumps({"session_id": "test-session"})
            )
            chunk = b"\x00\x01" * 160
            frame.alloc_buf(len(chunk))
            buf = frame.lock_buf()
            buf[:] = chunk
            frame.unlock_buf(buf)
            await ten_env.send_audio_frame(frame)
            await asyncio.sleep(0.05)


class ExtensionTesterBasic(AsyncExtensionTester):
    def __init__(self):
        super().__init__()
        self.sender = AudioSender()
        self.sender_task: asyncio.Task | None = None
        self.session_ready_received = False
        self.transcript_finals: list[str] = []
        self.audio_frames_received = 0

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.sender_task = asyncio.create_task(self.sender.run(ten_env_tester))

    @override
    async def on_data(self, ten_env_tester: AsyncTenEnvTester, data) -> None:
        name = data.get_name()
        if name == "mllm_server_session_ready":
            self.session_ready_received = True
        elif name == "mllm_server_output_transcript":
            json_str, _ = data.get_property_to_json(None)
            payload = json.loads(json_str)
            if payload.get("final"):
                self.transcript_finals.append(payload.get("content", ""))
                ten_env_tester.stop_test()

    @override
    async def on_audio_frame(self, _ten_env_tester, _audio_frame) -> None:
        self.audio_frames_received += 1

    @override
    async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.sender.stopped = True
        if self.sender_task:
            self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass


@patch("gradium_mllm_python.extension.GradiumS2SClient")
def test_session_ready_and_translated_output(mock_client_cls):
    audio_b64 = base64.b64encode(b"\x00\x01\x02").decode("ascii")
    mock_client_cls.return_value = make_streaming_mock_client(
        messages=[
            {"type": "audio", "audio": audio_b64},
            {"type": "text", "text": "Bonjour", "final": True},
        ]
    )

    tester = ExtensionTesterBasic()
    tester.set_test_mode_single("gradium_mllm_python", json.dumps(MOCK_CONFIG))
    err = tester.run()

    assert err is None, f"test failed: {err}"
    assert tester.session_ready_received
    assert tester.transcript_finals == ["Bonjour"]
    assert tester.audio_frames_received > 0


class ExtensionTesterError(AsyncExtensionTester):
    def __init__(self):
        super().__init__()
        self.sender = AudioSender()
        self.sender_task: asyncio.Task | None = None
        self.error_received = False
        self.error_code: int | None = None
        self.error_message: str | None = None
        self.vendor: str | None = None

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.sender_task = asyncio.create_task(self.sender.run(ten_env_tester))

    @override
    async def on_data(self, ten_env_tester: AsyncTenEnvTester, data) -> None:
        if data.get_name() == "error":
            json_str, _ = data.get_property_to_json(None)
            payload = json.loads(json_str)
            self.error_received = True
            self.error_code = payload.get("code")
            self.error_message = payload.get("message")
            self.vendor = payload.get("vendor_info", {}).get("vendor")
            ten_env_tester.stop_test()

    @override
    async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.sender.stopped = True
        if self.sender_task:
            self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass


@patch("gradium_mllm_python.extension.GradiumS2SClient")
def test_server_error_message_is_reported(mock_client_cls):
    mock_client_cls.return_value = make_streaming_mock_client(
        messages=[{"type": "error", "message": "quota exceeded", "code": "E429"}]
    )

    tester = ExtensionTesterError()
    tester.set_test_mode_single("gradium_mllm_python", json.dumps(MOCK_CONFIG))
    err = tester.run()

    assert err is None, f"test failed: {err}"
    assert tester.error_received
    assert tester.error_message == "quota exceeded"
    assert tester.vendor == "gradium"


@patch("gradium_mllm_python.extension.GradiumS2SClient")
def test_connect_failure_is_reported(mock_client_cls):
    mock_client_cls.return_value = make_streaming_mock_client(
        connect_error=RuntimeError("401 Unauthorized")
    )

    tester = ExtensionTesterError()
    tester.set_test_mode_single("gradium_mllm_python", json.dumps(MOCK_CONFIG))
    err = tester.run()

    assert err is None, f"test failed: {err}"
    assert tester.error_received
    assert tester.error_code == -1000
    assert "401 Unauthorized" in (tester.error_message or "")


def test_missing_voice_id_is_reported_without_connecting():
    tester = ExtensionTesterError()
    config = {"api_key": "test_api_key", "voice_id": ""}
    tester.set_test_mode_single("gradium_mllm_python", json.dumps(config))
    err = tester.run()

    assert err is None, f"test failed: {err}"
    assert tester.error_received
    assert tester.error_code == -1000
    assert "voice_id" in (tester.error_message or "")


def test_missing_api_key_is_reported_without_connecting():
    tester = ExtensionTesterError()
    config = {"api_key": "", "voice_id": "test-voice-en"}
    tester.set_test_mode_single("gradium_mllm_python", json.dumps(config))
    err = tester.run()

    assert err is None, f"test failed: {err}"
    assert tester.error_received
    assert tester.error_code == -1000
    assert "api_key" in (tester.error_message or "")
