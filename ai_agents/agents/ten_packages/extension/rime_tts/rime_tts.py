import asyncio
import json
import base64
from datetime import datetime
from collections.abc import Awaitable, Callable

import websockets
from websockets.legacy.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedOK

from ten_ai_base.message import (
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleVendorException,
)
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR
from .config import RimeTTSConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.struct import TTSTextInput


# RIME TTS message types
RIME_MESSAGE_TYPE_CHUNK = "chunk"
RIME_MESSAGE_TYPE_TIMESTAMPS = "timestamps"
RIME_MESSAGE_TYPE_ERROR = "error"
RIME_MESSAGE_TYPE_DONE = "done"

EVENT_TTS_RESPONSE = 1
EVENT_TTS_END = 2
EVENT_TTS_TTFB_METRIC = 3
EVENT_TTS_ERROR = 4


class RimeTTSynthesizer:
    def __init__(
        self,
        config: RimeTTSConfig,
        ten_env: AsyncTenEnv,
        vendor: str,
        response_msgs: asyncio.Queue[tuple[int, bytes | int]],
        on_connection_connecting: Callable[[], Awaitable[None]] | None = None,
        on_connection_connected: Callable[[], Awaitable[None]] | None = None,
        on_connection_disconnected: (
            Callable[..., Awaitable[None]] | None
        ) = None,
    ):
        self.config = config
        self.api_key = config.api_key
        self.base_url = config.base_url
        self.ws: WebSocketClientProtocol | None = None
        self.ten_env: AsyncTenEnv = ten_env
        self.vendor = vendor
        self.response_msgs: asyncio.Queue[tuple[int, bytes | int]] | None = (
            response_msgs
        )
        self.on_connection_connecting = on_connection_connecting
        self.on_connection_connected = on_connection_connected
        self.on_connection_disconnected = on_connection_disconnected

        # Connection management
        self._session_closing = False
        self._connect_exp_cnt = 0
        self.websocket_task = None
        self.channel_tasks = []

        # Queue for pending text to be sent
        self.text_input_queue = asyncio.Queue[TTSTextInput]()

        # Event synchronization
        self._connection_ready = asyncio.Event()
        self._receive_ready_event = asyncio.Event()

        # Start websocket connection monitoring
        self.websocket_task = asyncio.create_task(self._process_websocket())

        # Flag to ensure TTFB is sent only once per
        self.sent_ts: datetime | None = None
        self.ttfb_sent: bool = False

        self.cur_request_id: str | None = None
        self.send_end_text: bool = False
        self.latest_context_id: str | None = None

    def _build_websocket_url(self) -> str:
        """Build RIME TTS WebSocket URL with query parameters"""
        params = self.config.params.copy()

        # Build query string
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.base_url}?{query_string}"

    def get_auth_headers(self) -> dict[str, str]:
        """Get RIME TTS authentication headers"""
        return {"Authorization": f"Bearer {self.api_key}"}

    def _process_ws_exception(self, exp) -> None | Exception:
        """Handle websocket connection exceptions and decide whether to reconnect"""
        self.ten_env.log_warn(
            f"websocket_connect_error: error={exp}",
            category=LOG_CATEGORY_VENDOR,
        )
        self._connect_exp_cnt += 1
        if self._connect_exp_cnt > 5:  # MAX_RETRY_TIMES_FOR_TRANSPORT
            self.ten_env.log_error(f"Max retries (5) exceeded: {str(exp)}")
            return exp
        return None  # Return None to continue reconnection

    async def _process_websocket(self) -> None:
        """Main websocket connection monitoring and reconnection logic"""
        try:
            self.ten_env.log_debug(
                "Starting RIME TTS websocket connection process"
            )
            if self.on_connection_connecting:
                await self.on_connection_connecting()

            # Use websockets.connect's automatic reconnection mechanism
            async for ws in websockets.connect(
                uri=self._build_websocket_url(),
                additional_headers=self.get_auth_headers(),
                max_size=100_000_000,
                compression=None,
                process_exception=self._process_ws_exception,
            ):
                self.ws = ws
                try:
                    self.ten_env.log_debug(
                        "websocket_connected",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    if self._session_closing:
                        self.ten_env.log_debug("Session is closing, break.")
                        return

                    # Start send and receive tasks
                    self.channel_tasks = [
                        asyncio.create_task(self._send_loop(ws)),
                        asyncio.create_task(self._receive_loop(ws)),
                    ]

                    # Wait for receive loop to be ready
                    await self._receive_ready_event.wait()
                    self._connection_ready.set()
                    if self.on_connection_connected:
                        await self.on_connection_connected()

                    await self._await_channel_tasks()

                except websockets.ConnectionClosed as e:
                    self.ten_env.log_debug(
                        f"websocket_closed: error={e}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    if self.on_connection_disconnected:
                        await self.on_connection_disconnected(
                            code=0,
                            message=str(e),
                            vendor_info=ModuleErrorVendorInfo(
                                vendor=self.vendor,
                                code=str(e.code),
                                message=str(e),
                            ),
                        )
                    if not self._session_closing:
                        self.ten_env.log_warn(
                            "RIME TTS websocket connection closed, will reconnect."
                        )
                        # Connection closed normally, send end event
                        self.ten_env.log_debug("RIME TTS connection closed")
                        if self.response_msgs and self.send_end_text:
                            self.ten_env.log_debug("Sending end event")
                            await self.response_msgs.put((EVENT_TTS_END, b""))
                            self.latest_context_id = None
                            self.send_end_text = False

                        # Cancel all channel tasks
                        for task in self.channel_tasks:
                            task.cancel()
                        await self._await_channel_tasks()

                        # Reset event states
                        self._receive_ready_event.clear()
                        self._connection_ready.clear()

                        # Reset TTFB tracking for next request
                        self.ttfb_sent = False
                        self.sent_ts = None

                        # Reset connection exception counter
                        self._connect_exp_cnt = 0
                        continue

        except Exception as e:
            self.ten_env.log_error(
                f"Exception in RIME TTS websocket process: {e}"
            )
        finally:
            if self.ws:
                await self.ws.close()
            if self.on_connection_disconnected:
                await self.on_connection_disconnected(
                    code=int(ModuleErrorCode.FATAL_ERROR),
                    message="closed",
                    vendor_info=ModuleErrorVendorInfo(
                        vendor=self.vendor,
                        code="0",
                        message="closed",
                    ),
                )
            self.ten_env.log_debug(
                "RIME TTS websocket connection process ended."
            )

    async def _await_channel_tasks(self) -> None:
        """Wait for channel tasks to complete"""
        if not self.channel_tasks:
            return

        (done, pending) = await asyncio.wait(
            self.channel_tasks,
            return_when=asyncio.FIRST_EXCEPTION,
        )
        self.ten_env.log_debug("RIME TTS channel tasks finished.")

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
        """Text sending loop for RIME TTS"""
        try:
            while not self._session_closing:
                # Get text to send from queue
                tts_text_input = await self.text_input_queue.get()
                if tts_text_input is None:  # End signal
                    break

                context_id = tts_text_input.request_id
                self.latest_context_id = context_id
                # Send text message
                await self._send_text_internal(
                    ws,
                    tts_text_input.text,
                    context_id,
                    tts_text_input.request_id,
                    tts_text_input.text_input_end,
                )
        except Exception as e:
            self.ten_env.log_error(f"Exception in RIME TTS send_loop: {e}")
            raise e

    async def _receive_loop(self, ws: WebSocketClientProtocol) -> None:
        """Message receiving loop for RIME TTS"""
        try:
            # Mark receive loop as ready
            self._receive_ready_event.set()

            # Use recv() method like official example to properly catch ConnectionClosedOK
            while True:
                if self._session_closing:
                    self.ten_env.log_debug(
                        "Session is closing, break receive loop."
                    )
                    break

                try:
                    message = await ws.recv()
                    try:
                        await self._handle_server_message(message)
                    except ModuleVendorException as e:
                        # Vendor errors should be propagated to the extension
                        self.ten_env.log_error(
                            f"Vendor error handling RIME TTS server message: {e}"
                        )
                        if self.response_msgs:
                            await self.response_msgs.put(
                                (EVENT_TTS_ERROR, str(e.error.message).encode())
                            )
                    except Exception as e:
                        self.ten_env.log_error(
                            f"Error handling RIME TTS server message: {e}"
                        )
                except ConnectionClosedOK:
                    # Connection closed normally, send end event
                    self.ten_env.log_debug("RIME TTS connection closed")
                    if self.response_msgs and self.send_end_text:
                        self.ten_env.log_debug("Sending end event")
                        await self.response_msgs.put((EVENT_TTS_END, b""))
                        self.latest_context_id = None
                        self.send_end_text = False
                    break

        except asyncio.CancelledError:
            self.ten_env.log_debug("RIME TTS receive loop cancelled")
            raise
        except Exception as e:
            if "Needs sentence parameter" in str(e):
                self.ten_env.log_warn(
                    f"RIME TTS receive loop error: {e}, please check the sentence parameter"
                )
                return
            self.ten_env.log_error(f"Exception in RIME TTS receive_loop: {e}")
            raise e

    async def _handle_server_message(self, message):
        """Handle RIME TTS server responses"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            if message_type == RIME_MESSAGE_TYPE_CHUNK:
                context_id = data.get("contextId")
                # Handle audio chunk
                audio_data = base64.b64decode(data["data"])
                self.ten_env.log_debug(
                    f"recv_audio_chunk: context_id={context_id}, audio_len={len(audio_data)}",
                    category=LOG_CATEGORY_VENDOR,
                )
                if self.response_msgs:
                    if self.sent_ts and not self.ttfb_sent:
                        ttfb_ms = int(
                            (datetime.now() - self.sent_ts).total_seconds()
                            * 1000
                        )
                        await self.response_msgs.put(
                            (EVENT_TTS_TTFB_METRIC, ttfb_ms)
                        )
                        self.ttfb_sent = True
                        self.ten_env.log_debug(
                            f"RIME TTS: TTFB metric sent: {ttfb_ms}ms"
                        )
                    await self.response_msgs.put(
                        (EVENT_TTS_RESPONSE, audio_data)
                    )

            elif message_type == RIME_MESSAGE_TYPE_TIMESTAMPS:
                # Handle timestamps (optional, for debugging)
                self.ten_env.log_debug(
                    f"RIME TTS timestamps: {data.get('word_timestamps', {})}"
                )
            elif message_type == RIME_MESSAGE_TYPE_DONE:
                context_id = data.get("contextId")
                self.ten_env.log_debug(
                    f"RIME TTS done for context_id: {context_id} and latest_context_id: {self.latest_context_id}, send end event: {self.send_end_text}"
                )

            elif message_type == RIME_MESSAGE_TYPE_ERROR:
                # Handle error
                error_message = data.get("message", "Unknown error")
                raise ModuleVendorException(
                    ModuleErrorVendorInfo(
                        vendor=self.vendor,
                        code="RIME_TTS_ERROR",
                        message=error_message,
                    )
                )
            else:
                self.ten_env.log_warn(
                    f"Unknown RIME TTS message type: {message_type}"
                )

        except Exception as e:
            self.ten_env.log_error(f"Failed to parse RIME TTS message: {e}")
            raise RuntimeError(f"Failed to parse RIME TTS message: {e}") from e

    async def send_text(self, t: TTSTextInput):
        await self.text_input_queue.put(t)

    async def _send_text_internal(
        self,
        ws: WebSocketClientProtocol,
        text: str,
        context_id: str,
        request_id: str,
        text_input_end: bool,
    ):
        """Internal text sending implementation for RIME TTS"""

        # Create RIME TTS text message
        message = {"text": text, "contextId": context_id}
        message_json = json.dumps(message)
        self.ten_env.log_debug(
            f"send_text_to_tts_server: {message_json}",
            category=LOG_CATEGORY_VENDOR,
        )
        if self.cur_request_id is None or self.cur_request_id != request_id:
            self.cur_request_id = request_id
            self.sent_ts = datetime.now()

        await ws.send(message_json)
        if text_input_end:
            self.send_end_text = True
            eos_operation = {"operation": "eos"}
            eos_json = json.dumps(eos_operation)
            self.ten_env.log_debug(
                f"send_context_end: context_id={context_id}, request_id={request_id}",
                category=LOG_CATEGORY_VENDOR,
            )
            await ws.send(eos_json)

    def cancel(self) -> None:
        """Cancel current connection, used for flush scenarios"""
        self.ten_env.log_debug("Cancelling RIME TTS request.")

        self._session_closing = True

        for task in self.channel_tasks:
            task.cancel()

        self._clear_queues()

    async def suppress_connection_callbacks_for_replacement(self) -> None:
        on_connection_disconnected = self.on_connection_disconnected
        self.on_connection_connecting = None
        self.on_connection_connected = None
        self.on_connection_disconnected = None
        if on_connection_disconnected and self.ws:
            try:
                await on_connection_disconnected(
                    code=0,
                    message="closed",
                    vendor_info=ModuleErrorVendorInfo(
                        vendor=self.vendor,
                        code="0",
                        message="closed",
                    ),
                )
            except Exception as e:
                self.ten_env.log_error(
                    f"Failed to report RIME TTS replacement disconnect: {e}"
                )

    def _clear_queues(self) -> None:
        """Clear all queues to prevent old data from being processed"""
        # Clear text queue
        while not self.text_input_queue.empty():
            try:
                self.text_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Clear response messages queue
        if self.response_msgs:
            while not self.response_msgs.empty():
                try:
                    self.response_msgs.get_nowait()
                except asyncio.QueueEmpty:
                    break

        self.ten_env.log_debug("All RIME TTS queues cleared during cancel")

    async def close(self):
        self.ten_env.log_debug("Closing RimeTTSynthesizer")

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


class RimeTTSClient:
    def __init__(
        self,
        config: RimeTTSConfig,
        ten_env: AsyncTenEnv,
        vendor: str,
        response_msgs: asyncio.Queue[tuple[int, bytes | int]],
        on_connection_connecting: Callable[[], Awaitable[None]] | None = None,
        on_connection_connected: Callable[[], Awaitable[None]] | None = None,
        on_connection_disconnected: (
            Callable[..., Awaitable[None]] | None
        ) = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor
        self.response_msgs = response_msgs
        self.on_connection_connecting = on_connection_connecting
        self.on_connection_connected = on_connection_connected
        self.on_connection_disconnected = on_connection_disconnected

        # Current active synthesizer
        self.synthesizer: RimeTTSynthesizer = self._create_synthesizer()

        # List of synthesizers to be cleaned up
        self.cancelled_synthesizers = []

        # Cleanup task
        self.cleanup_task = asyncio.create_task(
            self._cleanup_cancelled_synthesizers()
        )

    def _create_synthesizer(self) -> RimeTTSynthesizer:
        """Create new RIME TTS synthesizer instance"""
        return RimeTTSynthesizer(
            self.config,
            self.ten_env,
            self.vendor,
            self.response_msgs,
            self.on_connection_connecting,
            self.on_connection_connected,
            self.on_connection_disconnected,
        )

    async def _cleanup_cancelled_synthesizers(self) -> None:
        """Periodically clean up completed cancelled synthesizers"""
        while True:
            try:
                for synthesizer in self.cancelled_synthesizers[:]:
                    if (
                        synthesizer.websocket_task
                        and synthesizer.websocket_task.done()
                    ):
                        self.ten_env.log_debug(
                            f"Cleaning up cancelled RIME TTS synthesizer {id(synthesizer)}"
                        )
                        self.cancelled_synthesizers.remove(synthesizer)

                await asyncio.sleep(5.0)  # Check every 5 seconds
            except Exception as e:
                self.ten_env.log_error(f"Error in RIME TTS cleanup task: {e}")
                await asyncio.sleep(5.0)

    def cancel(self) -> None:
        """Cancel current synthesizer and create new synthesizer"""
        self.ten_env.log_debug(
            "Cancelling current RIME TTS synthesizer and creating new one"
        )

        # Clear response messages queue to prevent old data from being processed
        if self.response_msgs:
            while not self.response_msgs.empty():
                try:
                    self.response_msgs.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self.ten_env.log_debug(
                "RIME TTS response messages queue cleared during cancel"
            )

        # Move current synthesizer to cleanup list
        if self.synthesizer:
            self.cancelled_synthesizers.append(self.synthesizer)
            self.synthesizer.cancel()

        # Create new synthesizer
        self.synthesizer = self._create_synthesizer()
        self.ten_env.log_debug("New RIME TTS synthesizer created successfully")

    async def send_text(self, t: TTSTextInput):
        """Send text to RIME TTS"""
        await self.synthesizer.send_text(t)

    async def reset_synthesizer(self):
        """Reset synthesizer"""
        synthesizer = self.synthesizer
        if synthesizer:
            await synthesizer.suppress_connection_callbacks_for_replacement()
            if self.synthesizer is not synthesizer:
                return
            self.cancelled_synthesizers.append(synthesizer)
            synthesizer.cancel()

        self.synthesizer = self._create_synthesizer()
        self.ten_env.log_debug("Synthesizer reset successfully")

    async def close(self):
        """Close RIME TTS client"""
        self.ten_env.log_debug("Closing RimeTTSClient")

        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        # Close current synthesizer
        if self.synthesizer:
            await self.synthesizer.close()

        # Close all cancelled synthesizers
        for synthesizer in self.cancelled_synthesizers:
            try:
                await synthesizer.close()
            except Exception as e:
                self.ten_env.log_error(
                    f"Error closing cancelled RIME TTS synthesizer: {e}"
                )

        self.cancelled_synthesizers.clear()
        self.ten_env.log_debug("RimeTTSClient closed")
