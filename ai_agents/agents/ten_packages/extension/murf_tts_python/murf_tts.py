import asyncio
import json
import base64
from datetime import datetime
from typing import Any

import websockets
from websockets.legacy.client import WebSocketClientProtocol

from ten_ai_base.message import (
    ModuleErrorVendorInfo,
    ModuleVendorException,
)
from .config import MurfTTSConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.struct import TTSTextInput

MAX_RETRY_TIMES_FOR_TRANSPORT = 5
WS_MAX_MESSAGE_BYTES = 100_000_000
TEXT_QUEUE_MAXSIZE = 100

EVENT_TTS_RESPONSE = 1
EVENT_TTS_END = 2
EVENT_TTS_TTFB_METRIC = 3
EVENT_TTS_ERROR = 4

VOICE_CONFIG_PARAM_KEYS = (
    "voice_id",
    "voiceId",
    "locale",
    "multiNativeLocale",
    "multi_native_locale",
    "style",
    "rate",
    "pitch",
    "variation",
    "pronunciationDictionary",
    "pronunciation_dictionary",
)

ADVANCED_SETTINGS_PARAM_KEYS = (
    "min_buffer_size",
    "max_buffer_delay_in_ms",
)


class MurfTTSynthesizer:

    def __init__(
        self,
        config: MurfTTSConfig,
        ten_env: AsyncTenEnv,
        vendor: str,
        response_msgs: asyncio.Queue[tuple[int, bytes | int]],
    ):
        self.config = config
        self.api_key = config.api_key
        self.base_url = config.base_url
        self.ws: WebSocketClientProtocol | None = None
        self.ten_env: AsyncTenEnv = ten_env
        self.vendor = vendor
        self.response_msgs = response_msgs

        # Connection management
        self._session_closing = False
        self.first_chunk_of_connection = True
        self._connect_exp_cnt = 0
        self._max_retries_exceeded = False
        self.websocket_task = None
        self.channel_tasks = []
        self.latest_context_id: str | None = None
        # map for request id to first chunk sent time
        self.request_first_chunk_sent_time: dict[str, tuple[datetime, bool]] = (
            {}
        )  # request_id -> first chunk sent time with mark done flag

        # Queue for pending text to be sent
        self.text_input_queue = asyncio.Queue[TTSTextInput](
            maxsize=TEXT_QUEUE_MAXSIZE
        )

        # Event synchronization
        self._receive_ready_event = asyncio.Event()
        self.cleared_context_ids: set[str] = (
            set()
        )  # Context IDs that have been cleared

        # Start websocket connection monitoring
        self.websocket_task = asyncio.create_task(self._process_websocket())

    def _build_websocket_url(self) -> str:
        """Build MURF TTS WebSocket URL with query parameters"""
        sample_rate = self.config.sample_rate
        audio_format = self.config.audio_format
        model = self.config.model

        # Build query string
        query_string = (
            f"model={model}&sample_rate={sample_rate}&format={audio_format}"
        )
        return f"{self.base_url}?{query_string}"

    def _build_websocket_headers(self) -> dict[str, str]:
        """Build WebSocket headers for authentication"""
        return {"api-key": self.api_key}

    def _format_exception(self, exp: Exception) -> str:
        return f"{type(exp).__name__}: {exp}"

    def _process_ws_exception(self, exp) -> None | Exception:
        """Handle websocket connection exceptions and decide whether to reconnect"""
        self.ten_env.log_warn(
            f"Websocket internal error during connecting: {self._format_exception(exp)}."
        )
        self._connect_exp_cnt += 1
        if self._connect_exp_cnt > MAX_RETRY_TIMES_FOR_TRANSPORT:
            self._max_retries_exceeded = True
            self._session_closing = True
            self.ten_env.log_error(
                f"Max retries ({MAX_RETRY_TIMES_FOR_TRANSPORT}) exceeded: {self._format_exception(exp)}"
            )
            return exp
        return None  # Return None to continue reconnection

    async def _process_websocket(self) -> None:
        """Main websocket connection monitoring and reconnection logic"""
        try:
            self.ten_env.log_info(
                "Starting MURF TTS websocket connection process"
            )

            # Use websockets.connect's automatic reconnection mechanism
            async for ws in websockets.connect(
                uri=self._build_websocket_url(),
                max_size=WS_MAX_MESSAGE_BYTES,
                compression=None,
                process_exception=self._process_ws_exception,
                additional_headers=self._build_websocket_headers(),
            ):
                self.ws = ws
                self.first_chunk_of_connection = True
                try:
                    await self._send_voice_config(ws)
                    await self._send_advanced_settings(ws)
                    self.ten_env.log_info(
                        "MURF TTS websocket connected successfully"
                    )
                    if self._session_closing:
                        self.ten_env.log_info("Session is closing, break.")
                        return

                    # Start send and receive tasks
                    self.channel_tasks = [
                        asyncio.create_task(self._send_loop(ws)),
                        asyncio.create_task(self._receive_loop(ws)),
                    ]

                    # Wait for receive loop to be ready
                    await self._receive_ready_event.wait()

                    await self._await_channel_tasks()

                except websockets.ConnectionClosed as e:
                    self.ten_env.log_info(
                        f"MURF TTS websocket connection closed: {e}."
                    )
                    if self._max_retries_exceeded:
                        self.ten_env.log_error(
                            "Max retries exceeded, stop reconnecting."
                        )
                        return
                    if not self._session_closing:
                        self.ten_env.log_warn(
                            "MURF TTS websocket connection closed, will reconnect."
                        )

                        # Cancel all channel tasks
                        for task in self.channel_tasks:
                            task.cancel()
                        await self._await_channel_tasks()

                        # Signal error if there was an active request
                        if self.latest_context_id and self.response_msgs:
                            self.ten_env.log_warn(
                                f"Active request {self.latest_context_id} lost due to connection close, signaling error"
                            )
                            await self.response_msgs.put(
                                (
                                    EVENT_TTS_ERROR,
                                    f"Connection closed: {e}".encode(),
                                )
                            )
                            self.latest_context_id = None

                        # Reset event states
                        self._receive_ready_event.clear()

                        # Reset connection exception counter
                        self._connect_exp_cnt = 0
                        continue

            if self._max_retries_exceeded:
                self.ten_env.log_error(
                    "Max retries exceeded, websocket loop stopped."
                )
                return

        except Exception as e:
            self.ten_env.log_error(
                f"Exception in MURF TTS websocket process: {self._format_exception(e)}"
            )
        finally:
            if self.ws:
                await self.ws.close()
            self.ten_env.log_info(
                "MURF TTS websocket connection process ended."
            )

    def _get_voice_config_from_params(self) -> dict[str, Any]:
        params = self.config.params
        voice_config: dict[str, Any] = {}
        if not params:
            return voice_config

        for key in VOICE_CONFIG_PARAM_KEYS:
            value = params.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value:
                continue
            voice_config[key] = value

        return voice_config

    def _get_advanced_settings_from_params(self) -> dict[str, Any]:
        params = self.config.params
        advanced_settings: dict[str, Any] = {}
        if not params:
            return advanced_settings

        for key in ADVANCED_SETTINGS_PARAM_KEYS:
            value = params.get(key)
            if value is None:
                continue
            advanced_settings[key] = value

        return advanced_settings

    async def _send_voice_config(self, ws: WebSocketClientProtocol) -> None:
        """Send voice config to MURF TTS"""
        voice_config = self._get_voice_config_from_params()
        self.ten_env.log_info(
            f"KEYPOINT Sending voice config to MURF TTS: {voice_config}"
        )
        message = {"voice_config": voice_config}
        message_json = json.dumps(message)
        await ws.send(message_json)

    async def _send_advanced_settings(
        self, ws: WebSocketClientProtocol
    ) -> None:
        """Send advanced settings to MURF TTS once per websocket connection."""
        advanced_settings = self._get_advanced_settings_from_params()
        if not advanced_settings:
            return

        self.ten_env.log_info(
            f"KEYPOINT Sending advanced settings to MURF TTS: {advanced_settings}"
        )
        message = advanced_settings
        message_json = json.dumps(message)
        await ws.send(message_json)

    def _clear_synthesizer(self, context_id: str) -> None:
        """Clear MURF TTS synthesizer for context ID"""
        self.cleared_context_ids.add(context_id)
        self.request_first_chunk_sent_time.pop(context_id, None)
        # Send clear command to MURF TTS
        asyncio.create_task(self._send_clear_command(context_id))

    def clear_synthesizer(self, context_id: str) -> None:
        """Public wrapper to clear synthesizer for context ID"""
        self._clear_synthesizer(context_id)

    def clear_text_queue(self) -> None:
        """Public wrapper to clear pending text queue"""
        self._clear_text_queue()

    async def _send_clear_command(self, context_id: str) -> None:
        """Send clear command to MURF TTS"""
        try:
            if self.ws:
                message = {"context_id": context_id, "clear": True}
                message_json = json.dumps(message)
                await self.ws.send(message_json)
                self.ten_env.log_debug(
                    f"KEYPOINT Sent clear command to MURF TTS: {message}"
                )
        except Exception as e:
            self.ten_env.log_error(
                f"Exception in MURF TTS send_clear_command: {self._format_exception(e)}"
            )
            raise e

    async def _await_channel_tasks(self) -> None:
        """Wait for channel tasks to complete"""
        if not self.channel_tasks:
            return

        (done, pending) = await asyncio.wait(
            self.channel_tasks,
            return_when=asyncio.FIRST_EXCEPTION,
        )
        self.ten_env.log_debug("MURF TTS channel tasks finished.")

        self.channel_tasks.clear()

        # Cancel remaining tasks
        for task in pending:
            task.cancel()

        # Check for exceptions
        for task in done:
            exp = task.exception()
            if exp and not isinstance(exp, asyncio.CancelledError):
                raise exp

    async def _send_loop(self, ws: WebSocketClientProtocol) -> None:
        """Text sending loop for MURF TTS"""
        try:
            while not self._session_closing:
                # Get text to send from queue
                tts_text_input = await self.text_input_queue.get()
                if tts_text_input is None:  # End signal
                    break

                context_id = f"{tts_text_input.request_id}"
                is_last = tts_text_input.text_input_end
                self.latest_context_id = context_id

                # Send text message
                await self._send_text_internal(
                    ws, tts_text_input.text, context_id, is_last
                )
        except Exception as e:
            self.ten_env.log_error(f"Exception in MURF TTS send_loop: {e}")
            raise e

    async def _receive_loop(self, ws: WebSocketClientProtocol) -> None:
        """Message receiving loop for MURF TTS"""
        try:
            # Mark receive loop as ready
            self._receive_ready_event.set()

            async for message in ws:
                if self._session_closing:
                    self.ten_env.log_debug(
                        "Session is closing, break receive loop."
                    )
                    break

                try:
                    await self._handle_server_message(message)
                except ModuleVendorException as e:
                    # Vendor errors should be propagated to the extension
                    self.ten_env.log_error(
                        f"Vendor error handling MURF TTS server message: {self._format_exception(e)}"
                    )
                    if self.response_msgs:
                        await self.response_msgs.put(
                            (EVENT_TTS_ERROR, str(e.error.message).encode())
                        )
                except Exception as e:
                    self.ten_env.log_error(
                        f"Error handling MURF TTS server message: {self._format_exception(e)}"
                    )

        except asyncio.CancelledError:
            self.ten_env.log_debug("MURF TTS receive loop cancelled")
            raise
        except Exception as e:
            self.ten_env.log_error(
                f"Exception in MURF TTS receive_loop: {self._format_exception(e)}"
            )
            raise e

    async def _handle_server_message(self, message):
        """Handle MURF TTS server responses"""
        try:
            data = json.loads(message)
            is_final = data.get("final", False)
            context_id = data.get("context_id", None)

            if "audio" in data:
                audio_data = base64.b64decode(data["audio"])
                # First packet may contain a 44-byte header
                if self.first_chunk_of_connection:
                    if len(audio_data) > 44:
                        audio_data = audio_data[44:]
                    else:
                        self.ten_env.log_warn(
                            "First audio chunk too small to strip header; passing through."
                        )
                    self.first_chunk_of_connection = False
                # if context is in cleared context ids then skip
                if context_id in self.cleared_context_ids:
                    self.ten_env.log_debug(
                        f"Context ID {context_id} is in cleared context IDs, skipping"
                    )
                else:
                    self.ten_env.log_debug(
                        f"Received audio chunk, context_id: {context_id}, length: {len(audio_data)}"
                    )
                    if self.response_msgs:
                        await self._check_for_ttfb(
                            context_id
                        )  # check for TTFB metric
                        await self.response_msgs.put(
                            (EVENT_TTS_RESPONSE, audio_data)
                        )  # send the audio data to the response messages queue
            if is_final:
                # if context is in cleared context ids then skip
                if (
                    context_id
                    and context_id == self.latest_context_id
                    and self.response_msgs
                ):
                    await self.response_msgs.put((EVENT_TTS_END, b""))
                    self.request_first_chunk_sent_time.pop(context_id, None)
                else:
                    self.ten_env.log_debug(
                        f"Context ID {context_id} is not the latest context ID, or response messages is not ready, skipping"
                    )
            if "error" in data:
                error_message = data.get("error", "Unknown error")
                raise ModuleVendorException(
                    ModuleErrorVendorInfo(
                        vendor=self.vendor,
                        code="MURF_TTS_ERROR",
                        message=error_message,
                    )
                )

        except ModuleVendorException:
            raise
        except Exception as e:
            self.ten_env.log_error(
                f"Failed to parse MURF TTS message: {self._format_exception(e)}"
            )
            raise RuntimeError(
                f"Failed to parse MURF TTS message: {self._format_exception(e)}"
            ) from e

    async def _check_for_ttfb(self, context_id: str) -> None:
        """Check for TTFB metric"""
        if context_id in self.request_first_chunk_sent_time:
            first_chunk_sent_time, ttfb_sent = (
                self.request_first_chunk_sent_time[context_id]
            )
            if not ttfb_sent:
                ttfb_ms = int(
                    (datetime.now() - first_chunk_sent_time).total_seconds()
                    * 1000
                )
                self.request_first_chunk_sent_time[context_id] = (
                    first_chunk_sent_time,
                    True,
                )  # update the first chunk sent time and mark done flag to true
                self.ten_env.log_debug(
                    f"KEYPOINT TTFB metric sent: {ttfb_ms}ms"
                )
                await self.response_msgs.put(
                    (EVENT_TTS_TTFB_METRIC, ttfb_ms)
                )  # send the TTFB metric to the response messages queue

    def _add_first_chunk_sent_time(self, context_id: str) -> None:
        """Add first chunk sent time to request first chunk sent time map"""
        if (
            context_id not in self.request_first_chunk_sent_time
        ):  # if first chunk is not sent yet then set the first chunk sent time
            self.request_first_chunk_sent_time[context_id] = (
                datetime.now(),
                False,
            )
            self.ten_env.log_debug(
                f"KEYPOINT First chunk sent time for request ID {context_id} set to {self.request_first_chunk_sent_time[context_id]}"
            )

    async def send_text(self, t: TTSTextInput):
        await self.text_input_queue.put(t)

    async def _send_text_internal(
        self,
        ws: WebSocketClientProtocol,
        text: str,
        context_id: str,
        is_last: bool = False,
    ):
        """Internal text sending implementation for MURF TTS"""

        voice_config = self._get_voice_config_from_params()
        # Create MURF TTS text message
        message = {
            "text": text,
            "context_id": context_id,
            "end": is_last,
            "voice_config": voice_config,
        }
        message_json = json.dumps(message)
        self.ten_env.log_debug(
            f"KEYPOINT Sending text to MURF TTS: {message_json}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )
        await ws.send(message_json)
        self._add_first_chunk_sent_time(
            context_id
        )  # add first chunk sent time to request first chunk sent time map

    def _clear_text_queue(self) -> None:
        """Clear all queues to prevent old data from being processed"""
        while not self.text_input_queue.empty():
            try:
                self.text_input_queue.get_nowait()  # get the text input from the queue
            except asyncio.QueueEmpty:
                break  # if the queue is empty then break

    async def close(self):
        self.ten_env.log_info("Closing MurfTTSynthesizer")

        # Set closing flag
        self._session_closing = True

        # Send end signal to text queue
        await self.text_input_queue.put(None)

        # Cancel websocket task
        if self.websocket_task:
            self.websocket_task.cancel()
            try:
                await self.websocket_task
            except asyncio.CancelledError:
                pass

        # Close websocket connection
        if self.ws:
            await self.ws.close()
            self.ws = None
        self.response_msgs: asyncio.Queue[tuple[int, bytes | int]] | None = None


class MurfTTSClient:
    def __init__(
        self,
        config: MurfTTSConfig,
        ten_env: AsyncTenEnv,
        vendor: str,
        response_msgs: asyncio.Queue[tuple[int, bytes | int]],
    ):
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor
        self.response_msgs = response_msgs

        # Current active synthesizer
        self.synthesizer: MurfTTSynthesizer = self._create_synthesizer()

    def _create_synthesizer(self) -> MurfTTSynthesizer:
        """Create new MurfTTS synthesizer instance"""
        return MurfTTSynthesizer(
            self.config, self.ten_env, self.vendor, self.response_msgs
        )

    def cancel(self, request_id: str) -> None:
        """Cancel current synthesizer request"""
        self.ten_env.log_debug(
            f"Cancelling current MurfTTS synthesizer for request_id: {request_id}"
        )

        # Clear response messages queue to prevent old data from being processed
        if self.response_msgs:
            while not self.response_msgs.empty():
                try:
                    self.response_msgs.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self.ten_env.log_debug(
                "MURF TTS response messages queue cleared during cancel"
            )

        if self.synthesizer:
            self.synthesizer.clear_text_queue()
            self.synthesizer.clear_synthesizer(request_id)

        self.ten_env.log_debug(
            f"MurfTTS synthesizer cleared successfully for request_id: {request_id}"
        )

    async def send_text(self, t: TTSTextInput):
        """Send text to MurfTTS"""
        await self.synthesizer.send_text(t)

    def clear_synthesizer(self, request_id: str):
        """Clear MurfTTS synthesizer for request_id"""
        if self.synthesizer:
            self.synthesizer.clear_synthesizer(request_id)

        self.ten_env.log_debug(
            f"MurfTTS synthesizer cleared successfully for request_id: {request_id}"
        )

    async def close(self):
        """Close MurfTTS client"""
        self.ten_env.log_info("Closing MurfTTSClient")

        # Close current synthesizer
        if self.synthesizer:
            await self.synthesizer.close()

        self.ten_env.log_info("MurfTTSClient closed")
