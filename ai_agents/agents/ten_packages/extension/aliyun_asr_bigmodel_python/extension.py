from datetime import datetime
import os
import asyncio
from typing import Any

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
)
from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_KEY_POINT,
)

from ten_ai_base.dumper import Dumper
from .reconnect_manager import ReconnectManager
from .config import AliyunASRBigmodelConfig

import dashscope
from dashscope.audio.asr import (
    Recognition,
    RecognitionCallback,
    RecognitionResult,
    VocabularyService,
)


class AliyunRecognitionCallback(RecognitionCallback):
    """Aliyun ASR Recognition Callback Class"""

    def __init__(self, extension_instance: "AliyunASRBigmodelExtension"):
        super().__init__()
        self.extension = extension_instance
        self.ten_env = extension_instance.ten_env
        self.loop = asyncio.get_event_loop()

    def on_open(self) -> None:
        """Callback when connection is established"""
        self.ten_env.log_info(
            "vendor_status_changed: on_open",
            category=LOG_CATEGORY_VENDOR,
        )
        asyncio.run_coroutine_threadsafe(
            self.extension.on_asr_open(), self.loop
        )

    def on_complete(self) -> None:
        """Callback when recognition is completed"""
        asyncio.run_coroutine_threadsafe(
            self.extension.on_asr_complete(), self.loop
        )

    def on_error(self, result: RecognitionResult) -> None:
        """Error handling callback"""
        self.ten_env.log_error(
            f"vendor_error: code: {result.status_code}, reason: {result.message}",
            category=LOG_CATEGORY_VENDOR,
        )
        asyncio.run_coroutine_threadsafe(
            self.extension.on_asr_error(result), self.loop
        )

    def on_event(self, result: RecognitionResult) -> None:
        """Recognition result event callback"""
        # Avoid str(result): dashscope >=1.26.0 __str__ expects API response headers.
        self.ten_env.log_info(
            f"Aliyun ASR result event: {result.get_sentence()}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )
        asyncio.run_coroutine_threadsafe(
            self.extension.on_asr_event(result), self.loop
        )

    def on_close(self) -> None:
        """Callback when connection is closed"""
        self.ten_env.log_info(
            "vendor_status_changed: on_close",
            category=LOG_CATEGORY_VENDOR,
        )
        asyncio.run_coroutine_threadsafe(
            self.extension.on_asr_close(), self.loop
        )


class AliyunASRBigmodelExtension(AsyncASRBaseExtension):
    """Aliyun ASR Big Model Extension"""

    def __init__(self, name: str):
        super().__init__(name)
        self.connected: bool = False
        self.recognition: Recognition | None = None
        self.config: AliyunASRBigmodelConfig | None = None
        self.audio_dumper: Dumper | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        # Vocabulary service
        self.service: VocabularyService = VocabularyService()

        # Reconnection manager
        self.reconnect_manager: ReconnectManager | None = None

        # Callback instance
        self.recognition_callback: AliyunRecognitionCallback | None = None

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_info("Deinitializing Aliyun ASR Bigmodel Extension")
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None

    @override
    def vendor(self) -> str:
        """Get ASR vendor name"""
        return "aliyun_bigmodel"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        model = self.config.params.get("model")
        return {"model": model} if model else {}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        # Initialize reconnection manager
        self.reconnect_manager = ReconnectManager(logger=ten_env)

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            temp_config = AliyunASRBigmodelConfig.model_validate_json(
                config_json
            )

            if temp_config.model == "":
                temp_config.model = "paraformer-realtime-v2"

            self.config = temp_config
            self.config.update(self.config.params)
            ten_env.log_info(
                f"Aliyun ASR config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            # Initialize Dashscope with API key
            dashscope.api_key = self.config.api_key

            # Initialize vocabulary service
            if len(self.config.vocabulary_list) > 0:
                self.config.vocabulary_id = self.service.create_vocabulary(
                    prefix=self.config.vocabulary_prefix,
                    target_model=self.config.vocabulary_target_model,
                    vocabulary=self.config.vocabulary_list,
                )

            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)

        except Exception as e:
            ten_env.log_error(f"Invalid Aliyun ASR config: {e}")
            self.config = AliyunASRBigmodelConfig.model_validate_json("{}")
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
        self.ten_env.log_info("Starting Aliyun ASR connection")

        try:
            # Check API key
            if not self.config.api_key or self.config.api_key.strip() == "":
                error_msg = (
                    "Aliyun API key is required but not provided or is empty"
                )
                self.ten_env.log_error(error_msg)
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.FATAL_ERROR.value,
                        message=error_msg,
                    ),
                )
                return

            # Stop existing connection
            if self.is_connected():
                await self.stop_connection()

            # Start audio dumper
            if self.audio_dumper:
                await self.audio_dumper.start()

            # Create callback instance
            self.recognition_callback = AliyunRecognitionCallback(self)

            # Create recognition instance
            self.recognition = Recognition(
                model=self.config.model,
                format="pcm",
                language_hints=self.config.language_hints,
                sample_rate=self.config.sample_rate,
                disfluency_removal_enabled=self.config.disfluency_removal_enabled,
                semantic_punctuation_enabled=self.config.semantic_punctuation_enabled,
                multi_threshold_mode_enabled=self.config.multi_threshold_mode_enabled,
                punctuation_prediction_enabled=self.config.punctuation_prediction_enabled,
                inverse_text_normalization_enabled=self.config.inverse_text_normalization_enabled,
                heartbeat=self.config.heartbeat,
                max_sentence_silence=self.config.max_sentence_silence,
                vocabulary_id=self.config.vocabulary_id,
                callback=self.recognition_callback,
            )

            # Start recognition
            self.recognition.start()
            self.ten_env.log_info("Aliyun ASR connection started successfully")

        except Exception as e:
            self.ten_env.log_error(
                f"Failed to start Aliyun ASR connection: {e}"
            )
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    async def on_asr_open(self) -> None:
        """Handle callback when connection is established"""
        self.ten_env.log_info("Aliyun ASR connection opened")

        self.connected = True
        # Notify reconnect manager of successful connection
        if self.reconnect_manager and self.connected:
            self.reconnect_manager.mark_connection_successful()
        # Reset timeline and audio duration
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()

    async def on_asr_complete(self) -> None:
        """Handle callback when recognition is completed"""
        self.ten_env.log_info("Aliyun ASR recognition completed")
        await self.on_asr_reconnection()

    async def on_asr_error(self, result: RecognitionResult) -> None:
        """Handle error callback"""
        self.ten_env.log_error(f"Aliyun ASR error: {result.message}")
        # Send error information
        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=result.message,
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=(
                    str(result.status_code)
                    if hasattr(result, "status_code")
                    else "unknown"
                ),
                message=result.message,
            ),
        )

    async def on_asr_event(self, result: RecognitionResult) -> None:
        """Handle recognition result event callback"""
        try:
            sentence = result.get_sentence()
            self.ten_env.log_debug(
                f"vendor_result: on_event: {sentence}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )
            if (
                isinstance(sentence, dict)
                and "text" in sentence
                and sentence["text"]
            ):
                text = sentence["text"]
                is_final = RecognitionResult.is_sentence_end(sentence)

                # Calculate timestamps
                start_ms = int(sentence.get("begin_time", 0) or 0)
                end_ms = int(sentence.get("end_time", 0) or 0)

                # If end_time is 0 or None, get end_time from the last word
                if end_ms == 0 and "words" in sentence and sentence["words"]:
                    words = sentence["words"]
                    if words and len(words) > 0:
                        last_word = words[-1]
                        if "end_time" in last_word and last_word["end_time"]:
                            end_ms = int(last_word["end_time"])
                            self.ten_env.log_debug(
                                f"Using last word end_time: {end_ms} as sentence end_time"
                            )

                duration_ms = end_ms - start_ms if end_ms > start_ms else 0

                # Calculate actual start time
                actual_start_ms = int(
                    self.audio_timeline.get_audio_duration_before_time(start_ms)
                    + self.sent_user_audio_duration_ms_before_last_reset
                )

                self.ten_env.log_debug(
                    f"Aliyun ASR result: {text}, is_final: {is_final}, "
                    f"start_ms: {actual_start_ms}, duration_ms: {duration_ms}",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )

                # Process ASR result
                if self.config is not None:
                    await self._handle_asr_result(
                        text=text,
                        final=is_final,
                        start_ms=actual_start_ms,
                        duration_ms=duration_ms,
                        language=self.config.normalized_language,
                    )
                else:
                    self.ten_env.log_error(
                        "Cannot handle ASR result: config is None"
                    )

        except Exception as e:
            self.ten_env.log_error(f"Error processing Aliyun ASR result: {e}")

    async def on_asr_close(self) -> None:
        """Handle callback when connection is closed"""
        self.ten_env.log_debug("Aliyun ASR connection closed")
        await self.on_asr_reconnection()

    async def on_asr_reconnection(self) -> None:
        if self.connected == False:
            return

        self.connected = False

        if not self.stopped:
            self.ten_env.log_warn(
                "Aliyun ASR connection closed unexpectedly. Reconnecting..."
            )
            await self._handle_reconnect()

    @override
    async def finalize(self, session_id: str | None) -> None:
        """Finalize recognition"""
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        self.ten_env.log_info(
            f"vendor_cmd: finalize start at {self.last_finalize_timestamp}",
            category=LOG_CATEGORY_VENDOR,
        )

        if self.config.finalize_mode == "disconnect":
            await self._handle_finalize_disconnect()
        elif self.config.finalize_mode == "mute_pkg":
            await self._handle_finalize_mute_pkg()

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

    async def _handle_finalize_disconnect(self):
        """Handle disconnect mode finalization"""
        if self.recognition:
            try:
                if self.is_connected():
                    self.recognition.stop()
                    self.ten_env.log_debug(
                        "Aliyun ASR finalize disconnect completed"
                    )
                else:
                    self.ten_env.log_debug(
                        "Aliyun ASR finalize disconnect completed, but not connected"
                    )
            except Exception as e:
                self.ten_env.log_error(f"Error during finalize disconnect: {e}")
                # Don't propagate the error, just log it

    async def _handle_finalize_mute_pkg(self):
        """Handle mute package mode finalization"""
        # Send silence package
        if self.recognition and self.config and self.is_connected():
            try:
                mute_pkg_duration_ms = self.config.mute_pkg_duration_ms
                silence_duration = mute_pkg_duration_ms / 1000.0
                silence_samples = int(
                    self.config.sample_rate * silence_duration
                )
                silence_data = b"\x00" * (silence_samples * 2)  # 16-bit samples
                self.audio_timeline.add_silence_audio(mute_pkg_duration_ms)
                self.recognition.send_audio_frame(silence_data)
                self.ten_env.log_debug("Aliyun ASR finalize mute package sent")
            except Exception as e:
                self.ten_env.log_error(
                    f"Error sending mute package during finalize: {e}"
                )
                # Don't propagate the error, just log it
        else:
            self.ten_env.log_debug(
                "Aliyun ASR finalize mute package skipped - not connected"
            )

    async def _handle_reconnect(self):
        """Handle reconnection"""
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return

        # Check if retry is still possible
        if not self.reconnect_manager.can_retry():
            self.ten_env.log_warn("No more reconnection attempts allowed")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message="No more reconnection attempts allowed",
                )
            )
            return

        # Attempt reconnection
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
                f"Aliyun ASR finalize end at {timestamp}, latency: {latency}ms"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def stop_connection(self) -> None:
        """Stop ASR connection"""
        try:
            if self.recognition:
                self.recognition.stop()
                self.recognition = None

            self.recognition_callback = None
            self.connected = False
            self.ten_env.log_info("Aliyun ASR connection stopped")

        except Exception as e:
            self.ten_env.log_error(f"Error stopping Aliyun ASR connection: {e}")

    @override
    def is_connected(self) -> bool:
        """Check connection status"""
        is_connected = self.connected and self.recognition is not None
        # self.ten_env.log_debug(f"Aliyun ASR is_connected: {is_connected}")
        return is_connected

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        """Buffer strategy configuration"""
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

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
            return False

        try:
            buf = frame.lock_buf()
            audio_data = bytes(buf)

            # Dump audio data
            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)

            # Update timeline
            self.audio_timeline.add_user_audio(
                int(len(audio_data) / (self.config.sample_rate / 1000 * 2))
            )

            # self.ten_env.log_info(f"Sending audio data: {len(audio_data)} bytes")

            # Send audio data to recognition service
            try:
                self.recognition.send_audio_frame(audio_data)
                # self.ten_env.log_info("Audio frame sent successfully")
            except Exception as e:
                self.ten_env.log_error(f"Error in send_audio_frame: {e}")
                return False

            frame.unlock_buf(buf)
            # self.ten_env.log_info("Audio frame successfully processed, returning True")
            return True

        except Exception as e:
            self.ten_env.log_error(f"Error sending audio to Aliyun ASR: {e}")
            frame.unlock_buf(buf)
            self.ten_env.log_error(
                "Failed to process audio frame, returning False"
            )
            return False
