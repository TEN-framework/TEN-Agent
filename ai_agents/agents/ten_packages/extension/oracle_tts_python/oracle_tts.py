#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import struct
import time
from typing import AsyncIterator

import oci
import oci.ai_speech
import oci.ai_speech.models

from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR

from .config import OracleTTSConfig

EVENT_TTS_RESPONSE = 1
EVENT_TTS_REQUEST_END = 2
EVENT_TTS_ERROR = 3
EVENT_TTS_INVALID_KEY_ERROR = 4


class OracleTTS:
    def __init__(
        self,
        config: OracleTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        self.config = config
        self.ten_env = ten_env
        self.client: oci.ai_speech.AIServiceSpeechClient | None = None
        self._is_cancelled = False
        self._initialize_client()

    def _initialize_client(self) -> None:
        params = self.config.params
        oci_config = {
            "tenancy": params.get("tenancy", ""),
            "user": params.get("user", ""),
            "fingerprint": params.get("fingerprint", ""),
            "key_file": params.get("key_file", ""),
            "region": params.get("region") or "us-phoenix-1",
        }
        oci.config.validate_config(oci_config)
        self.client = oci.ai_speech.AIServiceSpeechClient(oci_config)
        self.ten_env.log_debug(
            f"vendor_status: OCI Speech client initialized, region={oci_config['region']}",
            category=LOG_CATEGORY_VENDOR,
        )

    _KNOWN_MODELS = {"TTS_1_STANDARD", "TTS_2_NATURAL"}

    def _build_model_details(
        self,
    ) -> oci.ai_speech.models.TtsOracleModelDetails:
        params = self.config.params
        model_name = params.get("model_name", "TTS_2_NATURAL")
        voice_id = params.get("voice_id", "Annabelle")
        language_code = params.get("language_code", "en-US")

        if model_name not in self._KNOWN_MODELS:
            raise ValueError(
                f"Unknown TTS model: {model_name}. "
                f"Known models: {sorted(self._KNOWN_MODELS)}"
            )

        if model_name == "TTS_1_STANDARD":
            return oci.ai_speech.models.TtsOracleTts1StandardModelDetails(
                model_name="TTS_1_STANDARD",
                voice_id=voice_id,
            )

        return oci.ai_speech.models.TtsOracleTts2NaturalModelDetails(
            model_name="TTS_2_NATURAL",
            voice_id=voice_id,
            language_code=language_code,
        )

    def _build_speech_settings(
        self,
    ) -> oci.ai_speech.models.TtsOracleSpeechSettings:
        params = self.config.params
        sample_rate = int(params.get("sample_rate", 16000))
        output_format = params.get("output_format", "PCM")

        return oci.ai_speech.models.TtsOracleSpeechSettings(
            text_type="TEXT",
            sample_rate_in_hz=sample_rate,
            output_format=output_format,
        )

    @staticmethod
    def _strip_wav_header(audio: bytes) -> bytes:
        """Strip WAV/RIFF header from complete audio data, returning raw PCM.

        Oracle TTS with is_stream_enabled=True may declare an inaccurate
        data chunk size in the WAV header. This method handles two cases:
        1. chunk_size is accurate and there are trailing WAV metadata chunks
           -> use chunk_size to exclude trailing non-PCM data (prevents pops)
        2. chunk_size is too small (streaming placeholder)
           -> use all remaining bytes (prevents truncation)
        """
        if len(audio) < 44 or audio[:4] != b"RIFF":
            return audio

        if audio[8:12] != b"WAVE":
            return audio

        pos = 12
        while pos + 8 <= len(audio):
            chunk_id = audio[pos : pos + 4]
            chunk_size = struct.unpack_from("<I", audio, pos + 4)[0]
            if chunk_id == b"data":
                data_start = pos + 8
                remaining = len(audio) - data_start

                # Check if chunk_size leads to a valid subsequent WAV chunk.
                # If so, chunk_size accurately marks where PCM ends and
                # trailing metadata begins — trust it to avoid pops.
                next_pos = data_start + chunk_size
                if chunk_size % 2 == 1:
                    next_pos += 1
                _KNOWN_TRAILING_CHUNKS = {
                    b"LIST",
                    b"fact",
                    b"id3 ",
                    b"INFO",
                    b"PEAK",
                    b"bext",
                    b"JUNK",
                    b"cue ",
                }
                has_trailing_chunk = (
                    next_pos + 8 <= len(audio)
                    and audio[next_pos : next_pos + 4] in _KNOWN_TRAILING_CHUNKS
                )

                if has_trailing_chunk and chunk_size <= remaining:
                    pcm = audio[data_start : data_start + chunk_size]
                else:
                    pcm = audio[data_start:]

                # Ensure even byte count for 16-bit PCM
                if len(pcm) % 2 != 0:
                    pcm = pcm[:-1]
                return pcm

            pos += 8 + chunk_size
            if pos % 2 == 1:
                pos += 1

        pcm = audio[44:]
        if len(pcm) % 2 != 0:
            pcm = pcm[:-1]
        return pcm

    def _get_audio_bytes(self, text: str) -> bytes:
        """Synchronous: call OCI TTS API and return clean raw PCM audio bytes.

        1. Call Oracle synthesize_speech API
        2. Strip WAV header (handles both truncation and trailing data)
        """
        params = self.config.params
        compartment_id = params.get("compartment_id", "")

        details = oci.ai_speech.models.SynthesizeSpeechDetails(
            text=text,
            is_stream_enabled=True,
            compartment_id=compartment_id,
            configuration=oci.ai_speech.models.TtsOracleConfiguration(
                model_family="ORACLE",
                model_details=self._build_model_details(),
                speech_settings=self._build_speech_settings(),
            ),
        )
        response = self.client.synthesize_speech(
            synthesize_speech_details=details,
        )

        data = response.data
        if hasattr(data, "content"):
            raw = data.content
        elif hasattr(data, "iter_content"):
            raw = b"".join(c for c in data.iter_content(chunk_size=65536) if c)
        elif hasattr(data, "read"):
            raw = data.read()
        else:
            raw = bytes(data)

        return self._strip_wav_header(raw)

    async def _get_audio_bytes_cancellable(self, text: str) -> bytes | None:
        """Run _get_audio_bytes in a thread, returning None if cancelled.

        Polls ``_is_cancelled`` every 100 ms so that the queue processor
        is not blocked when a flush/cancel arrives while the synchronous
        OCI API call is still in flight.
        """
        fut = asyncio.get_event_loop().run_in_executor(
            None, self._get_audio_bytes, text
        )
        while not fut.done():
            if self._is_cancelled:
                fut.cancel()
                return None
            await asyncio.sleep(0.1)
        return fut.result()

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[tuple[bytes | None, int, int | None]]:
        """Generate TTS audio for the given text via Oracle OCI Speech API."""
        self._is_cancelled = False

        if not self.client:
            yield "OCI Speech client not initialized".encode(
                "utf-8"
            ), EVENT_TTS_ERROR, None
            return

        self.ten_env.log_debug(
            f"send_text_to_tts_server: {text} of request_id: {request_id}",
            category=LOG_CATEGORY_VENDOR,
        )

        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            ttfb_ms: int | None = None
            try:
                start_ts = time.time()

                audio_data = await self._get_audio_bytes_cancellable(text)

                if audio_data is None:
                    return
                ttfb_ms = int((time.time() - start_ts) * 1000)

                self.ten_env.log_debug(
                    f"vendor_latency: ttfb={ttfb_ms}ms, "
                    f"audio_bytes={len(audio_data)}, "
                    f"request_id={request_id}",
                    category=LOG_CATEGORY_VENDOR,
                )

                if not audio_data:
                    yield "No audio content received from Oracle TTS".encode(
                        "utf-8"
                    ), EVENT_TTS_ERROR, None
                    return

                chunk_size = 4096
                first_chunk = True
                for i in range(0, len(audio_data), chunk_size):
                    if self._is_cancelled:
                        break
                    chunk = audio_data[i : i + chunk_size]
                    yield chunk, EVENT_TTS_RESPONSE, (
                        ttfb_ms if first_chunk else None
                    )
                    first_chunk = False
                    await asyncio.sleep(0)

                yield None, EVENT_TTS_REQUEST_END, None
                return

            except oci.exceptions.ServiceError as e:
                error_message = str(e)
                self.ten_env.log_error(
                    f"vendor_error: code: {e.status} reason: {e.message}",
                    category=LOG_CATEGORY_VENDOR,
                )

                if e.status in (401, 403):
                    yield error_message.encode(
                        "utf-8"
                    ), EVENT_TTS_INVALID_KEY_ERROR, ttfb_ms
                    return

                if (
                    e.status in (429, 500, 502, 503)
                    and attempt < max_retries - 1
                ):
                    self.ten_env.log_debug(
                        f"Retryable error (attempt {attempt + 1}/{max_retries}): {error_message}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                yield error_message.encode("utf-8"), EVENT_TTS_ERROR, ttfb_ms
                return

            except Exception as e:
                error_message = str(e)
                self.ten_env.log_error(
                    f"vendor_error: {error_message}",
                    category=LOG_CATEGORY_VENDOR,
                )

                is_retryable = any(
                    kw in error_message.lower()
                    for kw in ("timeout", "connection", "socket")
                )
                if is_retryable and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                if any(
                    kw in error_message.lower()
                    for kw in ("401", "403", "auth", "credentials")
                ):
                    yield error_message.encode(
                        "utf-8"
                    ), EVENT_TTS_INVALID_KEY_ERROR, ttfb_ms
                else:
                    yield error_message.encode(
                        "utf-8"
                    ), EVENT_TTS_ERROR, ttfb_ms
                return

    def cancel(self) -> None:
        self._is_cancelled = True

    def clean(self) -> None:
        self._is_cancelled = True
        self.client = None
