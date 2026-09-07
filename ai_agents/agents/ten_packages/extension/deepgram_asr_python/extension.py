from datetime import datetime
import os
import asyncio
import copy
from typing import Dict, Any

from typing_extensions import override
from .const import (
    DUMP_FILE_NAME,
    MODULE_NAME_ASR,
)
from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorVendorInfo,
    ModuleErrorCode,
)
from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
    Data,
)
from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_KEY_POINT,
)

from ten_ai_base.dumper import Dumper
from .reconnect_manager import ReconnectManager
from .recognition import DeepgramASRRecognition, DeepgramASRRecognitionCallback
from .config import DeepgramASRConfig


class DeepgramASRExtension(
    AsyncASRBaseExtension, DeepgramASRRecognitionCallback
):
    """Deepgram ASR Extension"""

    def __init__(self, name: str):
        super().__init__(name)
        self.recognition: DeepgramASRRecognition | None = None
        self.config: DeepgramASRConfig | None = None
        self.audio_dumper: Dumper | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        # Reconnection manager
        self.reconnect_manager: ReconnectManager = None  # type: ignore

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None

    @override
    def vendor(self) -> str:
        """Get ASR vendor name"""
        return "deepgram"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        params = self.config.params or {}
        key = None
        for name in ("api_key", "key"):
            value = params.get(name)
            if isinstance(value, str) and value.strip():
                key = value
                break
        fields = {
            "key": key,
            "url": params.get("url"),
            "model": params.get("model"),
        }
        return {k: v for k, v in fields.items() if v}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        # Initialize reconnection manager
        self.reconnect_manager = ReconnectManager(logger=ten_env)

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            self.config = DeepgramASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)

            # Apply default params based on model type (nova or flux)
            self.config.apply_defaults()

            ten_env.log_info(
                f"config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
                await self.audio_dumper.start()
        except Exception as e:
            ten_env.log_error(f"Invalid Deepgram config: {e}")
            self.config = DeepgramASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def start_connection(self) -> None:
        """Start ASR connection"""
        assert self.config is not None
        self.ten_env.log_info("Starting Deepgram connection")

        try:
            # Check required credentials
            api_key = self.config.params.get("api_key", "")
            key = self.config.params.get("key", "")

            # Use api_key if available, otherwise fallback to key
            final_api_key = (
                api_key
                if api_key
                and (isinstance(api_key, str) and api_key.strip() != "")
                else key
            )

            # Check if final_api_key is valid
            if not final_api_key or (
                isinstance(final_api_key, str) and final_api_key.strip() == ""
            ):
                error_msg = "Deepgram API key is required but missing or empty"
                self.ten_env.log_error(error_msg)
                error = ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=error_msg,
                )
                await self.send_asr_error(error)
                await self.on_disconnected(
                    code=error.code, message=error.message
                )
                return

            # Stop existing connection
            if self.is_connected():
                await self.stop_connection()

            # Create recognition instance
            self.recognition = DeepgramASRRecognition(
                api_key=final_api_key,
                audio_timeline=self.audio_timeline,
                ten_env=self.ten_env,
                config=self.config.params,
                callback=self,
            )

            asyncio.create_task(self.recognition.start(timeout=10))

        except Exception as e:
            self.ten_env.log_error(f"Failed to start Deepgram connection: {e}")
            error = ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=str(e),
            )
            await self.send_asr_error(error)
            await self.on_disconnected(code=error.code, message=error.message)

    @override
    async def finalize(self, _session_id: str | None) -> None:
        """Finalize recognition"""
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        self.ten_env.log_debug(
            f"Deepgram finalize start at {self.last_finalize_timestamp}"
        )

        finalize_mode = self.config.finalize_mode
        if self.config.is_flux_model:
            if finalize_mode == "ignore":
                await self._finalize_end()
            else:
                await self._handle_finalize_mute_pkg()
        else:
            if finalize_mode == "flush_api":
                await self._handle_finalize_flush_api()
            elif finalize_mode == "mute_pkg":
                await self._handle_finalize_mute_pkg()
            else:
                raise ValueError(f"invalid finalize mode: {finalize_mode}")

    async def _handle_event_result(self, event: str) -> None:
        """Handle ASR event result"""
        self.ten_env.log_info(
            f"_handle_event_result: {event}",
            category=LOG_CATEGORY_KEY_POINT,
        )
        if event == "StartOfTurn":
            data = Data.create("sos")
            await self.ten_env.send_data(data)
        elif event == "EndOfTurn":
            data = Data.create("eos")
            await self.ten_env.send_data(data)
        elif event == "EagerEndOfTurn":
            data = Data.create("eager_eos")
            await self.ten_env.send_data(data)

    def _build_metadata_with_asr_info(
        self,
        additional_fields: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Build metadata according to protocol: session_id at root, others in asr_info.

        Args:
            additional_fields: Additional fields to add to asr_info

        Returns:
            Metadata dict with structure: {"session_id": "...", "asr_info": {...}}
        """
        # Start with a copy of base metadata if available
        base_metadata = (
            copy.deepcopy(self.metadata) if self.metadata is not None else {}
        )

        # Extract session_id from base metadata if present
        session_id = base_metadata.pop("session_id", None)

        # Collect all other fields into asr_info
        asr_info = copy.deepcopy(base_metadata)

        # Add vendor field to asr_info
        asr_info["vendor"] = self.vendor()
        asr_info["model"] = self.config.params.get("model", "unknown")

        # Add additional fields to asr_info if provided
        if additional_fields:
            asr_info.update(additional_fields)

        # Build final metadata structure
        metadata: Dict[str, Any] = {}
        if session_id is not None:
            metadata["session_id"] = session_id
        metadata["asr_info"] = asr_info

        return metadata

    async def _handle_asr_result(
        self,
        text: str,
        final: bool,
        start_ms: int = 0,
        duration_ms: int = 0,
        language: str = "",
        metadata: Dict[str, Any] | None = None,
    ):
        """Process ASR recognition result"""
        assert self.config is not None

        if final:
            await self._finalize_end()

        asr_result = ASRResult(
            text=text,
            final=final,
            start_ms=start_ms,
            duration_ms=duration_ms,
            language=language,
            words=[],
            metadata=metadata if metadata is not None else {},
        )

        await self.send_asr_result(asr_result)

    async def _handle_finalize_disconnect(self):
        """Handle disconnect mode finalization.

        Deprecated: This method uses flush_api for finalization.
        """
        if self.recognition:
            await self.recognition.stop()
            self.ten_env.log_debug("Deepgram finalize completed")

    async def _handle_finalize_flush_api(self):
        """Handle flush API mode finalization"""
        if self.recognition:
            await self.recognition.stop()
            self.ten_env.log_debug("Deepgram finalize completed")

    async def _handle_finalize_mute_pkg(self):
        """Handle mute package mode finalization"""
        # Send silence package
        if self.recognition and self.config:
            mute_pkg_duration_ms = self.config.mute_pkg_duration_ms
            sample_rate = self.config.params.get("sample_rate", 16000)
            silence_duration = mute_pkg_duration_ms / 1000.0
            silence_samples = int(sample_rate * silence_duration)
            silence_data = b"\x00" * (silence_samples * 2)  # 16-bit samples
            self.audio_timeline.add_silence_audio(mute_pkg_duration_ms)
            await self.recognition.send_audio_frame(silence_data)
            self.ten_env.log_debug("Deepgram finalize mute package sent")

    async def _handle_reconnect(self):
        """Handle reconnection"""
        # Attempt reconnection
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return

        success = await self.reconnect_manager.handle_reconnect(
            connection_func=self.start_connection,
            error_handler=self.send_asr_error,
        )

        if success:
            self.ten_env.log_debug(
                "Reconnection attempt initiated successfully"
            )
        else:
            info = self.reconnect_manager.get_attempts_info()
            self.ten_env.log_debug(
                f"Reconnection attempt failed. Status: {info}"
            )

    async def _finalize_end(self) -> None:
        """Handle finalization end logic"""
        if self.last_finalize_timestamp != 0:
            timestamp = int(datetime.now().timestamp() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_debug(
                f"Deepgram finalize end at {timestamp}, latency: {latency}ms"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def stop_connection(self) -> None:
        """Stop ASR connection"""
        self.ten_env.log_info("Deepgram stop_connection stop_connection")
        try:
            if self.recognition:
                await self.recognition.close()
                self.recognition = None
            self.ten_env.log_info("Deepgram connection stopped1")
        except Exception as e:
            self.ten_env.log_error(f"Error stopping Deepgram connection: {e}")

    @override
    def is_connected(self) -> bool:
        """Check connection status"""
        is_connected: bool = (
            self.recognition is not None and self.recognition.is_connected()
        )
        return is_connected

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        """Buffer strategy configuration"""
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    def input_audio_sample_rate(self) -> int:
        """Input audio sample rate"""
        assert self.config is not None
        return self.config.params.get("sample_rate", 16000)

    @override
    async def send_audio(
        self, frame: AudioFrame, _session_id: str | None
    ) -> bool:
        """Send audio data"""
        assert self.recognition is not None

        try:
            buf = frame.lock_buf()
            audio_data = bytes(buf)

            # Dump audio data
            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)

            # self.ten_env.log_debug(f"Sending audio frame: {len(audio_data)} bytes")
            await self.recognition.send_audio_frame(audio_data)

            frame.unlock_buf(buf)
            return True

        except Exception as e:
            self.ten_env.log_error(f"Error sending audio to Deepgram Flux: {e}")
            frame.unlock_buf(buf)
            return False

    # Vendor callback functions
    @override
    async def on_open(self) -> None:
        """Handle callback when connection is established"""
        self.ten_env.log_info(
            "vendor connection opened",
            category=LOG_CATEGORY_VENDOR,
        )
        # Notify reconnect manager of successful connection
        self.reconnect_manager.mark_connection_successful()

        # Reset timeline and audio duration
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()
        await self.on_connected()

    @override
    async def on_result(self, message_data: Dict[str, Any]) -> None:
        """Handle recognition result callback"""
        assert self.config is not None

        try:
            # Extract basic fields
            if self.config.is_flux_model:
                event = message_data.get("event", "")
                result_to_send = message_data.get("transcript", "")

                is_final = event == "EndOfTurn"

                start_ms = int(
                    message_data.get("audio_window_start", 0) * 1000 or 0
                )
                end_ms = int(
                    message_data.get("audio_window_end", 0) * 1000 or 0
                )
                duration_ms = end_ms - start_ms

                actual_start_ms = int(
                    self.audio_timeline.get_audio_duration_before_time(start_ms)
                    + self.sent_user_audio_duration_ms_before_last_reset
                )
                await self._handle_event_result(event)

                # Build metadata with asr_info for flux model
                turn_index = message_data.get("turn_index")
                end_of_turn_confidence = message_data.get(
                    "end_of_turn_confidence"
                )

                asr_info_fields: Dict[str, Any] = {
                    "turn_event": event,
                }
                if turn_index is not None:
                    asr_info_fields["turn_index"] = turn_index
                if end_of_turn_confidence is not None:
                    asr_info_fields["end_of_turn_confidence"] = (
                        end_of_turn_confidence
                    )

                metadata = self._build_metadata_with_asr_info(asr_info_fields)

                # Process ASR result
                await self._handle_asr_result(
                    text=result_to_send,
                    final=is_final,
                    start_ms=actual_start_ms,
                    duration_ms=duration_ms,
                    language=self.config.asr_result_language,
                    metadata=metadata,
                )

            else:
                is_final = message_data.get("is_final", False)
                # Extract transcript and words from channel.alternatives[0]
                channel = message_data.get("channel", {})
                alternatives = channel.get("alternatives", [])
                if not alternatives:
                    self.ten_env.log_debug("No alternatives in Deepgram result")
                    return

                first_alt = alternatives[0]
                result_to_send = first_alt.get("transcript", "")

                # Extract timing information (in seconds, convert to milliseconds)
                start_seconds = message_data.get("start", 0)
                duration_seconds = message_data.get("duration", 0)
                start_ms = int(start_seconds * 1000)
                duration_ms = int(duration_seconds * 1000)

                # Calculate actual start time using audio timeline
                actual_start_ms = int(
                    self.audio_timeline.get_audio_duration_before_time(start_ms)
                    + self.sent_user_audio_duration_ms_before_last_reset
                )
                metadata = self._build_metadata_with_asr_info(
                    {
                        "api": "listen_v1",
                        "message_type": message_data.get("type", "Results"),
                        "is_final": is_final,
                        "speech_final": message_data.get("speech_final", False),
                    },
                )
                # Process ASR result
                await self._handle_asr_result(
                    text=result_to_send,
                    final=is_final,
                    start_ms=actual_start_ms,
                    duration_ms=duration_ms,
                    language=self.config.asr_result_language,
                    metadata=metadata,
                )

        except Exception as e:
            self.ten_env.log_error(f"Error processing Deepgram result: {e}")

    @override
    async def on_error(
        self, error_msg: str, error_code: int | None = None
    ) -> None:
        """Handle error callback"""
        self.ten_env.log_error(
            f"vendor_error: code: {error_code}, reason: {error_msg}",
            category=LOG_CATEGORY_VENDOR,
        )

        vendor_info = ModuleErrorVendorInfo(
            vendor=self.vendor(),
            code=str(error_code) if error_code else "unknown",
            message=error_msg,
        )
        error_criteria = ["400", "401", "402", "403", "404"]
        is_fatal = any(code in error_msg for code in error_criteria)
        module_error = ModuleError(
            module=MODULE_NAME_ASR,
            code=(
                ModuleErrorCode.FATAL_ERROR.value
                if is_fatal
                else ModuleErrorCode.NON_FATAL_ERROR.value
            ),
            message=error_msg,
        )
        await self.send_asr_error(module_error, vendor_info)

        if not self.is_connected():
            await self.on_disconnected(
                code=module_error.code,
                message=error_msg,
                vendor_info=vendor_info,
            )

        if not is_fatal and not self.stopped and not self.is_connected():
            self.ten_env.log_warn(
                "Deepgram connection error unexpectedly. Reconnecting..."
            )
            await self._handle_reconnect()

    @override
    async def on_close(
        self, vendor_code: int = 0, vendor_message: str = "closed"
    ) -> None:
        """Handle callback when connection is closed"""
        self.ten_env.log_info(
            f"vendor connection closed: code={vendor_code}, message={vendor_message}",
            category=LOG_CATEGORY_VENDOR,
        )
        vendor_info = None
        if vendor_code not in (0, 1000):
            vendor_info = ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(vendor_code),
                message=vendor_message,
            )
        await self.on_disconnected(
            code=0, message="closed", vendor_info=vendor_info
        )

        if not self.stopped:
            self.ten_env.log_warn(
                "Deepgram connection closed unexpectedly. Reconnecting..."
            )
            await self._handle_reconnect()
