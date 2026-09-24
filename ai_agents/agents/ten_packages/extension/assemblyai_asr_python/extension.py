from datetime import datetime
import os
from typing import Optional, Dict, Any

from typing_extensions import override
from .const import DUMP_FILE_NAME
from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeDiscard,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorVendorInfo,
    ModuleErrorCode,
    ModuleType,
)
from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
)

from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
)

from ten_ai_base.dumper import Dumper
from .reconnect_manager import ReconnectManager
from .config import AssemblyAIASRConfig
from .recognition import (
    AssemblyAIWSRecognition,
    AssemblyAIWSRecognitionCallback,
)


class AssemblyAIASRExtension(
    AsyncASRBaseExtension, AssemblyAIWSRecognitionCallback
):
    """AssemblyAI ASR Extension"""

    def __init__(self, name: str):
        super().__init__(name)
        self.recognition: Optional[AssemblyAIWSRecognition] = None
        self.config: Optional[AssemblyAIASRConfig] = None
        self.audio_dumper: Optional[Dumper] = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0

        self.reconnect_manager: Optional[ReconnectManager] = None

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        try:
            if self.audio_dumper:
                await self.audio_dumper.stop()
                self.audio_dumper = None

            if self.reconnect_manager:
                self.reconnect_manager = None

            self.config = None

        except Exception as e:
            ten_env.log_error(f"Error during deinit: {e}")

    @override
    def vendor(self) -> str:
        """Get ASR vendor name"""
        return "assemblyai"

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        self.reconnect_manager = ReconnectManager(logger=ten_env)

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            temp_config = AssemblyAIASRConfig.model_validate_json(config_json)
            ten_env.log_info(f"AssemblyAI ASR temp_config: {temp_config}")
            self.config = temp_config
            self.config.update(self.config.params)
            ten_env.log_info(f"AssemblyAI ASR config: {self.config}")

            ten_env.log_info(
                f"AssemblyAI ASR config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
                await self.audio_dumper.start()

        except Exception as e:
            ten_env.log_error(f"Invalid AssemblyAI ASR config: {e}")
            self.config = AssemblyAIASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=ModuleType.ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def start_connection(self) -> None:
        """Start ASR connection"""
        assert self.config is not None
        self.ten_env.log_info("Starting AssemblyAI ASR connection")

        try:
            if not self.config.api_key or self.config.api_key.strip() == "":
                error_msg = "AssemblyAI API key is required but not provided or is empty"
                self.ten_env.log_error(error_msg)
                await self.send_asr_error(
                    ModuleError(
                        module=ModuleType.ASR,
                        code=ModuleErrorCode.FATAL_ERROR.value,
                        message=error_msg,
                    ),
                )
                return

            if self.is_connected():
                await self.stop_connection()

            assemblyai_config = {
                "sample_rate": self.config.sample_rate,
                "encoding": self.config.encoding,
                "end_of_turn_confidence_threshold": self.config.end_of_turn_confidence_threshold,
                "format_turns": self.config.format_turns,
                "keyterms_prompt": self.config.keyterms_prompt,
                "min_end_of_turn_silence_when_confident": self.config.min_end_of_turn_silence_when_confident,
                "max_turn_silence": self.config.max_turn_silence,
            }
            self.ten_env.log_info(f"AssemblyAI ASR config: {assemblyai_config}")
            self.recognition = AssemblyAIWSRecognition(
                api_key=self.config.api_key,
                ws_url=self.config.ws_url,
                audio_timeline=self.audio_timeline,
                ten_env=self.ten_env,
                config=assemblyai_config,
                callback=self,
            )

            await self.recognition.start()
            self.ten_env.log_info(
                "AssemblyAI ASR connection started successfully"
            )

        except Exception as e:
            self.ten_env.log_error(
                f"Failed to start AssemblyAI ASR connection: {e}"
            )
            await self.send_asr_error(
                ModuleError(
                    module=ModuleType.ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(e),
                )
            )

    @override
    async def on_open(self) -> None:
        """Handle callback when connection is established"""
        self.ten_env.log_info(
            "vendor_status_changed: on_open",
            category=LOG_CATEGORY_VENDOR,
        )
        if self.reconnect_manager:
            self.reconnect_manager.mark_connection_successful()

        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.ten_env.log_info(
            f"AssemblyAI ASR sent_user_audio_duration_ms_before_last_reset: {self.sent_user_audio_duration_ms_before_last_reset}"
        )
        self.audio_timeline.reset()

    @override
    async def on_result(self, message_data: Dict[str, Any]) -> None:
        """Handle recognition result callback"""
        self.ten_env.log_debug(
            f"AssemblyAI ASR result: {message_data}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )
        try:
            text = message_data.get("transcript", "")
            if not text:
                return

            is_final = message_data.get("end_of_turn", False)
            turn_is_formatted = True
            if self.config.format_turns:
                turn_is_formatted = message_data.get("turn_is_formatted", False)
            all_final = is_final and turn_is_formatted
            words = message_data.get("words", [])
            start_ms = 0
            end_ms = 0

            if words:
                for word in words:
                    if word.get("word_is_final", False):
                        start_ms = word.get("start", 0)
                        break

                for word in reversed(words):
                    if word.get("word_is_final", False):
                        end_ms = word.get("end", 0)
                        break

            duration_ms = end_ms - start_ms if end_ms > start_ms else 0

            actual_start_ms = int(
                self.audio_timeline.get_audio_duration_before_time(start_ms)
                + self.sent_user_audio_duration_ms_before_last_reset
            )

            self.ten_env.log_debug(
                f"AssemblyAI ASR result: {text}, is_final: {all_final}, "
                f"start_ms: {actual_start_ms}, duration_ms: {duration_ms}"
            )

            if self.config is not None:
                await self._handle_asr_result(
                    text=text,
                    final=all_final,
                    start_ms=actual_start_ms,
                    duration_ms=duration_ms,
                    language=self.config.normalized_language,
                )
            else:
                self.ten_env.log_error(
                    "Cannot handle ASR result: config is None"
                )

        except Exception as e:
            self.ten_env.log_error(
                f"Error processing AssemblyAI ASR result: {e}"
            )

    @override
    async def on_error(
        self, error_msg: str, error_code: Optional[str] = None
    ) -> None:
        """Handle error callback"""
        self.ten_env.log_error(
            f"vendor_error: code: {error_code}, reason: {error_msg}",
            category=LOG_CATEGORY_VENDOR,
        )

        await self.send_asr_error(
            ModuleError(
                module=ModuleType.ASR,
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=error_msg,
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=error_code or "unknown",
                message=error_msg,
            ),
        )

    @override
    async def on_close(self) -> None:
        """Handle callback when connection is closed"""
        self.ten_env.log_info(
            "vendor_status_changed: on_close",
            category=LOG_CATEGORY_VENDOR,
        )

        if not self.stopped:
            await self._handle_reconnect()

    @override
    async def on_event(self, message_data: Dict[str, Any]) -> None:
        """Handle callback when event is received"""
        self.ten_env.log_info(
            f"vendor_status_changed: on_event message_data: {message_data}",
            category=LOG_CATEGORY_VENDOR,
        )

    @override
    async def finalize(self, session_id: str | None) -> None:
        """Finalize recognition"""
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        self.ten_env.log_debug(
            f"AssemblyAI ASR finalize start at {self.last_finalize_timestamp}"
        )

        if self.recognition and self.is_connected():
            await self.recognition.force_endpoint()

    async def _handle_asr_result(
        self,
        text: str,
        final: bool,
        start_ms: int = 0,
        duration_ms: int = 0,
        language: str = "",
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
        )

        await self.send_asr_result(asr_result)

    async def _handle_reconnect(self):
        """Handle reconnection"""
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return

        if not self.reconnect_manager.can_retry():
            self.ten_env.log_warn("No more reconnection attempts allowed")
            await self.send_asr_error(
                ModuleError(
                    module=ModuleType.ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message="No more reconnection attempts allowed",
                )
            )
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
                f"AssemblyAI ASR finalize end at {timestamp}, latency: {latency}ms"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def stop_connection(self) -> None:
        """Stop ASR connection"""
        try:
            if self.recognition:
                await self.recognition.close()

            self.ten_env.log_info("AssemblyAI ASR connection stopped")

        except Exception as e:
            self.ten_env.log_error(
                f"Error stopping AssemblyAI ASR connection: {e}"
            )
        finally:
            self.recognition = None

    @override
    def is_connected(self) -> bool:
        """Check connection status"""
        is_connected = (
            self.recognition is not None and self.recognition.is_connected()
        )
        return is_connected

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        """Buffer strategy configuration"""
        return ASRBufferConfigModeDiscard()

    @override
    def input_audio_sample_rate(self) -> int:
        """Input audio sample rate"""
        assert self.config is not None
        return self.config.sample_rate

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        """Send audio data"""
        assert self.config is not None

        if not self.recognition:
            self.ten_env.log_error("AssemblyAI ASR recognition not initialized")
            return False

        buf = None
        try:
            buf = frame.lock_buf()
            audio_data = bytes(buf)

            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)
            await self.recognition.send_audio_frame(audio_data)

            return True

        except Exception as e:
            self.ten_env.log_error(
                f"Error sending audio to AssemblyAI ASR: {e}"
            )
            return False
        finally:
            if buf is not None:
                frame.unlock_buf(buf)
