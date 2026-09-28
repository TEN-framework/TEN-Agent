import asyncio
import os
from datetime import datetime
from typing import Any
from typing_extensions import override
from ten_ai_base.asr import (
    AsyncASRBaseExtension,
    ASRBufferConfig,
    ASRBufferConfigModeDiscard,
    ASRResult,
)
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import (
    ModuleType,
    ModuleError,
    ModuleErrorVendorInfo,
    ModuleErrorCode,
)

from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_KEY_POINT,
)

from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
)
from .bytedance_asr import AsrWsClient
from .config import BytedanceASRConfig
from .const import (
    DUMP_FILE_NAME,
    BYTEDANCE_ERROR_CODES,
    RECONNECTABLE_ERROR_CODES,
    FATAL_ERROR_CODES,
)
from .audio_buffer_manager import AudioBufferManager


class BytedanceASRExtension(AsyncASRBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)

        # Connection state
        self.connected: bool = False
        self.client: AsrWsClient | None = None
        self.config: BytedanceASRConfig | None = None
        self.last_finalize_timestamp: int = 0
        self.audio_dumper: Dumper | None = None
        self.ten_env: AsyncTenEnv = None  # type: ignore

        # Reconnection parameters (will be set from config)
        self.max_retries: int = 5
        self.base_delay: float = 0.3
        self.attempts: int = 0
        self.stopped: bool = False  # Whether extension is stopped
        self.last_fatal_error: int | None = (
            None  # Track fatal errors to prevent unnecessary reconnection
        )
        self._reconnecting: bool = (
            False  # Reconnection lock to prevent concurrent reconnections
        )

        # Audio buffer manager for controlling audio chunk size
        self.audio_buffer_manager: AudioBufferManager | None = None

        # State tracking for logging
        self._last_logged_state: bool | None = None

        # Session tracking
        self.session_id: str | None = None
        self.sent_user_audio_duration_ms_before_last_reset = 0

    @override
    def vendor(self) -> str:
        """Get the name of the ASR vendor."""
        return "bytedance"

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        self.ten_env = ten_env  # Store ten_env reference for reconnection

        config_json, _ = await ten_env.get_property_to_json()

        try:
            self.config = BytedanceASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)
            # Ensure user field exists in params with required uid field
            default_uid = getattr(self.config, "uid", "default_user")
            self.config.ensure_user_field(default_uid)
            # Ensure request field exists in params with required sequence field
            self.config.ensure_request_field()
            # Ensure audio field exists in params with required format field
            self.config.ensure_audio_field()
            ten_env.log_info(
                f"config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            # Set reconnection parameters from config
            self.max_retries = self.config.max_retries
            self.base_delay = self.config.base_delay

            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
                await self.audio_dumper.start()

            self.audio_timeline.reset()
            self.last_finalize_timestamp = 0
        except Exception as e:
            ten_env.log_error(f"invalid property: {e}")
            self.config = BytedanceASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=ModuleType.ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
                ModuleErrorVendorInfo(
                    vendor="bytedance",
                    code="CONFIG_ERROR",
                    message=f"Configuration validation failed: {str(e)}",
                ),
            )

    async def _handle_reconnect(self, ten_env: Any | None = None) -> None:
        """Handle reconnection logic with exponential backoff strategy."""
        # Use provided ten_env or stored ten_env
        env = ten_env or getattr(self, "ten_env", None)
        if not env:
            # Unable to log since no ten_env is available
            return

        # Check if already reconnecting to prevent concurrent reconnections
        if self._reconnecting:
            env.log_info(
                "Reconnection already in progress, skipping duplicate request"
            )
            return

        if self.attempts >= self.max_retries:
            env.log_error(
                f"Max retries ({self.max_retries}) reached, stopping reconnection attempts"
            )
            return

        # Set reconnection lock
        self._reconnecting = True

        try:
            # Increment retry count and calculate exponential backoff delay
            self.attempts += 1
            delay = self.base_delay * (2 ** (self.attempts - 1))

            env.log_info(f"Reconnecting... Attempt {self.attempts}")
            await asyncio.sleep(delay)

            try:
                await self.stop_connection()
                await self.start_connection()
            except Exception as e:
                env.log_error(f"Reconnection failed: {e}")
                if self.attempts < self.max_retries and not self.stopped:
                    # Don't create new task, just continue with current one
                    await self._handle_reconnect(env)
                else:
                    env.log_error("All retry attempts failed")
        finally:
            # Always release reconnection lock
            self._reconnecting = False

    async def on_finalize_complete_callback(self) -> None:
        """Callback function when ASR finalize is completed."""
        try:
            await self.send_asr_finalize_end()
        except Exception as e:
            self.ten_env.log_error(
                f"Error sending asr_finalize_end signal: {e}"
            )

    @override
    async def start_connection(self) -> None:
        if not self.config:
            config_json, _ = await self.ten_env.get_property_to_json("")
            self.config = BytedanceASRConfig.model_validate_json(config_json)

            if self.config.auth_method == "api_key":
                if not self.config.api_key:
                    raise ValueError("api_key is required")
            elif self.config.auth_method == "token":
                if not self.config.appid:
                    raise ValueError("appid is required")
                if not self.config.token:
                    raise ValueError("token is required")

        async def on_message(result):
            if (
                not result
                or "text" not in result[0]
                or "utterances" not in result[0]
                or not result[0][
                    "utterances"
                ]  # Check if utterances list is not empty
            ):
                return

            sentence = result[0]["text"]
            start_ms = result[0]["utterances"][0].get("start_time", 0)
            end_ms = result[0]["utterances"][0].get("end_time", 0)
            language = self.config.language if self.config else "zh-CN"

            self.ten_env.log_debug(
                f"vendor_result: on_recognized: {sentence}, language: {language}, full_json: {result[0]}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            if len(sentence) == 0:
                return

            is_definite = result[0]["utterances"][0].get(
                "definite", False
            )  # Use get to avoid KeyError

            # Received normal message, consider connection successful, reset retry count
            if self.attempts > 0:
                self.attempts = 0

            # For Bytedance ASR, set final=True when definite=True
            # This ensures asr_aggregator can process the results
            is_final = is_definite

            actual_start_ms = int(
                self.audio_timeline.get_audio_duration_before_time(start_ms)
                + self.sent_user_audio_duration_ms_before_last_reset
            )

            # Convert to ASRResult
            asr_result = ASRResult(
                text=sentence,
                final=is_final,
                start_ms=actual_start_ms,
                duration_ms=end_ms - start_ms,
                language=language,
                words=[],
            )

            await self.send_asr_result(asr_result)

        async def on_error(error_code: int, error_msg: str):
            """Callback function to handle ASR error codes"""
            self.ten_env.log_error(
                f"vendor_error: code: {error_code}, reason: {error_msg}",
                category=LOG_CATEGORY_VENDOR,
            )
            error_message = ModuleError(
                module=ModuleType.ASR,
                code=int(ModuleErrorCode.NON_FATAL_ERROR),
                message=error_msg,
            )

            # Map error code to descriptive name using constants
            error_code_name = BYTEDANCE_ERROR_CODES.get(
                error_code, f"UNKNOWN_ERROR_{error_code}"
            )

            # Create vendor_info with Bytedance-specific error information
            vendor_info = ModuleErrorVendorInfo(
                vendor="bytedance",
                code=error_code_name,
                message=f"Bytedance ASR error {error_code}: {error_msg}",
            )

            await self.send_asr_error(error_message, vendor_info)

            # Check if this is a fatal error that shouldn't trigger reconnection
            if error_code in FATAL_ERROR_CODES:
                self.last_fatal_error = error_code

                self.ten_env.log_info(
                    f"=== Received fatal error code {error_code}, closing connection to prevent further errors ==="
                )
                # Close connection immediately for fatal errors to prevent continuous error logs
                await self.stop_connection()
                return

            # Special handling for connection errors (2001) - check if due to previous fatal error
            if error_code == 2001 and self.last_fatal_error:
                self.ten_env.log_info(
                    f"=== Connection closed due to previous fatal error {self.last_fatal_error}, skipping reconnection ==="
                )
                self.last_fatal_error = None  # Clear the flag
                return  # Don't proceed with reconnection logic

            # Trigger reconnection mechanism for reconnectable error codes
            if error_code in RECONNECTABLE_ERROR_CODES and not self.stopped:
                self.ten_env.log_info(
                    f"=== Received reconnectable error code {error_code}, triggering reconnection === Current retry count: {self.attempts}"
                )
                # Use create_task to avoid blocking, but _handle_reconnect will check for concurrent calls
                asyncio.create_task(self._handle_reconnect(self.ten_env))
            # Reset retry count for success codes and non-fatal errors
            elif error_code in [1000, 0] or (
                error_code not in RECONNECTABLE_ERROR_CODES
                and error_code < 2000
            ):
                if self.attempts > 0:
                    self.ten_env.log_info(
                        f"=== Received success/non-fatal error code ({error_code}), resetting retry count ==="
                    )
                    self.attempts = 0
                # Clear fatal error flag on success
                self.last_fatal_error = None
            else:
                # Other unknown error codes, log but don't handle
                self.ten_env.log_info(
                    f"=== Received unknown error code ({error_code}), no action taken ==="
                )

        try:
            self.client = AsrWsClient(
                ten_env=self.ten_env,
                cluster=self.config.cluster,
                appid=self.config.appid,
                token=self.config.token,
                ws_url=self.config.api_url,
                auth_method=self.config.auth_method,
                api_key=self.config.api_key,
                silence_pkg_length_ms=self.config.silence_pkg_length_ms,
                handle_received_message=on_message,
                on_finalize_complete=self.on_finalize_complete_callback,
                on_error=on_error,
                pass_through_params=self.config.params,  # Support pass-through parameters
            )

            # connect to websocket
            await self.client.start()
            self.connected = True
            # Clear fatal error flag on successful connection
            self.last_fatal_error = None
            self.sent_user_audio_duration_ms_before_last_reset += (
                self.audio_timeline.get_total_user_audio_duration()
            )
            self.audio_timeline.reset()

            # Initialize audio buffer manager with balanced threshold for optimal performance
            # 4800 bytes = 150ms at 16kHz (16000 * 2 bytes per sample * 0.15s)
            # This provides a good balance between latency and ASR efficiency
            if self.audio_buffer_manager is None:
                self.audio_buffer_manager = AudioBufferManager(
                    threshold_bytes=6400, logger=self.ten_env
                )
        except Exception as e:
            self.ten_env.log_error(f"Failed to start Bytedance ASR client: {e}")
            error_message = ModuleError(
                module=ModuleType.ASR,
                code=int(ModuleErrorCode.FATAL_ERROR),
                message=str(e),
            )

            vendor_info = ModuleErrorVendorInfo(
                vendor="bytedance",
                code="CONNECTION_ERROR",
                message=f"Failed to establish WebSocket connection: {str(e)}",
            )

            await self.send_asr_error(error_message, vendor_info)
            # Trigger reconnection on connection failure
            if not self.stopped:
                asyncio.create_task(self._handle_reconnect(self.ten_env))

    @override
    async def stop_connection(self) -> None:
        self.ten_env.log_info("stop_connection() called")
        # Don't set self.stopped = True here, as it prevents reconnection
        if self.client:
            self.ten_env.log_info("Stopping client connection")
            await self.client.finish()
            self.client = None
            self.connected = False

        # Stop audio dumper when connection stops
        if self.audio_dumper:
            try:
                await self.audio_dumper.stop()
            except Exception as e:
                self.ten_env.log_error(f"Error stopping audio dumper: {e}")
            finally:
                self.audio_dumper = None

        # Reset reconnection state when stopping
        self.attempts = 0
        self.last_fatal_error = None

        # Reset audio buffer manager
        # if self.audio_buffer_manager:
        #     self.audio_buffer_manager.reset()
        #     self.audio_buffer_manager = None

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        # Check if connection is closed due to fatal error
        if self.last_fatal_error:
            return False

        self.session_id = session_id
        buf = frame.lock_buf()
        try:
            # Log audio frame details for debugging
            audio_data = bytes(buf)
            # Note: Removed silent audio detection to ensure all audio data is sent to ASR service
            # This helps maintain audio continuity and improves ASR accuracy

            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)

            self.audio_timeline.add_user_audio(
                int(len(buf) / (self.input_audio_sample_rate() / 1000 * 2))
            )

            # Check connection status before sending
            if not self.connected or not self.client:
                # Try to reconnect if connection is lost
                self.ten_env.log_info(
                    "Connection lost, attempting to reconnect..."
                )
                try:
                    await self.start_connection()
                    self.ten_env.log_info("Reconnection successful")
                except Exception as e:
                    self.ten_env.log_error(f"Reconnection failed: {e}")
                    return False

            # Check WebSocket connection state
            if hasattr(self.client, "websocket") and self.client.websocket:
                websocket_state = self.client.websocket.state.name
                if websocket_state != "OPEN":
                    # Try to reconnect if WebSocket is not in OPEN state
                    self.ten_env.log_info(
                        f"WebSocket not in OPEN state: {websocket_state}, attempting to reconnect..."
                    )
                    try:
                        await self.start_connection()
                        self.ten_env.log_info(
                            "WebSocket reconnection successful"
                        )
                    except Exception as e:
                        self.ten_env.log_error(
                            f"WebSocket reconnection failed: {e}"
                        )
                        return False
            else:
                # No WebSocket, try to reconnect
                self.ten_env.log_info(
                    "No WebSocket available, attempting to reconnect..."
                )
                try:
                    await self.start_connection()
                    self.ten_env.log_info("Reconnection successful")
                except Exception as e:
                    self.ten_env.log_error(f"Reconnection failed: {e}")
                    return False

            # Note: No finalize state management here to avoid interfering with ASR service
            # Let the ASR service handle finalize state naturally

            # Use audio buffer manager with smaller threshold for better responsiveness
            if self.audio_buffer_manager and self.client:
                await self.audio_buffer_manager.push_audio(
                    audio_data, self.client.send
                )
                return True
            elif self.client:
                # Fallback to direct send if buffer manager not available
                await self.client.send(audio_data)
                return True
            else:
                return False
        finally:
            frame.unlock_buf(buf)

    async def finalize(self, session_id: str | None) -> None:
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)

        self.ten_env.log_info(f"Finalize called for session_id: {session_id}")

        if not self.client or not self.connected:
            self.ten_env.log_warn("Cannot finalize: client not connected")
            return

        try:
            # Check if client is available before finalizing
            if not self.client:
                self.ten_env.log_warn("Client is None, cannot finalize")
                return

            # First, flush any remaining audio data in buffer before sending NEG_SEQUENCE
            if self.audio_buffer_manager:
                buffer_size = self.audio_buffer_manager.get_buffer_size()
                if buffer_size > 0:
                    self.ten_env.log_info(
                        f"Flushing remaining audio data before finalize (buffer_size: {buffer_size} bytes)"
                    )
                    # Flush remaining audio data to ensure all audio is sent before NEG_SEQUENCE
                    await self.audio_buffer_manager.flush(self.client.send)

            # Call the client's finalize method to send NEG_SEQUENCE flag
            self.ten_env.log_info(
                "Calling client finalize method to send NEG_SEQUENCE"
            )
            await self.client.finalize()

            # add silence audio to audio timeline
            # Use silence_pkg_length_ms from config (distinct from volcano ASR vad_silence_time)
            silence_pkg_length_ms = self.config.silence_pkg_length_ms
            self.audio_timeline.add_silence_audio(int(silence_pkg_length_ms))

            # Use timeout from configuration
            finalize_timeout = self.config.finalize_timeout

            # Wait for final result or timeout
            finalize_success = await self.client.wait_for_finalize(
                finalize_timeout
            )

            if finalize_success:
                self.ten_env.log_info("ASR finalize completed successfully")
            else:
                self.ten_env.log_warn(
                    f"ASR finalize timeout after {finalize_timeout}s, proceeding with cleanup"
                )

        except Exception as e:
            self.ten_env.log_error(f"Error during finalize: {e}")
        finally:
            # Don't close connection after finalize - keep it alive for next session
            # This allows the same connection to handle multiple speech recognition sessions
            self.ten_env.log_info(
                "Finalize completed, keeping connection alive for next session"
            )
            # Note: Connection will be closed only when the extension is stopped or on fatal error

    @override
    def is_connected(self) -> bool:
        # Check both connection flag and WebSocket state
        websocket_connected = (
            self.client
            and hasattr(self.client, "websocket")
            and self.client.websocket
            and self.client.websocket.state.name == "OPEN"
        )

        current_state = bool(self.connected and websocket_connected)

        # Only log when state changes to reduce log noise
        if self.ten_env and (
            not hasattr(self, "_last_logged_state")
            or self._last_logged_state != current_state
        ):
            self.ten_env.log_info(
                f"vendor_status_changed: self.connected={self.connected}, websocket_connected={websocket_connected}, session_id: {self.session_id}",
                category=LOG_CATEGORY_VENDOR,
            )
            self._last_logged_state = current_state

        return bool(current_state)

    @override
    def input_audio_sample_rate(self) -> int:
        return 16000

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeDiscard()
