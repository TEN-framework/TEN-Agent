#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
import time
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_KEY_POINT,
)
from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.struct import ASRResults
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_runtime import AsyncTenEnv, AudioFrame, Data
from typing_extensions import override

from .config import (
    FinalizeMode,
    FinalizeReconnectMode,
    HoldingMode,
    SonioxASRConfig,
)
from .const import DUMP_FILE_NAME, MODULE_NAME_ASR, map_language_code
from .reconnect_manager import ReconnectManager
from .dumper import Dumper
from .text_utils import SentenceBoundaryDetector
from .websocket import (
    SonioxFinToken,
    SonioxEndToken,
    SonioxTranscriptToken,
    SonioxTranslationToken,
    SonioxToken,
    SonioxWebsocketClient,
    SonioxWebsocketEvents,
)


class ASRTranslationResult(BaseModel):
    """Translation result model specific to Soniox extension."""

    id: str
    text: str
    source_text: str  # Original text that was translated
    final: bool
    start_ms: int
    duration_ms: int
    language: str  # Target language of translation
    source_language: str  # Source language that was translated from
    metadata: dict[str, Any] = Field(default_factory=dict)


class SonioxASRErrorFilter:
    """Filter to downgrade specific 400 errors to non-fatal for ASR error reporting.

    See https://soniox.com/docs/stt/api-reference/websocket-api#error-response
    """

    NON_FATAL_400_PHRASES = ("No audio received", "Audio is too long")

    @classmethod
    def get_module_error_code(cls, error_code: int, error_message: str) -> int:
        if error_code == 400 and any(
            phrase in error_message for phrase in cls.NON_FATAL_400_PHRASES
        ):
            return ModuleErrorCode.NON_FATAL_ERROR.value
        if error_code in (400, 401, 402):
            return ModuleErrorCode.FATAL_ERROR.value
        return ModuleErrorCode.NON_FATAL_ERROR.value


class SonioxASRExtension(AsyncASRBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.connected: bool = False
        self.websocket: Optional[SonioxWebsocketClient] = None
        self.ws_task: asyncio.Task[None] | None = None
        self.config: Optional[SonioxASRConfig] = None
        self.audio_dumper: Optional[Dumper] = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        # Track last transcript for standalone translations
        self.last_transcript_text: str = ""
        self.last_transcript_start_ms: int = 0
        self.last_transcript_duration_ms: int = 0
        self.last_transcript_is_final: bool = False
        self.last_transcript_id: str = ""

        self.holding = False
        self.holding_final_tokens: list[SonioxTranscriptToken] = []
        self.holding_translation_tokens: list[SonioxTranslationToken] = []

        self._pending_close_finalize = False
        self._needs_reconnect = False
        self._suppress_close_status = False
        self._last_final_time_ms: int = 0
        self._last_final_wall_ms: int = 0
        self._deferred_vendor_final_tokens: list[SonioxTranscriptToken] = []
        self._sentence_boundary_detector = SentenceBoundaryDetector()
        self.reconnect_manager: ReconnectManager | None = None

    def _clear_deferred_vendor_final_tokens(self) -> None:
        self._deferred_vendor_final_tokens = []

    async def _flush_deferred_vendor_final_tokens(self) -> None:
        """Force-emit deferred vendor-final tokens as final on session boundary.

        Used when the session ends (<fin>) before a complete sentence was
        detected. Translation is not passed here: sentence_terminator mode does
        not use translation in current deployments.
        """
        if not self._deferred_vendor_final_tokens:
            return
        if (
            self.config is None
            or self.config.holding_mode != HoldingMode.SENTENCE_TERMINATOR
        ):
            self._clear_deferred_vendor_final_tokens()
            return

        tokens = self._deferred_vendor_final_tokens
        self._clear_deferred_vendor_final_tokens()
        asr_results = self._create_asr_results(tokens, True)
        await self._publish_asr_results(asr_results, [])

    def _adjust_tokens_for_sentence_end_finality(
        self,
        transcript_tokens: List[SonioxTranscriptToken],
        is_final: bool,
    ) -> tuple[List[SonioxTranscriptToken], bool]:
        """Emit vendor-final tokens through the first complete sentence; defer the rest."""
        if (
            self.config is None
            or self.config.holding_mode != HoldingMode.SENTENCE_TERMINATOR
        ):
            if not is_final and self._deferred_vendor_final_tokens:
                return (
                    [*self._deferred_vendor_final_tokens, *transcript_tokens],
                    False,
                )
            return transcript_tokens, is_final

        if not is_final:
            if self._deferred_vendor_final_tokens:
                return (
                    [*self._deferred_vendor_final_tokens, *transcript_tokens],
                    False,
                )
            return transcript_tokens, False

        merged_tokens = [
            *self._deferred_vendor_final_tokens,
            *transcript_tokens,
        ]
        if not merged_tokens:
            return transcript_tokens, False

        language = map_language_code(merged_tokens[0].language or "en")
        if not self._sentence_boundary_detector.supports_language(language):
            self._clear_deferred_vendor_final_tokens()
            return transcript_tokens, is_final

        emit_len, defer_start = (
            self._sentence_boundary_detector.split_at_last_complete_sentence(
                [token.text for token in merged_tokens],
                language,
            )
        )
        if emit_len <= 0:
            self._deferred_vendor_final_tokens = merged_tokens
            return merged_tokens, False

        emit_tokens = merged_tokens[:emit_len]
        self._deferred_vendor_final_tokens = merged_tokens[defer_start:]
        return emit_tokens, True

    def _effective_holding_mode(self) -> HoldingMode:
        if self.config is None:
            return HoldingMode.FALSE
        configured = self.config.holding_mode
        if configured == HoldingMode.ENDPOINTING_ONLY and not (
            self.config.params.get("enable_endpoint_detection", False)
        ):
            return HoldingMode.FALSE
        return configured

    @override
    def vendor(self) -> str:
        return "soniox"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        params = self.config.params or {}
        metadata: dict[str, Any] = {}
        api_key = params.get("api_key")
        if api_key:
            metadata["api_key"] = api_key
        if self.config.url:
            metadata["url"] = self.config.url
        model = params.get("model")
        if model:
            metadata["model"] = model
        return metadata

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        self.reconnect_manager = ReconnectManager(logger=ten_env)

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            self.config = SonioxASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if self.config.finalize_mode == FinalizeMode.IGNORE:
                if not (
                    self.config.params.get("enable_endpoint_detection", False)
                ):
                    ten_env.log_error(
                        "endpoint detection must be enabled when finalize_mode is IGNORE",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
            if self.config.dump:
                self.audio_dumper = Dumper(
                    self.config.dump_path, DUMP_FILE_NAME
                )
            effective = self._effective_holding_mode()
            ten_env.log_info(
                f"effective holding_mode: {effective.value}",
                category=LOG_CATEGORY_KEY_POINT,
            )
        except Exception as e:
            ten_env.log_error(f"invalid property: {e}")
            self.config = SonioxASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        if self._needs_reconnect:
            self._needs_reconnect = False
            self.uuid = self._get_uuid()
            self._clear_deferred_vendor_final_tokens()
            await self.start_connection()

        await super().on_audio_frame(ten_env, audio_frame)

    async def _start_websocket(self) -> None:
        """Start websocket connection only (without audio dumper)."""
        assert self.config is not None
        start_request = json.dumps(self.config.params)
        ws = SonioxWebsocketClient(
            self.config.url,
            start_request,
            enable_keepalive=self.config.enable_keepalive,
        )
        ws.on(SonioxWebsocketEvents.OPEN, self._handle_open)
        ws.on(SonioxWebsocketEvents.CLOSE, self._handle_close)
        ws.on(SonioxWebsocketEvents.EXCEPTION, self._handle_exception)
        ws.on(SonioxWebsocketEvents.ERROR, self._handle_error)
        ws.on(SonioxWebsocketEvents.FINISHED, self._handle_finished)
        ws.on(SonioxWebsocketEvents.TRANSCRIPT, self._handle_transcript)
        self.websocket = ws
        self.ws_task = asyncio.create_task(ws.connect())

    async def _stop_websocket(self, *, suppress_status: bool = False) -> None:
        """Stop websocket connection only (without audio dumper).

        When suppress_status is True, the resulting CLOSE callback skips
        connection_status reporting and reconnect handling. Used when
        start_connection replaces an existing client after disconnect was
        already reported.
        """
        self.connected = False
        ws = self.websocket
        task = self.ws_task
        self.websocket = None
        self.ws_task = None
        if ws:
            if suppress_status:
                self._suppress_close_status = True
            await ws.stop()
        if task and not task.done():
            try:
                await task
            except Exception:
                pass

    @override
    async def start_connection(self) -> None:
        assert self.config is not None
        self.ten_env.log_info("start_connection")

        if not self.config.params.get("api_key"):
            self.ten_env.log_error("Missing required api_key")
            error = ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.FATAL_ERROR.value,
                message="Missing required api_key",
            )
            await self.send_asr_error(error)
            await self.on_disconnected(code=error.code, message=error.message)
            return

        try:
            if self.websocket is not None:
                await self._stop_websocket(suppress_status=True)
            await self._start_websocket()
        except Exception as e:
            self.ten_env.log_error(f"start_connection failed: {e}")
            error = ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=str(e),
            )
            await self.send_asr_error(error)
            await self.on_disconnected(code=error.code, message=error.message)
            return

        try:
            if self.audio_dumper:
                await self.audio_dumper.start()
        except Exception as e:
            self.ten_env.log_error(f"Failed to start audio dumper: {e}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def stop_connection(self) -> None:
        self.ten_env.log_info("stop_connection")
        if self.audio_dumper:
            await self.audio_dumper.stop()
        await self._stop_websocket()

    @override
    def is_connected(self) -> bool:
        return self.connected and self.websocket is not None

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    def input_audio_sample_rate(self) -> int:
        return 16000

    @override
    def input_audio_channels(self) -> int:
        return 1

    @override
    def input_audio_sample_width(self) -> int:
        return 2

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: Optional[str]
    ) -> bool:
        assert self.config is not None
        assert self.websocket is not None

        buf = frame.get_buf()
        if self.audio_dumper:
            try:
                await self.audio_dumper.push_bytes(bytes(buf))
            except Exception as e:
                self.ten_env.log_warn(
                    f"Failed to push bytes into audio dumper, error: {str(e)}"
                )
        self.audio_timeline.add_user_audio(
            int(len(buf) / (self.config.sample_rate / 1000 * 2))
        )

        await self.websocket.send_audio(bytes(buf))

        return True

    @override
    async def finalize(self, session_id: Optional[str]) -> None:
        # NOTE: This is an empty method, actual finalize logic is handled in on_data.
        pass

    @override
    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        await super().on_data(ten_env, data)
        if data.get_name() == "asr_finalize":
            self.last_finalize_timestamp = int(time.time() * 1000)
            if self.config.finalize_mode == FinalizeMode.MUTE_PKG:
                await self._real_finalize_by_mute_pkg()
                return
            if self.config.finalize_mode == FinalizeMode.CLOSE:
                await self._real_finalize_by_close()
                return
            if self._effective_holding_mode() == HoldingMode.FINALIZE:
                self.holding = True
            if self.config.finalize_mode == FinalizeMode.IGNORE:
                return
            # NOTE: We need this extra parameter for manual finalization in order to achieve lower finalization latency.
            # Refer to: https://soniox.com/docs/stt/rt/manual-finalization#trailing-silence
            #
            # This property is not in the asr api, but will be included in the future.
            # The upstream can set this property if it knows the trailing silence duration.
            silence_duration_ms, err = data.get_property_int(
                "silence_duration_ms"
            )
            if err:
                await self._real_finalize()
            else:
                await self._real_finalize(silence_duration_ms)

    async def _send_silence_packets(self, duration_ms: int) -> None:
        """Send silence packets and update audio timeline."""
        empty_audio_bytes_len = int(
            duration_ms * self.config.sample_rate / 1000 * 2
        )
        frame = bytearray(empty_audio_bytes_len)

        if self.audio_dumper:
            await self.audio_dumper.push_bytes(bytes(frame))

        if self.websocket:
            await self.websocket.send_audio(bytes(frame))

        self.audio_timeline.add_silence_audio(duration_ms)

    async def _real_finalize(
        self, silence_duration_ms: int | None = None
    ) -> None:
        # Send silence packets if enabled for DEFAULT mode
        if self.config.default_finalize_send_silence:
            sent_silence_duration_ms = (
                self.config.default_finalize_silence_duration_ms
            )
            await self._send_silence_packets(sent_silence_duration_ms)
            if silence_duration_ms is None:
                silence_duration_ms = 0
            silence_duration_ms += sent_silence_duration_ms

        # Create rotation callback if dump rotation is enabled
        callback = None
        if self.config.dump_rotate_on_finalize and self.audio_dumper:

            async def rotate_callback(audio_bytes_sent: int = 0):
                audio_timestamp_ms = int(
                    audio_bytes_sent
                    / self.input_audio_sample_width()
                    / self.input_audio_channels()
                    / self.input_audio_sample_rate()
                    * 1000
                )
                self.ten_env.log_info(
                    f"Sending finalize to Soniox server at timestamp: {audio_timestamp_ms}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                if self.audio_dumper:
                    try:
                        await self.audio_dumper.rotate()
                    except Exception as e:
                        self.ten_env.log_warn(
                            f"Failed to rotate audio dumper, error: {str(e)}"
                        )

            callback = rotate_callback

        self.ten_env.log_info(
            f"vendor_cmd: finalize, silence_duration_ms: {silence_duration_ms}",
            category=LOG_CATEGORY_VENDOR,
        )
        if self.websocket:
            await self.websocket.finalize(
                silence_duration_ms, before_send_callback=callback
            )

    async def _real_finalize_by_mute_pkg(self) -> None:
        self.ten_env.log_info(
            "vendor_cmd: finalize, by mute pkg",
            category=LOG_CATEGORY_VENDOR,
        )

        await self._send_silence_packets(self.config.mute_pkg_duration_ms)

        # No need to do stats.
        self.last_finalize_timestamp = 0
        await self.send_asr_finalize_end()

        self.ten_env.log_info("finalize by mute pkg done")

    async def _real_finalize_by_close(self) -> None:
        self.ten_env.log_info(
            "vendor_cmd: finalize, by close",
            category=LOG_CATEGORY_VENDOR,
        )
        if self.websocket:
            self._pending_close_finalize = True
            await self._stop_websocket()
        else:
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def _flush_endpointing_only_holding(
        self,
        reason: str,
        end_time_stream_ms: int | None = None,
    ) -> None:
        if self._effective_holding_mode() != HoldingMode.ENDPOINTING_ONLY:
            return
        if not self.holding_final_tokens:
            return
        ttlw_ms = 0
        wall_ttlw_ms = 0
        if end_time_stream_ms is not None:
            ttlw_ms = end_time_stream_ms - self._last_final_time_ms
        wall_ttlw_ms = int(time.time() * 1000) - self._last_final_wall_ms
        self.ten_env.log_info(
            f"holding_mode endpointing_only flush: reason={reason}, ttlw_ms={ttlw_ms}, wall_ttlw_ms={wall_ttlw_ms}",
            category=LOG_CATEGORY_KEY_POINT,
        )
        await self._send_transcript_and_translation(
            self.holding_final_tokens,
            self.holding_translation_tokens,
            True,
        )
        self.holding_final_tokens = []
        self.holding_translation_tokens = []

    async def _finalize_end(
        self, flush_reason: str = "session finalize"
    ) -> None:
        self.ten_env.log_info("finalize end")
        # Emit any transcript held back for sentence-end detection.
        await self._flush_deferred_vendor_final_tokens()
        if self._effective_holding_mode() == HoldingMode.ENDPOINTING_ONLY:
            # Only flush on disconnect; <end> is handled in _handle_transcript.
            # Do not flush on <fin> (session finalize) so segment boundary and TTLW
            # stay aligned with endpoint time.
            if flush_reason == "disconnect":
                await self._flush_endpointing_only_holding(flush_reason, None)
        if (
            self.holding
            and self._effective_holding_mode() == HoldingMode.FINALIZE
        ):
            self.holding = False
            if self.holding_final_tokens:
                await self._send_transcript_and_translation(
                    self.holding_final_tokens,
                    self.holding_translation_tokens,
                    True,
                )
                self.holding_final_tokens = []
                self.holding_translation_tokens = []

        if self.config.finalize_mode == FinalizeMode.IGNORE:
            # No need to check if there is corresponding asr_finalize in this mode.
            await self.send_asr_finalize_end()
        elif self.last_finalize_timestamp != 0:
            timestamp = int(time.time() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_info(
                f"finalize end at {timestamp}, latency: {latency}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def _handle_reconnect(self) -> None:
        """Schedule one reconnect attempt; further retries come from _handle_close."""
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return

        await self.reconnect_manager.handle_reconnect(
            connection_func=self.start_connection,
            error_handler=self.send_asr_error,
        )

    # WebSocket event handlers
    async def _handle_open(self, connection_start_timestamp: int):
        connection_delay_ms = (
            int(time.time() * 1000) - connection_start_timestamp
        )

        self.ten_env.log_info(
            f"vendor_status_changed: connection opened, connection_delay_ms: {connection_delay_ms}",
            category=LOG_CATEGORY_VENDOR,
        )

        await self.send_connect_delay_metrics(connection_delay_ms)

        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()

        self.connected = True
        self._clear_deferred_vendor_final_tokens()
        if self.reconnect_manager:
            self.reconnect_manager.mark_connection_successful()
        await self.on_connected()

    async def _handle_close(
        self, vendor_code: int = 0, vendor_message: str = "closed"
    ):
        if self._suppress_close_status:
            self._suppress_close_status = False
            self.connected = False
            return

        is_normal_close = vendor_code in (0, 1000)
        self.ten_env.log_info(
            f"vendor connection closed: code={vendor_code}, message={vendor_message}",
            category=LOG_CATEGORY_VENDOR,
        )
        self.connected = False

        # Normal close is a disconnect only — do not attach vendor error info
        # or inflate ASR error stats.
        vendor_info = None
        if not is_normal_close:
            vendor_info = ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(vendor_code),
                message=vendor_message,
            )

        await self.on_disconnected(
            code=0, message="closed", vendor_info=vendor_info
        )

        if self._pending_close_finalize:
            self._pending_close_finalize = False
            await self._finalize_end("disconnect")

            if (
                self.config.finalize_reconnect_mode
                == FinalizeReconnectMode.IMMEDIATE
            ):
                await self.start_connection()
            elif self.buffered_frames.qsize() > 0:
                await self.start_connection()
            else:
                self._needs_reconnect = True
            return

        # Intentional close-finalize reconnects call start_connection() directly.
        if not self.stopped:
            self.ten_env.log_warn(
                "Soniox connection closed unexpectedly. Reconnecting..."
            )
            await self._handle_reconnect()

    @staticmethod
    def _is_normal_websocket_close(exc: Exception) -> bool:
        """True only for intentional normal closure (1000), not going-away (1001)."""
        return SonioxWebsocketClient.is_normal_close(exc)

    async def _handle_exception(self, e: Exception):
        # Normal close (1000) must not enter ASR error stats.
        # 1001 going-away is a transient service failure → NON_FATAL_ERROR.
        if self._is_normal_websocket_close(e):
            self.ten_env.log_info(
                f"soniox connection closed normally: {type(e).__name__} {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        self.ten_env.log_error(
            f"soniox connection exception: {type(e)} {str(e)}"
        )
        await self._handle_error(-1, str(e))

    async def _handle_error(
        self,
        error_code: int,
        error_message: str,
        request_id: str | None = None,
        error_type: str | None = None,
    ):
        # Vendor ERROR events are reported here; on_disconnected is emitted from
        # _handle_close when the websocket actually closes.
        request_id_str = str(request_id) if request_id else None
        error_type_str = str(error_type) if error_type else None

        log_parts = [
            f"code: {error_code}",
            f"message: {error_message}",
        ]
        if error_type_str:
            log_parts.append(f"error_type: {error_type_str}")
        if request_id_str:
            log_parts.append(f"request_id: {request_id_str}")

        self.ten_env.log_error(
            f"vendor_error: {', '.join(log_parts)}",
            category=LOG_CATEGORY_VENDOR,
        )
        error_msg = f"soniox error {error_code}: {error_message}"
        if request_id_str:
            error_msg = f"{error_msg} (request_id={request_id_str})"

        module_error_code = SonioxASRErrorFilter.get_module_error_code(
            error_code, error_message
        )
        error_metadata: dict[str, Any] = {}
        if request_id_str:
            error_metadata["request_id"] = request_id_str
        if error_type_str:
            error_metadata["error_type"] = error_type_str

        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=module_error_code,
                message=error_msg,
                metadata=error_metadata,
            ),
            ModuleErrorVendorInfo(
                vendor="soniox",
                code=str(error_code),
                message=error_message,
            ),
        )

    async def _handle_finished(
        self, final_audio_proc_ms: int, total_audio_proc_ms: int
    ):
        self.ten_env.log_info(
            f"soniox finished: final_audio_proc_ms={final_audio_proc_ms}, total_audio_proc_ms={total_audio_proc_ms}"
        )

    async def _handle_transcript(
        self,
        tokens: List[SonioxToken],
        final_audio_proc_ms: int,
        total_audio_proc_ms: int,
    ):
        """
        Tokens can be TranscriptToken, TranslationToken, FinToken, EndToken.
        Tokens have is_final and language.
        We need to group tokens properly in order to send `asr_result` and `asr_translation_result`.
        We can assume some patterns:
        - Final transcript tokens come before non-final tokens.
        - When there are translation tokens, they always come after the corresponding transcript tokens.
        """
        self.ten_env.log_debug(
            f"vendor_result: transcript: {tokens}, final_audio_proc_ms: {final_audio_proc_ms}, total_audio_proc_ms: {total_audio_proc_ms}",
            category=LOG_CATEGORY_VENDOR,
        )

        try:
            transcript_tokens = []
            translation_tokens = []
            send_finalize_end = False
            has_only_translations = True
            had_end_token = False
            endpoint_time_ms = 0

            # First pass: Separate tokens by type
            for token in tokens:
                match token:
                    case SonioxTranscriptToken():
                        has_only_translations = False
                        if translation_tokens and transcript_tokens:
                            await self._process_transcript_and_translation(
                                transcript_tokens, translation_tokens
                            )
                            transcript_tokens = []
                            translation_tokens = []
                        transcript_tokens.append(token)
                    case SonioxTranslationToken():
                        translation_tokens.append(token)
                    case SonioxFinToken():
                        send_finalize_end = True
                    case SonioxEndToken():
                        send_finalize_end = True
                        had_end_token = True
                        endpoint_time_ms = total_audio_proc_ms

            # Handle standalone translations (no transcript tokens in this call)
            if (
                has_only_translations
                and translation_tokens
                and self.last_transcript_text
            ):
                # Use the saved id from the last transcript
                await self._send_translation_results(
                    translation_tokens,
                    self.last_transcript_is_final,
                    self.last_transcript_text,
                    self.last_transcript_start_ms,
                    self.last_transcript_duration_ms,
                    result_id=self.last_transcript_id,
                )
            # Process transcript and translation pairs
            elif transcript_tokens:
                await self._process_transcript_and_translation(
                    transcript_tokens, translation_tokens
                )

            # Handle finalization
            if send_finalize_end:
                if had_end_token:
                    await self._flush_endpointing_only_holding(
                        "endpoint", endpoint_time_ms
                    )
                await self._finalize_end()

        except Exception as e:
            self.ten_env.log_error(f"Error handling transcript: {e}")

    async def _process_transcript_and_translation(
        self,
        transcript_tokens: List[SonioxTranscriptToken],
        translation_tokens: List[SonioxTranslationToken],
    ) -> None:
        """Process transcript tokens and their corresponding translations."""
        if not transcript_tokens:
            return

        # Group transcript tokens by is_final
        final_transcripts = [t for t in transcript_tokens if t.is_final]
        non_final_transcripts = [t for t in transcript_tokens if not t.is_final]

        effective = self._effective_holding_mode()
        use_holding = (effective == HoldingMode.FINALIZE and self.holding) or (
            effective == HoldingMode.ENDPOINTING_ONLY
        )

        if not use_holding and final_transcripts and non_final_transcripts:
            await self._send_mixed_transcript_and_translation(
                final_transcripts,
                non_final_transcripts,
                translation_tokens,
            )
            return

        # Process final transcripts first (they come before non-final)
        if final_transcripts:
            if use_holding:
                self.holding_final_tokens.extend(final_transcripts)
                self.holding_translation_tokens.extend(translation_tokens)
                if effective == HoldingMode.ENDPOINTING_ONLY:
                    last_end_ms = max(t.end_ms for t in final_transcripts)
                    self._last_final_time_ms = last_end_ms
                    self._last_final_wall_ms = int(time.time() * 1000)
            else:
                await self._send_transcript_and_translation(
                    final_transcripts, translation_tokens, is_final=True
                )

        # Process non-final transcripts
        if non_final_transcripts:
            tokens = non_final_transcripts
            if use_holding and self.holding_final_tokens:
                tokens = [*self.holding_final_tokens, *non_final_transcripts]
                # In ENDPOINTING_ONLY we only clear holding on flush (endpoint or
                # disconnect), not when sending cumulative non-final.
            await self._send_transcript_and_translation(
                tokens,
                translation_tokens,
                is_final=False,
            )

    async def _send_mixed_transcript_and_translation(
        self,
        final_transcripts: List[SonioxTranscriptToken],
        non_final_transcripts: List[SonioxTranscriptToken],
        translation_tokens: List[SonioxTranslationToken],
    ) -> None:
        """Send one batch with both final and non-final segments."""
        adjusted_final_tokens, adjusted_final = (
            self._adjust_tokens_for_sentence_end_finality(
                final_transcripts,
                True,
            )
        )
        adjusted_non_final_tokens, _ = (
            self._adjust_tokens_for_sentence_end_finality(
                non_final_transcripts,
                False,
            )
        )

        asr_results: List[ASRResult] = []
        if adjusted_final and adjusted_final_tokens:
            asr_results.extend(
                self._create_asr_results(adjusted_final_tokens, True)
            )
            if adjusted_non_final_tokens:
                asr_results.extend(
                    self._create_asr_results(adjusted_non_final_tokens, False)
                )
        elif adjusted_non_final_tokens:
            asr_results.extend(
                self._create_asr_results(adjusted_non_final_tokens, False)
            )
        elif adjusted_final_tokens:
            asr_results.extend(
                self._create_asr_results(adjusted_final_tokens, False)
            )
        if not asr_results:
            return

        await self._publish_asr_results(asr_results, translation_tokens)

    async def _publish_asr_results(
        self,
        asr_results: List[ASRResult],
        translation_tokens: List[SonioxTranslationToken],
    ) -> None:
        """Publish one asr_result per segment, then one asr_results batch.

        Per-segment asr_result is kept for backward compatibility. In a mixed
        final/non-final batch, translation is sent only for final segments:
        Soniox emits translation tokens with is_final=true, and partial ASR
        segments must not trigger a translation event.
        """

        for index, result in enumerate(asr_results):
            if index > 0 and not result.id:
                result.id = self._get_uuid()
            await self.send_asr_result(result)
            result_id: str = result.id or self.uuid

            self.last_transcript_text = result.text
            self.last_transcript_start_ms = result.start_ms
            self.last_transcript_duration_ms = result.duration_ms
            self.last_transcript_is_final = result.final
            self.last_transcript_id = result_id

            # Gate on runtime ASR finality, not translation_token.is_final.
            if translation_tokens:
                if (
                    self.config is None
                    or self.config.holding_mode
                    == HoldingMode.SENTENCE_TERMINATOR
                ):
                    # In SENTENCE_TERMINATOR mode, asr_results are sent in segments, so it is necessary to determine whether it is the final segment
                    if result.final:
                        await self._send_translation_results(
                            translation_tokens,
                            result.final,
                            result.text,
                            result.start_ms,
                            result.duration_ms,
                            result_id,
                        )
                else:
                    # other modes, send translation for each segment (per language)
                    await self._send_translation_results(
                        translation_tokens,
                        result.final,
                        result.text,
                        result.start_ms,
                        result.duration_ms,
                        result_id,
                    )

        await self._send_asr_results_data(asr_results)

    async def _send_asr_results_data(self, results: List[ASRResult]) -> None:
        """Send asr_results using payloads already populated by send_asr_result."""
        if not results:
            return

        payload = ASRResults(results=results).model_dump()
        data = Data.create("asr_results")
        data.set_property_from_json(None, json.dumps(payload))
        await self.ten_env.send_data(data)
        self.ten_env.log_info(
            f"send asr_results: {payload}",
            category=LOG_CATEGORY_KEY_POINT,
        )

    async def _send_transcript_and_translation(
        self,
        transcript_tokens: List[SonioxTranscriptToken],
        translation_tokens: List[SonioxTranslationToken],
        is_final: bool,
    ) -> None:
        """Send ASR results and their translations."""
        adjusted_tokens, adjusted_final = (
            self._adjust_tokens_for_sentence_end_finality(
                transcript_tokens,
                is_final,
            )
        )
        if not adjusted_tokens:
            return

        # Create and send ASR results
        asr_results = self._create_asr_results(adjusted_tokens, adjusted_final)
        await self._publish_asr_results(asr_results, translation_tokens)

    async def _send_translation_results(
        self,
        translation_tokens: List[SonioxTranslationToken],
        is_final: bool,
        source_text: str,
        start_ms: int,
        duration_ms: int,
        result_id: str | None = None,
    ) -> None:
        """Send translation results with timing from corresponding transcript."""
        if not translation_tokens:
            return

        # Combine all translation tokens into one text
        text = "".join(token.text for token in translation_tokens)

        # Use provided result_id if available, otherwise fall back to self.uuid
        # result_id should match the corresponding asr_result.id
        translation_id = result_id if result_id is not None else self.uuid

        translation_result = ASRTranslationResult(
            id=translation_id,
            text=text,
            source_text=source_text,
            final=is_final,
            start_ms=start_ms,
            duration_ms=duration_ms,
            language=map_language_code(translation_tokens[0].language),
            source_language=map_language_code(
                translation_tokens[0].source_language
            ),
        )
        if self.metadata is not None:
            translation_result.metadata = self.metadata

        # Send as Data message with name 'asr_translation_result'
        data = Data.create("asr_translation_result")
        data.set_property_from_json(None, translation_result.model_dump_json())

        self.ten_env.log_info(
            f"send_asr_translation_result: {translation_result.model_dump_json()}",
            category=LOG_CATEGORY_KEY_POINT,
        )
        await self.ten_env.send_data(data)

    def _create_asr_results(
        self, tokens: List[SonioxTranscriptToken], is_final: bool
    ) -> List[ASRResult]:
        """
        Create ASRResult objects from a list of SonioxTranscriptToken, grouped by language.
        """
        return self._create_asr_results_for_group(tokens, is_final)

    def _create_asr_results_for_group(
        self, tokens: List[SonioxTranscriptToken], is_final: bool
    ) -> List[ASRResult]:
        if not tokens:
            return []

        results: List[ASRResult] = []
        current_language = map_language_code(tokens[0].language or "en")
        current_tokens: List[SonioxTranscriptToken] = []

        for token in tokens:
            token_language = map_language_code(token.language or "en")

            if token_language != current_language and current_tokens:
                results.append(
                    self._create_single_asr_result(
                        current_tokens, current_language, is_final
                    )
                )
                current_tokens = []
                current_language = token_language

            current_tokens.append(token)

        if current_tokens:
            results.append(
                self._create_single_asr_result(
                    current_tokens, current_language, is_final
                )
            )

        return results

    def _calculate_average_confidence(
        self, tokens: List[SonioxTranscriptToken]
    ) -> Optional[float]:
        """Calculate average confidence from tokens, skipping None values."""
        confidences = [t.confidence for t in tokens if t.confidence is not None]
        if not confidences:
            return None
        return sum(confidences) / len(confidences)

    def _create_single_asr_result(
        self, tokens: List[SonioxTranscriptToken], language: str, is_final: bool
    ) -> ASRResult:
        words = []
        text = ""
        start_ms = tokens[0].start_ms
        end_ms = tokens[-1].end_ms
        duration_ms = end_ms - start_ms

        for token in tokens:
            word = {
                "word": token.text,
                "start_ms": self._adjust_timestamp(token.start_ms),
                "duration_ms": token.end_ms - token.start_ms,
                "stable": is_final,
            }
            words.append(word)
            text += token.text

        # Calculate average confidence
        avg_confidence = self._calculate_average_confidence(tokens)
        metadata = {}
        if avg_confidence is not None:
            metadata["asr_info"] = {"confidence": avg_confidence}

        return ASRResult(
            text=text,
            final=is_final,
            start_ms=self._adjust_timestamp(start_ms),
            duration_ms=duration_ms,
            language=language,
            words=words,
            metadata=metadata,
        )

    def _adjust_timestamp(self, timestamp_ms: int) -> int:
        return int(
            self.audio_timeline.get_audio_duration_before_time(timestamp_ms)
            + self.sent_user_audio_duration_ms_before_last_reset
        )
