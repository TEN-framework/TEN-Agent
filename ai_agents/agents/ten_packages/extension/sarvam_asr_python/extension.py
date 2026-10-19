from datetime import datetime
import json
import os
import base64
import asyncio
from urllib.parse import urlencode
from typing import Any, Optional

import aiohttp
import numpy as np
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
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_VENDOR,
)
from ten_ai_base.dumper import Dumper
from .config import SarvamASRConfig
from .reconnect_manager import ReconnectManager


class SarvamASRExtension(AsyncASRBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.connected: bool = False
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.config: SarvamASRConfig | None = None
        self.audio_dumper: Dumper | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        self.reconnect_manager: ReconnectManager | None = None

        # Audio processing tasks
        self._audio_task: Optional[asyncio.Task] = None
        self._message_task: Optional[asyncio.Task] = None
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._speaking: bool = False

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None
        await self.stop_connection()

    @override
    def vendor(self) -> str:
        """Get the name of the ASR vendor."""
        return "sarvam"

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
            print(f"config_json: {config_json}")
            self.config = SarvamASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)
            ten_env.log_info(
                f"KEYPOINT vendor_config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            api_key = self.config.api_key or self.config.params.get(
                "api_key", ""
            )
            if not api_key:
                raise ValueError(
                    "Sarvam API key is required. Provide it in params.api_key or set SARVAM_ASR_KEY environment variable."
                )

            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
        except Exception as e:
            ten_env.log_error(f"invalid property: {e}")
            self.config = SarvamASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    def _build_websocket_url(self) -> str:
        """Build WebSocket URL with parameters."""
        assert self.config is not None
        ws_url = self.config.get_ws_url()

        params = {
            "language-code": self.config.language,
            "model": self.config.model,
            "vad_signals": "false",
        }

        return f"{ws_url}?{urlencode(params)}"

    async def _send_initial_config(self) -> None:
        """Send initial configuration message with prompt for saaras models."""
        assert self.config is not None
        assert self.ws is not None

        if self.config.model.startswith("saaras") and self.config.prompt:
            try:
                config_message = {
                    "prompt": self.config.prompt,
                    "type": "config",
                }
                await self.ws.send_str(json.dumps(config_message))
                self.ten_env.log_debug(
                    "Sent initial config for saaras model",
                    category=LOG_CATEGORY_VENDOR,
                )
            except Exception as e:
                self.ten_env.log_error(
                    f"Failed to send initial configuration: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )
                raise

    @override
    async def start_connection(self) -> None:
        assert self.config is not None
        self.ten_env.log_info("start_connection")

        try:
            await self.stop_connection()

            # Create aiohttp session if not exists
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()

            if self.audio_dumper:
                await self.audio_dumper.start()

            # Build WebSocket URL
            ws_url = self._build_websocket_url()
            # Get API key from config or params
            api_key = self.config.api_key or self.config.params.get(
                "api_key", ""
            )
            headers = {"api-subscription-key": api_key}

            self.ten_env.log_info(
                f"Connecting to Sarvam WebSocket: {ws_url}",
                category=LOG_CATEGORY_VENDOR,
            )

            # Connect to WebSocket
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                self.ws = await asyncio.wait_for(
                    self.session.ws_connect(
                        ws_url, headers=headers, timeout=timeout
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                self.ten_env.log_error("WebSocket connection timeout")
                raise
            except Exception as e:
                self.ten_env.log_error(f"WebSocket connection failed: {e}")
                raise

            self.connected = True
            self.sent_user_audio_duration_ms_before_last_reset += (
                self.audio_timeline.get_total_user_audio_duration()
            )
            self.audio_timeline.reset()

            # Send initial configuration for saaras models
            await self._send_initial_config()

            # Start message processing task
            self._message_task = asyncio.create_task(self._process_messages())

            self.ten_env.log_info(
                "start_connection completed",
                category=LOG_CATEGORY_VENDOR,
            )

            # Notify reconnect manager that connection is successful
            if self.reconnect_manager:
                self.reconnect_manager.mark_connection_successful()

        except Exception as e:
            self.ten_env.log_error(
                f"KEYPOINT start_connection failed: invalid vendor config: {e}"
            )
            self.connected = False
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(e),
                ),
            )
            asyncio.create_task(self._handle_reconnect())

    async def _process_messages(self) -> None:
        """Process incoming messages from the WebSocket."""
        assert self.ws is not None

        try:
            async for msg in self.ws:
                self.ten_env.log_info(
                    f"sarvam_asr_python: Received message: {msg.type} data: {msg.data}",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_message(data)
                    except json.JSONDecodeError as e:
                        self.ten_env.log_warn(
                            f"Invalid JSON received from WebSocket: {e}",
                            category=LOG_CATEGORY_VENDOR,
                        )
                        continue
                    except Exception as e:
                        self.ten_env.log_error(
                            f"Error processing WebSocket message: {e}",
                            category=LOG_CATEGORY_VENDOR,
                        )
                        raise

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    error_msg = f"WebSocket error: {self.ws.exception()}"
                    self.ten_env.log_error(
                        error_msg,
                        category=LOG_CATEGORY_VENDOR,
                    )
                    raise RuntimeError(error_msg)

                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    self.ten_env.log_info(
                        f"WebSocket closed: {msg.type}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    # WebSocket closed unexpectedly, trigger reconnection
                    if not self.stopped:
                        await self.send_asr_error(
                            ModuleError(
                                module=MODULE_NAME_ASR,
                                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                                message=f"WebSocket closed unexpectedly: {msg.type}",
                            ),
                        )
                        await self._handle_reconnect()
                    break

        except Exception as e:
            self.ten_env.log_error(
                f"Error in message processing loop: {e}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )
            if not self.stopped:
                # Send error before attempting reconnection
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message=f"WebSocket error, attempting reconnection: {str(e)}",
                    ),
                )
                await self._handle_reconnect()

    async def _handle_message(self, data: dict) -> None:
        """Handle different types of messages from Sarvam streaming API."""
        try:
            msg_type = data.get("type")
            if not msg_type:
                self.ten_env.log_warn(
                    "Received message without type field",
                    category=LOG_CATEGORY_VENDOR,
                )
                return

            if msg_type == "data":
                await self._handle_transcript_data(data)
            elif msg_type == "events":
                await self._handle_events(data)
            elif msg_type == "error":
                await self._handle_error_message(data)
            else:
                self.ten_env.log_debug(
                    f"Unknown message type: {msg_type}",
                    category=LOG_CATEGORY_VENDOR,
                )

        except Exception as e:
            self.ten_env.log_error(
                f"Unexpected error handling message: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise

    async def _handle_transcript_data(self, data: dict) -> None:
        """Handle transcription result messages."""
        transcript_data = data.get("data", {})
        transcript_text = transcript_data.get("transcript", "")
        language = transcript_data.get("language_code", "")

        if not transcript_text:
            self.ten_env.log_debug(
                "Received empty transcript",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        try:
            # Extract metrics if available
            metrics = transcript_data.get("metrics", {})
            audio_duration = metrics.get("audio_duration", 0.0)

            # Calculate timing
            # Get total audio duration sent so far (including before last reset)
            total_audio_sent_ms = (
                self.audio_timeline.get_total_user_audio_duration()
                + self.sent_user_audio_duration_ms_before_last_reset
            )
            duration_ms = (
                int(audio_duration * 1000) if audio_duration > 0 else 0
            )

            # Calculate start_ms: transcript corresponds to audio that was sent
            # Start is total audio sent minus the duration of this transcript
            start_ms = max(0, total_audio_sent_ms - duration_ms)

            # Create ASR result
            asr_result = ASRResult(
                text=transcript_text,
                final=True,  # Sarvam streaming API returns final transcripts
                start_ms=start_ms,
                duration_ms=duration_ms,
                language=language,
                words=[],
            )

            await self.send_asr_result(asr_result)
            await self._finalize_end()

            self.ten_env.log_debug(
                f"Transcript processed: {transcript_text[:50]}...",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

        except Exception as e:
            self.ten_env.log_error(
                f"Error processing transcript data: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise

    async def _handle_events(self, data: dict) -> None:
        """Handle VAD (Voice Activity Detection) events."""
        event_data = data.get("data", {})
        signal_type = event_data.get("signal_type")

        if not signal_type:
            self.ten_env.log_warn(
                "VAD event missing signal_type",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        self.ten_env.log_debug(
            f"Processing VAD event: {signal_type}",
            category=LOG_CATEGORY_VENDOR,
        )

        try:
            if signal_type == "START_SPEECH":
                if not self._speaking:
                    self._speaking = True

            elif signal_type == "END_SPEECH":
                if self._speaking:
                    self._speaking = False
            else:
                self.ten_env.log_debug(
                    f"Unknown VAD signal type: {signal_type}",
                    category=LOG_CATEGORY_VENDOR,
                )

        except Exception as e:
            self.ten_env.log_error(
                f"Error processing VAD event: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise

    async def _handle_error_message(self, data: dict) -> None:
        """Handle error messages from the API."""
        error_data = data.get("data", {})
        error_info = error_data.get("error", "Unknown error")
        error_code = error_data.get("code", "unknown")
        self.ten_env.log_error(
            f"API error - {error_data}",
            category=LOG_CATEGORY_VENDOR,
        )

        self.ten_env.log_error(
            f"API error received: {error_info} (code: {error_code})",
            category=LOG_CATEGORY_VENDOR,
        )

        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=str(error_info),
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(error_code),
                message=str(error_info),
            ),
        )

    async def _handle_reconnect(self):
        """
        Handle a single reconnection attempt using the ReconnectManager.
        Connection success is determined by the start_connection callback.
        """
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return

        # Check if we can still retry
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

        # Attempt a single reconnection
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

    @override
    async def finalize(self, session_id: str | None) -> None:
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        self.ten_env.log_info(
            f"vendor_cmd: finalize start at {self.last_finalize_timestamp}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self.send_flush()

    async def _finalize_end(self) -> None:
        """Handle finalize end logic."""
        if self.last_finalize_timestamp != 0:
            timestamp = int(datetime.now().timestamp() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_debug(
                f"KEYPOINT finalize end at {timestamp}, counter: {latency}"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def stop_connection(self) -> None:
        """Stop the Sarvam connection."""
        try:
            # Cancel tasks
            if self._message_task and not self._message_task.done():
                self._message_task.cancel()
                try:
                    await self._message_task
                except asyncio.CancelledError:
                    pass

            if self._audio_task and not self._audio_task.done():
                self._audio_task.cancel()
                try:
                    await self._audio_task
                except asyncio.CancelledError:
                    pass

            # Close WebSocket
            if self.ws and not self.ws.closed:
                await self.ws.close()
                self.ws = None

            # Close session
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

            self.connected = False
            self.ten_env.log_info("sarvam connection stopped")
        except Exception as e:
            self.ten_env.log_error(f"Error stopping sarvam connection: {e}")

    async def send_flush(self) -> None:
        try:
            flush_message = {"type": "flush"}
            await self.ws.send_str(json.dumps(flush_message))
            self.ten_env.log_debug("sarvam flush sent")
        except Exception as e:
            self.ten_env.log_error(f"Error sending sarvam flush: {e}")
            if not self.stopped:
                await self._handle_reconnect()

    @override
    def is_connected(self) -> bool:
        return self.connected and self.ws is not None and not self.ws.closed

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return self.config.sample_rate

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        assert self.config is not None
        assert self.ws is not None

        if not self.is_connected():
            self.ten_env.log_error("Sarvam connection is not established")
            return False

        buf = frame.lock_buf()
        try:
            audio_data = bytes(buf)

            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)

            self.audio_timeline.add_user_audio(
                int(len(buf) / (self.config.sample_rate / 1000 * 2))
            )

            # Convert audio to base64 and send
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            base64_audio = base64.b64encode(audio_array.tobytes()).decode(
                "utf-8"
            )

            audio_message = {
                "audio": {
                    "data": base64_audio,
                    "encoding": "audio/wav",
                    "sample_rate": self.config.sample_rate,
                }
            }

            await self.ws.send_str(json.dumps(audio_message))
            return True

        except Exception as e:
            self.ten_env.log_error(f"Error sending audio: {e}")
            if not self.stopped:
                await self._handle_reconnect()
            return False
        finally:
            frame.unlock_buf(buf)
