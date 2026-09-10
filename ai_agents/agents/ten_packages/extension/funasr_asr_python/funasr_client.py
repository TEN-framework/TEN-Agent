#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#

import asyncio
import re
from typing import Optional, Callable

import numpy as np
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


class FunASRClient:
    """Client for local FunASR ASR processing (SenseVoice / Fun-ASR-Nano / Paraformer)."""

    def __init__(
        self,
        model: str = "iic/SenseVoiceSmall",
        device: str = "cpu",
        language: str = "auto",
        use_itn: bool = True,
        sample_rate: int = 16000,
        on_result_callback: Optional[Callable] = None,
        on_error_callback: Optional[Callable] = None,
        logger: Optional[any] = None,
    ):
        self.model_id = model
        self.device = device
        self.language = language
        self.use_itn = use_itn
        self.sample_rate = sample_rate
        self.on_result_callback = on_result_callback
        self.on_error_callback = on_error_callback
        self.logger = logger

        self.model: Optional[AutoModel] = None
        self.audio_buffer = bytearray()
        self.processed_audio_duration_ms = 0
        self.is_connected_flag = False
        self.processing_lock = asyncio.Lock()

        # Buffer settings
        self.min_audio_length_ms = 1000  # Minimum 1 second of audio
        self.max_audio_length_ms = 30000  # Maximum 30 seconds per chunk

    async def connect(self) -> None:
        """Load the local FunASR model (off the event loop)."""
        try:
            if self.logger:
                self.logger.log_info(
                    f"Loading FunASR model: {self.model_id} on {self.device}"
                )

            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: AutoModel(
                    model=self.model_id,
                    device=self.device,
                    disable_update=True,
                ),
            )

            self.is_connected_flag = True
            if self.logger:
                self.logger.log_info("FunASR model loaded successfully")

        except Exception as e:
            self.is_connected_flag = False
            if self.logger:
                self.logger.log_error(f"Failed to load FunASR model: {e}")
            raise

    async def disconnect(self) -> None:
        """Clean up resources"""
        self.is_connected_flag = False
        self.model = None
        self.audio_buffer.clear()
        self.processed_audio_duration_ms = 0
        if self.logger:
            self.logger.log_info("FunASR client disconnected")

    def is_connected(self) -> bool:
        """Check if model is loaded"""
        return self.is_connected_flag and self.model is not None

    async def send_audio(self, audio_data: bytes) -> None:
        """Add audio data to buffer and process once enough has accumulated."""
        if not self.is_connected():
            return

        self.audio_buffer.extend(audio_data)

        # Calculate buffer duration in milliseconds (16-bit PCM => 2 bytes/sample)
        buffer_duration_ms = (
            len(self.audio_buffer) / (self.sample_rate * 2) * 1000
        )

        if buffer_duration_ms >= self.min_audio_length_ms:
            await self._process_audio()

    async def _process_audio(self) -> None:
        """Process accumulated audio buffer with the FunASR model."""
        async with self.processing_lock:
            if len(self.audio_buffer) == 0:
                return

            try:
                max_samples = max(
                    1,
                    int(self.max_audio_length_ms / 1000 * self.sample_rate),
                )
                sample_count = min(len(self.audio_buffer) // 2, max_samples)
                if sample_count == 0:
                    return
                byte_count = sample_count * 2
                audio_bytes = bytes(self.audio_buffer[:byte_count])
                del self.audio_buffer[:byte_count]

                # 16-bit PCM bytes -> float32 in [-1, 1]
                audio_np = (
                    np.frombuffer(audio_bytes, dtype=np.int16).astype(
                        np.float32
                    )
                    / 32768.0
                )

                duration_ms = int(len(audio_np) / self.sample_rate * 1000)
                start_ms = self.processed_audio_duration_ms
                self.processed_audio_duration_ms += duration_ms

                # Run inference in a thread pool to avoid blocking the loop
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(
                    None,
                    lambda: self.model.generate(
                        input=audio_np,
                        language=self.language,
                        use_itn=self.use_itn,
                    ),
                )

                # SenseVoice output carries tags like <|zh|><|NEUTRAL|>...; strip them.
                result = res[0] if res else {}
                raw_text = result.get("text", "")
                text = rich_transcription_postprocess(raw_text).strip()
                detected_language = self._extract_language(raw_text, result)

                if text and self.on_result_callback:
                    await self.on_result_callback(
                        text=text,
                        start_ms=start_ms,
                        duration_ms=duration_ms,
                        language=detected_language or self.language,
                        final=True,
                    )

            except Exception as e:
                if self.logger:
                    self.logger.log_error(f"Error processing audio: {e}")
                if self.on_error_callback:
                    await self.on_error_callback(str(e))

    @staticmethod
    def _extract_language(raw_text: str, result: dict) -> str:
        language = result.get("language") or result.get("lang")
        if language:
            return str(language)

        match = re.match(r"^<\|([a-z]{2,3})\|>", raw_text)
        return match.group(1) if match else ""

    async def finalize(self) -> None:
        """Process any remaining audio in buffer"""
        if len(self.audio_buffer) > 0:
            await self._process_audio()
