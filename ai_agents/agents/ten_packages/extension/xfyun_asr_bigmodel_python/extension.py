from datetime import datetime
import os
from typing import Optional, Dict, Any

from typing_extensions import override
from .const import (
    DUMP_FILE_NAME,
    MODULE_NAME_ASR,
)
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
)
from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
)
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_VENDOR,
)
from ten_ai_base.dumper import Dumper
from .reconnect_manager import ReconnectManager
from .recognition import XfyunWSRecognition, XfyunWSRecognitionCallback
from .config import XfyunASRConfig


class XfyunBigmodelASRExtension(
    AsyncASRBaseExtension, XfyunWSRecognitionCallback
):
    """Xfyun ASR Extension"""

    def __init__(self, name: str):
        super().__init__(name)
        self.recognition: Optional[XfyunWSRecognition] = None
        self.config: Optional[XfyunASRConfig] = None
        self.audio_dumper: Optional[Dumper] = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0

        # WPGS mode status variables
        self.wpgs_buffer: Dict[int, Dict[str, Any]] = (
            {}
        )  # Mapping from sequence number to data including text, bg, ed

        # Reconnection manager
        self.reconnect_manager: Optional[ReconnectManager] = None

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None

    @override
    def vendor(self) -> str:
        """Get ASR vendor name"""
        return "xfyun_bigmodel"

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        # Initialize reconnection manager
        self.reconnect_manager = ReconnectManager(logger=ten_env)

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            self.config = XfyunASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)
            ten_env.log_info(
                f"Xfyun ASR config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)

        except Exception as e:
            ten_env.log_error(f"Invalid Xfyun ASR config: {e}")
            self.config = XfyunASRConfig.model_validate_json("{}")
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
        self.ten_env.log_info("Starting Xfyun ASR connection")

        try:
            # Check required credentials
            if not self.config.app_id or self.config.app_id.strip() == "":
                error_msg = (
                    "Xfyun App ID is required but not provided or is empty"
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

            if not self.config.api_key or self.config.api_key.strip() == "":
                error_msg = (
                    "Xfyun API key is required but not provided or is empty"
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

            if (
                not self.config.api_secret
                or self.config.api_secret.strip() == ""
            ):
                error_msg = (
                    "Xfyun API secret is required but not provided or is empty"
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

            # Prepare Xfyun config
            xfyun_config = {
                "host": self.config.host,
                "domain": self.config.domain,
                "language": self.config.language,
                "language_name": self.config.language_name,
                "accent": self.config.accent,
                "dwa": self.config.dwa,
                "eos": self.config.eos,
                "punc": self.config.punc,
                "nunum": self.config.nunum,
                "vto": self.config.vto,
                "samplerate": self.config.sample_rate,
            }

            # Create recognition instance
            self.recognition = XfyunWSRecognition(
                app_id=self.config.app_id,
                api_key=self.config.api_key,
                api_secret=self.config.api_secret,
                audio_timeline=self.audio_timeline,
                ten_env=self.ten_env,
                config=xfyun_config,
                callback=self,
            )

            # Start recognition (now async)
            success = await self.recognition.start()
            if success:
                self.ten_env.log_info(
                    "Xfyun ASR connection started successfully"
                )
            else:
                error_msg = "Failed to start Xfyun ASR connection"
                self.ten_env.log_error(error_msg)
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message=error_msg,
                    ),
                )

        except Exception as e:
            self.ten_env.log_error(f"Failed to start Xfyun ASR connection: {e}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def on_open(self) -> None:
        """Handle callback when connection is established"""
        self.ten_env.log_info(
            "vendor_status_changed: on_open",
            category=LOG_CATEGORY_VENDOR,
        )
        # Notify reconnect manager of successful connection
        if self.reconnect_manager:
            self.reconnect_manager.mark_connection_successful()

        # Reset timeline and audio duration (recognition.py handles internal timeline)
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()

        # Reset WPGS status variables
        self.wpgs_buffer.clear()
        self.ten_env.log_debug("Xfyun ASR WPGS state reset")

    @override
    async def on_result(self, message_data: dict) -> None:
        """Handle recognition result callback"""
        # self.ten_env.log_debug(f"Xfyun ASR result: {message_data}")
        try:
            code = message_data.get("code")
            if code != 0:
                # Error handling is already done in recognition.py's _on_message
                return

            data = message_data.get("data", {})
            status = data.get("status")
            result_data = data.get("result", {})

            # Get result sequence number
            sn = result_data.get("sn", -1)

            # Extract sentence timing information
            start_ms = result_data.get("bg", 0)  # Sentence start time, ms
            end_ms = result_data.get("ed", 0)  # Sentence end time, ms
            duration_ms = end_ms - start_ms if end_ms > start_ms else 0

            # Process current data segment
            data_ws = result_data.get("ws", [])
            result = ""
            for i in data_ws:
                for w in i.get("cw", []):
                    result += w.get("w", "")

            # Determine if this is a final result
            is_final = False

            # Handle real-time speech-to-text wpgs mode
            pgs = result_data.get("pgs")
            result_to_send = result

            if pgs:
                if pgs == "apd":  # Append mode
                    self.ten_env.log_debug(
                        f"Xfyun ASR wpgs append mode, sn: {sn}"
                    )
                    # Store current result in buffer with timing information
                    self.wpgs_buffer[sn] = {
                        "text": result,
                        "bg": start_ms,
                        "ed": end_ms,
                    }

                    # Concatenate results in sequence order
                    combined_result = ""
                    for i in sorted(self.wpgs_buffer.keys()):
                        combined_result += self.wpgs_buffer[i]["text"]

                    result_to_send = combined_result

                elif pgs == "rpl":  # Replace mode
                    self.ten_env.log_debug(
                        f"Xfyun ASR wpgs replace mode, sn: {sn}"
                    )
                    # Get replacement range
                    rg = result_data.get("rg", [])
                    if len(rg) >= 2:
                        replace_start = rg[0]
                        replace_end = rg[1]

                        # Clear buffer content to be replaced
                        keys_to_remove = []
                        for key in self.wpgs_buffer.keys():
                            if replace_start <= key <= replace_end:
                                keys_to_remove.append(key)

                        for key in keys_to_remove:
                            self.wpgs_buffer.pop(key, None)

                    # Store current result in buffer with timing information
                    self.wpgs_buffer[sn] = {
                        "text": result,
                        "bg": start_ms,
                        "ed": end_ms,
                    }

                    # Concatenate results in sequence order
                    combined_result = ""
                    for i in sorted(self.wpgs_buffer.keys()):
                        combined_result += self.wpgs_buffer[i]["text"]

                    result_to_send = combined_result
            else:
                # Non-wpgs mode, use current result directly
                result_to_send = result

            # Handle sentence final result
            if result_data.get("sub_end") is True:
                is_final = True
                self.ten_env.log_debug(
                    f"Xfyun ASR sub sentence end: {result_to_send}",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )
                self.wpgs_buffer.clear()

            if status == 2:
                is_final = True
                self.ten_env.log_debug(
                    f"Xfyun ASR complete result: {result_to_send}",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )
                # Clear buffer when recognition completes
                min_sn = (
                    min(self.wpgs_buffer.keys()) if self.wpgs_buffer else sn
                )
                max_sn = (
                    max(self.wpgs_buffer.keys()) if self.wpgs_buffer else sn
                )
                start_ms = (
                    self.wpgs_buffer[min_sn]["bg"]
                    if self.wpgs_buffer
                    else start_ms
                )
                duration_ms = (
                    self.wpgs_buffer[max_sn]["ed"] - start_ms
                    if self.wpgs_buffer
                    else duration_ms
                )
                self.wpgs_buffer.clear()

            self.ten_env.log_debug(
                f"Xfyun ASR result: {result_to_send}, status: {status}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            # If no valid timestamps, use timeline to estimate
            actual_start_ms = int(
                self.audio_timeline.get_audio_duration_before_time(start_ms)
                + self.sent_user_audio_duration_ms_before_last_reset
            )

            # Process ASR result
            if self.config is not None:
                if result_to_send != "":
                    await self._handle_asr_result(
                        text=result_to_send,
                        final=is_final,
                        start_ms=actual_start_ms,
                        duration_ms=duration_ms,
                        language=self.config.normalized_language,
                    )

            else:
                self.ten_env.log_error(
                    "Cannot handle ASR result: config is None"
                )

            if status == 2:
                if self.recognition:
                    await self.recognition.close()

        except Exception as e:
            self.ten_env.log_error(f"Error processing Xfyun ASR result: {e}")

    @override
    async def on_error(
        self, error_msg: str, error_code: Optional[int] = None
    ) -> None:
        """Handle error callback"""
        self.ten_env.log_error(
            f"vendor_error: code: {error_code}, reason: {error_msg}",
            category=LOG_CATEGORY_VENDOR,
        )

        # Send error information
        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=error_msg,
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(error_code) if error_code else "unknown",
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

        # Clear WPGS status variables
        self.wpgs_buffer.clear()

        if not self.stopped:
            self.ten_env.log_warn(
                "Xfyun ASR connection closed unexpectedly. Reconnecting..."
            )
            await self._handle_reconnect()

    @override
    async def finalize(self, session_id: str | None) -> None:
        """Finalize recognition"""
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        self.ten_env.log_debug(
            f"Xfyun ASR finalize start at {self.last_finalize_timestamp}"
        )

        await self._handle_finalize_disconnect()

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
            await self.recognition.stop()
            self.ten_env.log_debug("Xfyun ASR finalize disconnect completed")

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
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
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
                f"Xfyun ASR finalize end at {timestamp}, latency: {latency}ms"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def stop_connection(self) -> None:
        """Stop ASR connection"""
        try:
            if self.recognition:
                await self.recognition.close()
                self.recognition = None
            self.ten_env.log_info("Xfyun ASR connection stopped")

        except Exception as e:
            self.ten_env.log_error(f"Error stopping Xfyun ASR connection: {e}")

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
            return False

        try:
            buf = frame.lock_buf()
            audio_data = bytes(buf)

            # Dump audio data
            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)

            # Send audio data to recognition service (which handles buffering and timeline internally)
            await self.recognition.send_audio_frame(audio_data)

            frame.unlock_buf(buf)
            return True

        except Exception as e:
            self.ten_env.log_error(f"Error sending audio to Xfyun ASR: {e}")
            frame.unlock_buf(buf)
            return False
