import asyncio
import json
from types import SimpleNamespace

import pytest

from stepfun_asr_python.config import StepFunASRConfig
from stepfun_asr_python.recognition import (
    StepFunASRRecognition,
    StepFunASRRecognitionCallback,
    TranscriptSegment,
)


class Callback(StepFunASRRecognitionCallback):
    def __init__(self):
        self.messages = []
        self.sent_bytes = []
        self.errors = []
        self.closed = 0

    async def on_result(self, message, segment: TranscriptSegment):
        self.messages.append((message, segment))

    async def on_audio_sent(self, total_bytes: int):
        self.sent_bytes.append(total_bytes)

    async def on_error(self, message, error_type="", error_code=""):
        self.errors.append((message, error_type, error_code))

    async def on_close(self):
        self.closed += 1


class FakeWebSocket:
    def __init__(self):
        self.open = True
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self):
        self.open = False


def config():
    return StepFunASRConfig.model_validate(
        {
            "params": {
                "api_key": "test-key",
                "url": "wss://example.test/asr",
                "model": "stepaudio-2.5-asr-stream",
                "language": "en",
                "sample_rate": 16000,
                "bits": 16,
                "channels": 1,
            }
        }
    )


@pytest.mark.asyncio
async def test_send_audio_and_commit_use_fifo():
    callback = Callback()
    recognition = StepFunASRRecognition(config(), SimpleNamespace(), callback)
    websocket = FakeWebSocket()
    recognition.websocket = websocket
    recognition._started = True
    recognition._generation = 1

    await recognition.send_audio(b"\x01\x02" * 160)
    await recognition.commit("final-1", asyncio.get_running_loop().time())

    events = [item["type"] for item in websocket.sent]
    assert events == [
        "input_audio_buffer.append",
        "input_audio_buffer.commit",
    ]
    assert callback.sent_bytes == [320]
    assert recognition._pending[0].finalize_id == "final-1"


@pytest.mark.asyncio
async def test_completed_message_is_bound_to_committed_audio():
    callback = Callback()
    recognition = StepFunASRRecognition(config(), SimpleNamespace(), callback)
    recognition._started = True
    recognition._generation = 1
    recognition.websocket = FakeWebSocket()
    await recognition.send_audio(b"\x01\x02" * 160)
    await recognition.commit("final-1", 1.0)

    await recognition._handle_message(
        {
            "type": "input_audio_buffer.committed",
            "item_id": "item-1",
        }
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-1",
            "transcript": "hello",
            "words": [{"word": "hello", "start": 0.0, "end": 0.1}],
        }
    )

    assert callback.messages[0][0]["transcript"] == "hello"
    assert callback.messages[0][1].finalize_id == "final-1"
