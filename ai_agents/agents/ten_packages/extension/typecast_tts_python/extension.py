#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import os

from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2_http import (
    AsyncTTS2HttpClient,
    AsyncTTS2HttpConfig,
    AsyncTTS2HttpExtension,
)
from ten_ai_base.message import TTSAudioEndReason
from ten_runtime import AsyncTenEnv

from .config import TypecastTTSConfig
from .typecast_tts import TYPECAST_STREAM_SAMPLE_RATE, TypecastTTSClient


class TypecastTTSExtension(AsyncTTS2HttpExtension):
    """Typecast TTS extension using Typecast streaming TTS."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: TypecastTTSConfig = None
        self.client: TypecastTTSClient = None
        self._emitted_audio_bytes = 0
        self._dump_start_offset = 0
        self._finish_task: asyncio.Task | None = None
        self._terminal_audio_sent = False

    async def create_config(self, config_json_str: str) -> AsyncTTS2HttpConfig:
        return TypecastTTSConfig.model_validate_json(config_json_str)

    async def create_client(
        self, config: AsyncTTS2HttpConfig, ten_env: AsyncTenEnv
    ) -> AsyncTTS2HttpClient:
        return TypecastTTSClient(config=config, ten_env=ten_env)

    def vendor(self) -> str:
        return "typecast"

    def synthesize_audio_sample_rate(self) -> int:
        return TYPECAST_STREAM_SAMPLE_RATE

    async def request_tts(self, t: TTSTextInput) -> None:
        if t.request_id != self.current_request_id:
            # A flush may cancel the child before the HTTP base initializes it.
            # The previous request's audio start must not survive this boundary.
            self.request_ts = None
            self._emitted_audio_bytes = 0
            self._finish_task = None
            self._terminal_audio_sent = False
            self._dump_start_offset = 0
        # Let the inherited flush path cancel the HTTP wait, not the queue loop.
        task = asyncio.create_task(super().request_tts(t))
        self.current_task = task
        try:
            await task
        finally:
            if self.client:
                await self.client.close_stream()
            if self.current_task is task:
                self.current_task = None

    async def send_tts_audio_start(
        self,
        request_id: str,
        turn_id: int = -1,
        extra_metadata: dict | None = None,
    ) -> None:
        # Keep the HTTP base timestamp visible while the start send is pending:
        # the flush path signals child cancellation without waiting for it.
        start_ts = self.request_ts
        try:
            recorder = self.recorder_map.get(request_id)
            if recorder:
                # Capture the append offset before the first write, inside the
                # inherited request error handler so a stat failure can finalize.
                try:
                    self._dump_start_offset = os.path.getsize(
                        recorder.file_name
                    )
                except FileNotFoundError:
                    self._dump_start_offset = 0
            await super().send_tts_audio_start(
                request_id, turn_id, extra_metadata
            )
        finally:
            # Preserve timing even when the pending start send is cancelled.
            self.request_ts = start_ts

    async def send_tts_audio_data(
        self, audio_data: bytes, timestamp: int = 0
    ) -> None:
        await super().send_tts_audio_data(audio_data, timestamp)
        self._emitted_audio_bytes += len(audio_data)

    async def cancel_tts(self) -> None:
        if self._finish_task is not None:
            # Finish the winning terminal event before acknowledging a flush.
            await self._send_audio_end_and_finish(
                self.current_request_id, TTSAudioEndReason.INTERRUPTED
            )
            return
        # Received bytes can include a frame cancelled before its send completed.
        self.total_audio_bytes = self._emitted_audio_bytes
        await super().cancel_tts()

    async def _send_audio_end_and_finish(
        self,
        request_id: str,
        reason: TTSAudioEndReason,
        log_message: str | None = None,
    ) -> None:
        if self._finish_task is None or (
            self._finish_task.done()
            and self._finish_task.exception() is not None
        ):
            self._finish_task = asyncio.create_task(
                self._finish_audio(request_id, reason, log_message)
            )
        # Cancellation must not split terminal emission from state cleanup.
        await asyncio.shield(self._finish_task)

    async def send_tts_audio_end(self, *args, **kwargs) -> None:
        # A failed usage/dump cleanup may retry the terminal path after emission.
        if not self._terminal_audio_sent:
            await super().send_tts_audio_end(*args, **kwargs)
            self._terminal_audio_sent = True

    async def _finish_audio(
        self,
        request_id: str,
        reason: TTSAudioEndReason,
        log_message: str | None,
    ) -> None:
        self.total_audio_bytes = self._emitted_audio_bytes
        # The base PCMWriter may retain tail bytes while a write is in flight.
        # Its cleanup flush then writes those bytes on this second pass.
        recorder = self.recorder_map.get(request_id)
        if recorder:
            await recorder.flush()
            if reason == TTSAudioEndReason.INTERRUPTED:
                await recorder.flush()
                # Discard the received chunk if its frame send was cancelled.
                if os.path.exists(recorder.file_name):
                    await asyncio.to_thread(
                        os.truncate,
                        recorder.file_name,
                        self._dump_start_offset + self._emitted_audio_bytes,
                    )

        await super()._send_audio_end_and_finish(
            request_id=request_id,
            reason=reason,
            log_message=log_message,
        )
