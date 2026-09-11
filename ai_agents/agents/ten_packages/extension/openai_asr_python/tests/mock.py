#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import pytest
import asyncio
import uuid
from typing import Callable
from unittest.mock import MagicMock, patch, AsyncMock
from ten_packages.extension.openai_asr_python.openai_asr_client import (
    AsyncOpenAIAsrListener,
    Session,
    TranscriptionParam,
    TranscriptionResultCommitted,
    TranscriptionResultCompleted,
    TranscriptionResultDelta,
)


class MockClient(object):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.listener: AsyncOpenAIAsrListener = kwargs["listener"]
        self.kwargs = kwargs
        self._is_connected = False
        self.mock_response_callback: Callable = self._mock_response
        # self.send_pcm_data = AsyncMock()
        assert self.listener is not None, "listener is required"
        self._is_ready = False

    async def _mock_response(self, voice_id: str | None = None):
        await asyncio.sleep(1)

        words = [
            "",
            "hello",
            "world",
            "I'm",
            "the",
            "ten",
            "framework",
            "extension",
            "test",
            "case",
        ]
        for index, word in enumerate(words):
            if index != len(words) - 1:
                await self.listener.on_asr_delta(
                    TranscriptionResultDelta(
                        type="conversation.item.input_audio_transcription.delta",
                        event_id="event_123",
                        item_id="item_123",
                        content_index=index,
                        delta=word,
                    )
                )
            else:
                await self.listener.on_asr_completed(
                    TranscriptionResultCompleted(
                        type="conversation.item.input_audio_transcription.completed",
                        event_id="event_123",
                        item_id="item_123",
                        content_index=index,
                        transcript=" ".join(words[: index + 1]),
                        usage=TranscriptionResultCompleted.Usage(
                            type="duration",
                            seconds=10,
                        ),
                    )
                )
                await self.listener.on_asr_committed(
                    TranscriptionResultCommitted(
                        type="input_audio_buffer.committed",
                        event_id="event_123",
                        item_id="item_123",
                    )
                )
            await asyncio.sleep(0.2)

    async def send_pcm_data(self, data: bytes):
        pass

    async def send_end_of_stream(self):
        pass

    async def send_heartbeat(self):
        pass

    async def start(self):
        self._is_ready = True
        voice_id = str(uuid.uuid4())
        await self.listener.on_asr_start(
            Session(
                type="session.updated",
                event_id="event_123",
                session=TranscriptionParam(
                    input_audio_format="pcm16",
                    input_audio_transcription={
                        "model": "whisper-1",
                        "prompt": "Please transcribe the following audio into text. Output in English.",
                        "language": "en",
                    },
                    turn_detection=None,
                    input_audio_noise_reduction=None,
                    include=None,
                ),
            )
        )
        if self.mock_response_callback is not None:
            await self.mock_response_callback(voice_id)

    async def stop(self):
        self._is_connected = False

    async def send(self, data: bytes):
        pass

    def is_ready(self):
        return self._is_ready

    def is_connected(self):
        return self.is_ready()


@pytest.fixture(scope="function")
def patch_asr_client():
    with patch(
        "ten_packages.extension.openai_asr_python.extension.OpenAIAsrClient"
    ) as MockTencentAsrClient:
        MockTencentAsrClient.side_effect = MockClient
        yield MockTencentAsrClient
