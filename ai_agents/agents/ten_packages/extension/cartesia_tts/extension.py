#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import copy
from datetime import datetime
import os
import traceback
import time
from typing import Any

from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleType,
    ModuleErrorVendorInfo,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput, TTSTextResult
from ten_ai_base.tts2 import AsyncTTS2BaseExtension, RequestState
from ten_ai_base.const import LOG_CATEGORY_VENDOR, LOG_CATEGORY_KEY_POINT
from .config import CartesiaTTSConfig

from .cartesia_tts import (
    CartesiaTTSClient,
    CartesiaTTSConnectionException,
)
from ten_runtime import AsyncTenEnv


class CartesiaTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: CartesiaTTSConfig | None = None
        self.client: CartesiaTTSClient | None = None
        self.current_request_id: str | None = None
        self.current_turn_id: int = -1
        self.sent_ts: datetime | None = None
        self.current_request_finished: bool = False
        self.total_audio_bytes: int = 0
        self._is_stopped: bool = False
        self.recorder_map: dict[str, PCMWriter] = {}

        # Full-duplex state
        self.is_speaking: bool = False
        self.speaking_start_ms: float = -1
        self.request_total_audio_duration: int = 0
        self.last_audio_end_request_id: str = ""
        self.pending_audio_end: bool = False
        self.request_seq_id_map: dict[str, int] = {}
        self.session_id: str = ""
        self.has_valid_text: bool = False

        # Callbacks for client creation (set in on_init)
        self._error_callback = None
        self._fatal_error_callback = None
        self._ttfb_metrics_callback = None

        # Config update state
        self.pending_config_update: CartesiaTTSConfig | None = None
        self.config_update_lock = asyncio.Lock()

    # ── Static helpers (SSML) ────────────────────────────────────────

    @staticmethod
    def _clamp_float(value: Any, lower: float, upper: float) -> float | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric < lower:
            return lower
        if numeric > upper:
            return upper
        return numeric

    @staticmethod
    def _format_ratio(value: float) -> str:
        return f"{value:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def _normalize_time_string(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        try:
            stripped = str(value).strip()
        except Exception:
            return None
        return stripped or None

    def _compose_ssml_text(
        self, text: str, metadata: dict[str, Any] | None
    ) -> str:
        if not self.config:
            return text

        overrides: dict[str, Any] = {}
        if metadata:
            overrides_candidate = metadata.get("ssml") or metadata.get(
                "ssml_tags"
            )
            if isinstance(overrides_candidate, dict):
                overrides = overrides_candidate

        ssml_cfg = self.config.ssml
        enabled = overrides.get("enabled", ssml_cfg.enabled)
        if not enabled:
            return text

        speed_ratio = overrides.get("speed_ratio", ssml_cfg.speed_ratio)
        speed_ratio = self._clamp_float(speed_ratio, 0.6, 1.5)

        volume_ratio = overrides.get("volume_ratio", ssml_cfg.volume_ratio)
        volume_ratio = self._clamp_float(volume_ratio, 0.5, 2.0)

        emotion = overrides.get("emotion", ssml_cfg.emotion)
        if isinstance(emotion, str):
            emotion = emotion.strip() or None
        else:
            emotion = None

        pre_break_time = overrides.get(
            "pre_break_time", ssml_cfg.pre_break_time
        )
        pre_break_time = self._normalize_time_string(pre_break_time)

        post_break_time = overrides.get(
            "post_break_time", ssml_cfg.post_break_time
        )
        post_break_time = self._normalize_time_string(post_break_time)

        spell_words_override = overrides.get("spell_words")
        if spell_words_override is not None:
            if isinstance(spell_words_override, str):
                spell_words = [spell_words_override]
            elif isinstance(spell_words_override, (list, tuple, set)):
                spell_words = list(spell_words_override)
            else:
                spell_words = []
        else:
            spell_words = list(ssml_cfg.spell_words)

        cleaned_spell_words: list[str] = []
        for word in spell_words:
            if isinstance(word, str):
                trimmed = word.strip()
                if trimmed and trimmed not in cleaned_spell_words:
                    cleaned_spell_words.append(trimmed)

        mutated_text = text
        if cleaned_spell_words:
            for word in sorted(cleaned_spell_words, key=len, reverse=True):
                mutated_text = mutated_text.replace(
                    word, f"<spell>{word}</spell>"
                )

        prefix_tags: list[str] = []
        if pre_break_time:
            prefix_tags.append(f'<break time="{pre_break_time}"/>')
        if speed_ratio is not None and abs(speed_ratio - 1.0) > 1e-3:
            prefix_tags.append(
                f'<speed ratio="{self._format_ratio(speed_ratio)}"/>'
            )
        if volume_ratio is not None and abs(volume_ratio - 1.0) > 1e-3:
            prefix_tags.append(
                f'<volume ratio="{self._format_ratio(volume_ratio)}"/>'
            )
        if emotion:
            prefix_tags.append(f'<emotion value="{emotion}"/>')

        prefix = " ".join(prefix_tags)
        if prefix:
            mutated_text = f"{prefix} {mutated_text}".strip()

        if post_break_time:
            mutated_text = f'{mutated_text} <break time="{post_break_time}"/>'

        return mutated_text

    def _apply_ssml_tags_safe(
        self, text: str, metadata: dict[str, Any] | None
    ) -> str:
        try:
            mutated = self._compose_ssml_text(text, metadata)
            if mutated != text:
                self.ten_env.log_debug(
                    f"Applied SSML tags: {mutated[:500]}",
                    category=LOG_CATEGORY_VENDOR,
                )
            return mutated
        except Exception as exc:
            self.ten_env.log_error(
                f"Failed to compose SSML tags: {exc}",
                category=LOG_CATEGORY_VENDOR,
            )
            return text

    # ── Lifecycle ────────────────────────────────────────────────────

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            config_json_str, _ = await self.ten_env.get_property_to_json("")

            if not config_json_str or config_json_str.strip() == "{}":
                raise ValueError(
                    "Configuration is empty. Required parameter 'key' is missing."
                )

            self.config = CartesiaTTSConfig.model_validate_json(config_json_str)
            self.config.update_params()
            ten_env.log_info(
                f"LOG_CATEGORY_KEY_POINT: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if not self.config.api_key:
                raise ValueError("API key is required")

            async def error_callback(request_id: str, error_message: str):
                has_received_text_input_end = False
                if (
                    request_id
                    and request_id in self.request_states
                    and self.request_states[request_id]
                    == RequestState.FINALIZING
                ):
                    has_received_text_input_end = True

                await self.send_tts_error(
                    request_id=request_id,
                    error=ModuleError(
                        message=error_message,
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.NON_FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    ),
                )

                if has_received_text_input_end:
                    ten_env.log_info(
                        f"Error after text_input_end for {request_id}, sending audio_end",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
                    request_event_interval = 0
                    if self.speaking_start_ms > 0:
                        request_event_interval = int(
                            time.time() * 1000 - self.speaking_start_ms
                        )
                    await self.send_tts_audio_end(
                        request_id=request_id,
                        request_event_interval_ms=request_event_interval,
                        request_total_audio_duration_ms=self.request_total_audio_duration,
                        reason=TTSAudioEndReason.ERROR,
                    )
                    await self.finish_request(
                        request_id=request_id,
                        reason=TTSAudioEndReason.ERROR,
                    )
                    self._cleanup_request_state(request_id)

            async def fatal_error_callback(error_message: str):
                await self.send_tts_error(
                    request_id=self.current_request_id or "",
                    error=ModuleError(
                        message=error_message,
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    ),
                )

            async def ttfb_metrics_callback(request_id: str, ttfb_ms: int):
                await self.send_tts_ttfb_metrics(
                    request_id=request_id,
                    ttfb_ms=ttfb_ms,
                    extra_metadata={
                        "model_id": self.config.params.get("model_id", ""),
                        "voice_id": self.config.params.get("voice", {}).get(
                            "id", ""
                        ),
                    },
                )

            # Store callbacks for client recreation on cancel
            self._error_callback = error_callback
            self._fatal_error_callback = fatal_error_callback
            self._ttfb_metrics_callback = ttfb_metrics_callback

            self.client = self._create_client()
            asyncio.create_task(self.client.start())
            asyncio.create_task(
                self._run_with_restart(self._process_audio_data, "audio")
            )
            asyncio.create_task(
                self._run_with_restart(
                    self._process_transcription, "transcription"
                )
            )
            ten_env.log_debug("CartesiaTTS full-duplex client initialized")

        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    message=f"Initialization failed: {e}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        self._is_stopped = True
        ten_env.log_debug("Extension stopping")

        if self.client:
            await self.client.stop()
            self.client = None

        for request_id, recorder in list(self.recorder_map.items()):
            try:
                await recorder.flush()
            except Exception as e:
                ten_env.log_error(f"Error flushing PCMWriter {request_id}: {e}")

        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)

    # ── Task restart wrapper ─────────────────────────────────────────

    async def _run_with_restart(self, coro_func, name: str) -> None:
        """Run an async function with automatic restart on failure."""
        min_delay = 0.1
        max_delay = 3.0
        consecutive_failures = 0

        while not self._is_stopped:
            if self.client is None:
                await asyncio.sleep(min_delay)
                continue
            try:
                await coro_func()
                consecutive_failures = 0
                await asyncio.sleep(min_delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_failures += 1
                delay = min(
                    min_delay * (2 ** (consecutive_failures - 1)), max_delay
                )
                self.ten_env.log_error(
                    f"_{name} failed (failures={consecutive_failures}): {e}, "
                    f"restarting in {delay:.1f}s",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                await asyncio.sleep(delay)

    # ── Audio consumer ─────────────────────────────────────────────

    async def _process_audio_data(self) -> None:
        """Consume audio chunks from client.pcm_queue."""
        while True:
            audio_data, request_id, audio_timestamp = (
                await self.client.get_audio()
            )

            if request_id == "":
                return

            # End-of-audio signal
            if audio_data is None:
                if request_id != self.current_request_id:
                    self.ten_env.log_debug(
                        f"skip audio end: {request_id} != {self.current_request_id}",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
                    continue
                self.ten_env.log_debug(
                    f"Received audio end signal for {request_id}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                # This path can race with request_tts() interrupting the
                # previous request. request_id filtering keeps stale end
                # signals from completing the new request, and
                # last_audio_end_request_id is checked by request_tts() so it
                # does not emit a second audio_end once completion has already
                # been observed.
                if not self.pending_audio_end:
                    self.pending_audio_end = True
                    await self._handle_completed_request(
                        TTSAudioEndReason.REQUEST_END
                    )
                    await self._reset_tts_request_info()
                continue

            # Skip audio for non-current request
            if request_id != self.current_request_id:
                self.ten_env.log_debug(
                    f"skip audio: {request_id} != {self.current_request_id}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                continue

            if not self.is_speaking:
                self.is_speaking = True
                self.speaking_start_ms = time.time() * 1000
                self.request_total_audio_duration = 0
                await self.send_tts_audio_start(
                    request_id=self.current_request_id
                )
            self.metrics_add_recv_audio_chunks(audio_data)

            # Calculate duration
            cur_duration = self._calculate_audio_duration_ms_from_bytes(
                len(audio_data)
            )
            self.request_total_audio_duration += cur_duration
            self.total_audio_bytes += len(audio_data)

            # Dump if enabled
            if (
                self.config
                and self.config.dump
                and self.current_request_id
                and self.current_request_id in self.recorder_map
            ):
                asyncio.create_task(
                    self.recorder_map[self.current_request_id].write(audio_data)
                )

            await self.send_tts_audio_data(audio_data, audio_timestamp)

    # ── Transcription consumer ─────────────────────────────────────

    async def _process_transcription(self) -> None:
        """Consume word timestamps from client.words_queue."""
        last_text_end_ms = 0
        while True:
            words, request_id, cur_text, text_input_end = (
                await self.client.get_words()
            )

            if request_id == "":
                return

            self.ten_env.log_debug(
                f"transcription: {len(words)} words, request_id={request_id}, "
                f"text={cur_text[:80]}, end={text_input_end}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if (
                self.current_request_id
                and request_id != self.current_request_id
            ):
                self.ten_env.log_debug(
                    f"skip transcription: {request_id} != {self.current_request_id}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                continue

            # Seq ID tracking
            if request_id not in self.request_seq_id_map:
                self.request_seq_id_map[request_id] = 0
            current_seq_id = self.request_seq_id_map[request_id]
            self.request_seq_id_map[request_id] += 1

            metadata = (
                self.metadatas.get(request_id, {}).copy()
                if self.metadatas.get(request_id)
                else {}
            )
            metadata["turn_seq_id"] = current_seq_id
            metadata["turn_status"] = 1 if text_input_end else 0

            duration_ms = (
                words[-1].start_ms - words[0].start_ms + words[-1].duration_ms
                if len(words) > 0
                else 0
            )

            start_ms = words[0].start_ms if words else last_text_end_ms

            transcript_result = TTSTextResult(
                request_id=request_id,
                text=cur_text,
                start_ms=start_ms,
                duration_ms=duration_ms,
                words=words,
                text_result_end=text_input_end,
                metadata=metadata,
            )

            if len(words) > 0:
                last_text_end_ms = words[-1].start_ms + words[-1].duration_ms
            self.metrics_add_input_characters(len(cur_text))
            await self.send_tts_text_result(transcript_result)

    def _cleanup_request_state(self, request_id: str | None) -> None:
        """Release per-request bookkeeping once the request is finished."""
        if not request_id:
            return
        self.request_seq_id_map.pop(request_id, None)

    # ── Request handling ──────────────────────────────────────────────

    async def _handle_completed_request(
        self, reason: TTSAudioEndReason
    ) -> None:
        """Send audio_end and finish_request for the current request."""
        if (
            self.config
            and self.config.dump
            and self.current_request_id
            and self.current_request_id in self.recorder_map
        ):
            try:
                await self.recorder_map[self.current_request_id].flush()
            except Exception as e:
                self.ten_env.log_error(f"Error flushing PCMWriter: {e}")

        self.last_audio_end_request_id = self.current_request_id or ""

        request_event_interval = 0
        if self.speaking_start_ms > 0:
            request_event_interval = int(
                time.time() * 1000 - self.speaking_start_ms
            )

        await self.send_tts_audio_end(
            request_id=self.current_request_id or "",
            request_event_interval_ms=request_event_interval,
            request_total_audio_duration_ms=self.request_total_audio_duration,
            reason=reason,
        )

        await self.send_usage_metrics(self.current_request_id or "")

        await self.finish_request(
            request_id=self.current_request_id or "",
            reason=reason,
        )
        self._cleanup_request_state(self.current_request_id)

    async def _reset_tts_request_info(self) -> None:
        """Reset per-request state."""
        self.is_speaking = False
        self.speaking_start_ms = -1
        self.request_total_audio_duration = 0
        self.pending_audio_end = False
        self.has_valid_text = False

    def _create_client(self) -> CartesiaTTSClient:
        """Create a new CartesiaTTSClient reusing stored config and callbacks."""
        return CartesiaTTSClient(
            config=self.config,
            ten_env=self.ten_env,
            error_callback=self._error_callback,
            fatal_error_callback=self._fatal_error_callback,
            ttfb_metrics_callback=self._ttfb_metrics_callback,
            latency_metrics_callback=self.metrics_connect_delay,
        )

    async def cancel_tts(self) -> None:
        self.current_request_finished = True
        if self.current_request_id:
            self.ten_env.log_debug(
                f"Cancelling request {self.current_request_id}, "
                f"destroying client and recreating"
            )

            # 1. Stop the old client (closes ws, cancels tasks, clears queues)
            old_client = self.client
            self.client = None  # consumer tasks will see None and wait

            if old_client:
                await old_client.stop()

            # 2. Send audio_end with INTERRUPTED reason
            request_event_interval = 0
            if self.speaking_start_ms > 0:
                request_event_interval = int(
                    time.time() * 1000 - self.speaking_start_ms
                )
            await self.send_tts_audio_end(
                request_id=self.current_request_id,
                request_event_interval_ms=request_event_interval,
                request_total_audio_duration_ms=self.request_total_audio_duration,
                reason=TTSAudioEndReason.INTERRUPTED,
            )

            # Mark audio_end as sent so request_tts won't send a redundant one
            self.last_audio_end_request_id = self.current_request_id

            if self.current_request_id in self.recorder_map:
                await self.recorder_map[self.current_request_id].flush()

            await self.finish_request(
                request_id=self.current_request_id,
                reason=TTSAudioEndReason.INTERRUPTED,
            )
            self._cleanup_request_state(self.current_request_id)
            await self._reset_tts_request_info()

            # 3. Create a fresh client and start it
            self.client = self._create_client()
            asyncio.create_task(self.client.start())
            self.ten_env.log_debug(
                "New CartesiaTTS client created after cancel"
            )

    def vendor(self) -> str:
        return "cartesia"

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 16000

    def _calculate_audio_duration_ms_from_bytes(self, byte_length: int) -> int:
        bytes_per_sample = 2  # 16-bit PCM
        channels = 1
        duration_sec = byte_length / (
            self.synthesize_audio_sample_rate() * bytes_per_sample * channels
        )
        return int(duration_sec * 1000)

    # ── update_configs ───────────────────────────────────────────────

    def _requires_reconnection(
        self,
        old_config: CartesiaTTSConfig,
        new_config: CartesiaTTSConfig,
    ) -> bool:
        """Determine if a config change requires client reconnection."""
        for field in ("api_key", "base_url", "sample_rate"):
            if getattr(old_config, field) != getattr(new_config, field):
                self.ten_env.log_info(
                    f"Config change requires reconnection: {field} changed",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                return True

        for field in (
            "model_id",
            "voice",
            "language",
            "output_format",
            "generation_config",
        ):
            if old_config.params.get(field) != new_config.params.get(field):
                self.ten_env.log_info(
                    f"Config change requires reconnection: params.{field} changed",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                return True

        return False

    async def update_configs(self, configs: dict) -> None:
        async with self.config_update_lock:
            try:
                safe_configs = copy.deepcopy(configs)
                params = safe_configs.get("params")
                if isinstance(params, dict) and "api_key" in params:
                    params["api_key"] = "***"
                self.ten_env.log_info(
                    f"tts_update_configs: {safe_configs}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                new_config = self.config.merge_updates(configs)

                self.ten_env.log_info(
                    f"Config update requested: {list(configs.keys())}",
                    category=LOG_CATEGORY_KEY_POINT,
                )

                if self.current_request_id:
                    self.pending_config_update = new_config
                    self.ten_env.log_info(
                        f"Buffering config update during request {self.current_request_id}",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
                    return

                await self._apply_config_update(new_config)
            except Exception as e:
                self.ten_env.log_error(f"Config update failed: {e}")
                raise

    async def _apply_config_update(self, new_config: CartesiaTTSConfig) -> None:
        old_config = self.config
        requires_reconnect = self._requires_reconnection(old_config, new_config)

        if requires_reconnect:
            self.ten_env.log_info(
                "Config update requires reconnection, recreating client",
                category=LOG_CATEGORY_KEY_POINT,
            )
            try:
                self.config = new_config
                if self.client:
                    await self.client.stop()
                self.client = self._create_client()
                asyncio.create_task(self.client.start())
                self.ten_env.log_info(
                    "Successfully reconnected with new config",
                    category=LOG_CATEGORY_KEY_POINT,
                )
            except Exception as e:
                self.ten_env.log_error(f"Reconnection failed: {e}")
                raise
        else:
            self.ten_env.log_info(
                "Config update does not require reconnection",
                category=LOG_CATEGORY_KEY_POINT,
            )
            self.config = new_config
            if self.client:
                self.client.config = new_config

        self.ten_env.log_info(
            f"Config update applied: {new_config.to_str(sensitive_handling=True)}",
            category=LOG_CATEGORY_KEY_POINT,
        )

    # ── request_tts (simplified: just put to queue) ──────────────────

    async def request_tts(self, t: TTSTextInput) -> None:
        try:
            self.ten_env.log_info(
                f"request_tts: text={t.text}, end={t.text_input_end}, "
                f"request_id={t.request_id}",
            )

            if self.client is None:
                self.ten_env.log_warn(
                    f"Client unavailable while handling request {t.request_id}, waiting for recreation",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                if not await self._wait_for_client_available():
                    self.ten_env.log_warn(
                        f"Client still unavailable, dropping request {t.request_id}",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
                    return

            if t.request_id != self.current_request_id:
                self.ten_env.log_debug(f"New TTS request: {t.request_id}")

                # Apply buffered config update on new request
                async with self.config_update_lock:
                    pending_config_update = self.pending_config_update
                if pending_config_update:
                    self.ten_env.log_info(
                        f"Applying buffered config update on new request {t.request_id}",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
                    await self._apply_config_update(pending_config_update)
                    async with self.config_update_lock:
                        if self.pending_config_update is pending_config_update:
                            self.pending_config_update = None

                # If previous request didn't get audio_end, handle it
                if (
                    self.current_request_id
                    and self.last_audio_end_request_id
                    != self.current_request_id
                ):
                    self.ten_env.log_debug(
                        f"Previous request {self.current_request_id} not ended, "
                        f"sending INTERRUPTED"
                    )
                    await self._handle_completed_request(
                        TTSAudioEndReason.INTERRUPTED
                    )

                await self._reset_tts_request_info()
                self.current_request_id = t.request_id
                self.current_request_finished = False
                self.total_audio_bytes = 0
                self.sent_ts = None

                await self.client.set_current_request_id(t.request_id)

                if t.metadata is not None:
                    self.session_id = t.metadata.get("session_id", "")
                    self.current_turn_id = t.metadata.get("turn_id", -1)

                # PCMWriter management
                if self.config and self.config.dump:
                    old_rids = [
                        rid for rid in self.recorder_map if rid != t.request_id
                    ]
                    for old_rid in old_rids:
                        try:
                            await self.recorder_map[old_rid].flush()
                            del self.recorder_map[old_rid]
                        except Exception as e:
                            self.ten_env.log_error(
                                f"Error cleaning PCMWriter {old_rid}: {e}"
                            )

                    if t.request_id not in self.recorder_map:
                        dump_file_path = os.path.join(
                            self.config.dump_path,
                            f"cartesia_dump_{t.request_id}.pcm",
                        )
                        self.recorder_map[t.request_id] = PCMWriter(
                            dump_file_path
                        )

            elif self.current_request_finished:
                self.ten_env.log_error(
                    f"Message for finished request '{t.request_id}'"
                )
                return

            if t.text_input_end:
                self.ten_env.log_debug(
                    f"KEYPOINT finish session for request: {t.request_id}"
                )
                self.current_request_finished = True

            # Track whether any valid (non-empty) text has been seen
            if t.text.strip():
                self.has_valid_text = True

            # All texts empty and end of input — complete immediately without
            # sending to server (Cartesia rejects empty text with 400)
            if t.text_input_end and not self.has_valid_text:
                self.ten_env.log_info(
                    f"All texts are empty for request_id {t.request_id}, "
                    f"sending tts_audio_end immediately",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                await self._handle_completed_request(
                    TTSAudioEndReason.REQUEST_END
                )
                await self._reset_tts_request_info()
                return

            prepared_text = self._apply_ssml_tags_safe(t.text, t.metadata)

            if self._is_stopped:
                return

            if t.text.strip() != "":
                self.ten_env.log_debug(
                    f"send_text_to_tts_server: {prepared_text} "
                    f"request_id={t.request_id}",
                    category=LOG_CATEGORY_VENDOR,
                )
                self.metrics_add_output_characters(len(prepared_text))

                tts_input = TTSTextInput(
                    request_id=t.request_id,
                    text=prepared_text,
                    text_input_end=t.text_input_end,
                    metadata=t.metadata,
                )
                await self.client.text_to_speech(tts_input)

            elif t.text_input_end:
                # Empty text but end of input — send end signal
                tts_input = TTSTextInput(
                    request_id=t.request_id,
                    text="",
                    text_input_end=True,
                    metadata=t.metadata,
                )
                await self.client.text_to_speech(tts_input)

        except CartesiaTTSConnectionException as e:
            self.ten_env.log_error(f"Connection error: {e.body}")
            await self.send_tts_error(
                request_id=self.current_request_id,
                error=ModuleError(
                    message=e.body,
                    module=ModuleType.TTS,
                    code=(
                        ModuleErrorCode.FATAL_ERROR
                        if e.status_code == 401
                        else ModuleErrorCode.NON_FATAL_ERROR
                    ),
                    vendor_info=ModuleErrorVendorInfo(
                        vendor=self.vendor(),
                        code=str(e.status_code),
                        message=e.body,
                    ),
                ),
            )
            await self.finish_request(
                request_id=self.current_request_id or "",
                reason=TTSAudioEndReason.ERROR,
                error=ModuleError(
                    message=e.body,
                    module=ModuleType.TTS,
                    code=(
                        ModuleErrorCode.FATAL_ERROR
                        if e.status_code == 401
                        else ModuleErrorCode.NON_FATAL_ERROR
                    ),
                    vendor_info=ModuleErrorVendorInfo(
                        vendor=self.vendor(),
                        code=str(e.status_code),
                        message=e.body,
                    ),
                ),
            )
            self._cleanup_request_state(self.current_request_id)

        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}"
            )
            await self.send_tts_error(
                request_id=self.current_request_id,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )
            await self.finish_request(
                request_id=self.current_request_id or "",
                reason=TTSAudioEndReason.ERROR,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )
            self._cleanup_request_state(self.current_request_id)

    # ── Helper methods ─────────────────────────────────────────────

    async def _wait_for_client_available(self, timeout_s: float = 5.0) -> bool:
        """Wait briefly for client recreation so transient teardown does not drop text."""
        deadline = time.monotonic() + timeout_s
        while not self._is_stopped:
            if self.client is not None:
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.01)
        return False

    async def send_fatal_tts_error(self, error_message: str) -> None:
        await self.send_tts_error(
            request_id=self.current_request_id or "",
            error=ModuleError(
                message=error_message,
                module=ModuleType.TTS,
                code=ModuleErrorCode.FATAL_ERROR,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            ),
        )

    async def send_non_fatal_tts_error(self, error_message: str) -> None:
        await self.send_tts_error(
            request_id=self.current_request_id or "",
            error=ModuleError(
                message=error_message,
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            ),
        )

    def _current_request_interval_ms(self) -> int:
        if not self.sent_ts:
            return 0
        return int((datetime.now() - self.sent_ts).total_seconds() * 1000)

    def _calculate_audio_duration_ms(self) -> int:
        if self.config is None:
            return 0
        bytes_per_sample = 2
        channels = 1
        duration_sec = self.total_audio_bytes / (
            self.synthesize_audio_sample_rate() * bytes_per_sample * channels
        )
        return int(duration_sec * 1000)
