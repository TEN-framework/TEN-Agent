import asyncio
import json
import re
import base64

from typing import Optional, Dict, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from websockets.protocol import State

from .audio_buffer_manager import AudioBufferManager

from ten_ai_base.timeline import AudioTimeline
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS
from ten_runtime import (
    AsyncTenEnv,
)


class ElevenLabsWSRecognitionCallback:
    """ElevenLabs WebSocket Speech Recognition Callback Interface"""

    async def on_open(self):
        """Called when connection is established"""

    async def on_result(self, message_data: Dict[str, Any]):
        """
        Recognition result callback
        :param message_data: Complete recognition result data
        """

    async def on_event(self, message_data: Dict[str, Any]):
        """
        Event callback
        :param message_data: Event data
        """

    async def on_error(self, error_msg: str, error_code: Optional[str] = None):
        """Error callback"""

    async def on_close(self):
        """Called when connection is closed"""


class ElevenLabsWSRecognition:
    """Async WebSocket-based ElevenLabs speech recognition client"""

    def __init__(
        self,
        audio_timeline=AudioTimeline,
        ten_env=AsyncTenEnv,
        params: Optional[Dict[str, Any]] = None,
        callback: Optional[ElevenLabsWSRecognitionCallback] = None,
    ):
        """
        Initialize ElevenLabs WebSocket speech recognition
        :param audio_timeline: Audio timeline for timestamp management
        :param ten_env: Ten environment object for logging
        :param params: Parameter dictionary containing configuration
        :param callback: Callback instance for handling events
        """
        self.audio_timeline = audio_timeline
        self.ten_env = ten_env
        self.params = params or {}
        self.callback = callback
        self.websocket = None
        self.is_started = False
        self._message_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None

        self.api_key = params.get("api_key")
        self.ws_url = params.get("ws_url")

        self.audio_buffer = AudioBufferManager(
            ten_env=self.ten_env, threshold=640
        )

    async def _handle_message(self, message: str):
        """Handle WebSocket message from ElevenLabs"""
        try:
            message_data = json.loads(message)
            self.ten_env.log_debug(
                f"vendor_result: on_recognized: {message}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            message_type = message_data.get("message_type", "")

            if message_type == "session_started":
                session_id = message_data.get("session_id")
                config = message_data.get("config", {})
                self.ten_env.log_info(
                    f"[ElevenLabs] Session started: {session_id}, config: {config}"
                )
                if self.callback:
                    await self.callback.on_open()
                    self.is_started = True

            elif message_type == "partial_transcript":
                if self.callback:
                    await self.callback.on_result(message_data)

            elif message_type == "committed_transcript":
                if self.callback:
                    await self.callback.on_result(message_data)

            elif message_type == "committed_transcript_with_timestamps":
                if self.callback:
                    await self.callback.on_result(message_data)

            elif message_type == "error":
                error = message_data.get("error", "Unknown error")
                self.ten_env.log_error(f"[ElevenLabs] Error: {error}")
                if self.callback:
                    await self.callback.on_error(error)

            elif message_type == "auth_error":
                error = message_data.get("error", "Authentication error")
                self.ten_env.log_error(f"[ElevenLabs] Auth error: {error}")
                if self.callback:
                    await self.callback.on_error(error, "auth_error")

            elif message_type == "quota_exceeded_error":
                error = message_data.get("error", "Quota exceeded")
                self.ten_env.log_error(f"[ElevenLabs] Quota exceeded: {error}")
                if self.callback:
                    await self.callback.on_error(error, "quota_exceeded")

            else:
                self.ten_env.log_info(
                    f"[ElevenLabs] Unknown message: {message_data}"
                )
                if self.callback:
                    await self.callback.on_event(message_data)

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse message JSON: {e}"
            self.ten_env.log_error(f"[ElevenLabs] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)
        except Exception as e:
            error_msg = f"Error processing message: {e}"
            self.ten_env.log_error(f"[ElevenLabs] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)

    async def _message_handler(self):
        """Handle incoming WebSocket messages"""
        if self.websocket is None:
            self.ten_env.log_info(
                "WebSocket connection not established, skipping message handler"
            )
            return
        try:
            async for message in self.websocket:
                try:
                    await self._handle_message(message)
                except Exception as e:
                    self.ten_env.log_error(f"Error handling message: {e}")
                    continue
        except ConnectionClosed as e:
            code_match = re.search(r"(\d{3,4})", str(e))
            code = int(code_match.group(1)) if code_match else 0
            self.ten_env.log_info(
                f"[ElevenLabs] WebSocket connection closed (code={code}, reason='{e}')"
            )
            if self.callback:
                if code != 0:
                    await self.callback.on_error(str(e), str(code))

        except WebSocketException as e:
            error_msg = f"WebSocket error: {e}"
            self.ten_env.log_error(f"[ElevenLabs] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)
        except asyncio.CancelledError:
            if self.callback:
                await self.callback.on_error(e)
        except Exception as e:
            if self.callback:
                await self.callback.on_error(str(e))
        finally:
            self.is_started = False
            if self.callback:
                await self.callback.on_close()

    def _build_websocket_url(self) -> str:
        """Build WebSocket URL with query parameters for ElevenLabs"""
        base_url = self.ws_url
        query_params = []

        excluded_params = {"ws_url", "api_key"}

        for param_key, value in self.params.items():
            if param_key not in excluded_params and value is not None:
                if isinstance(value, bool):
                    query_params.append(f"{param_key}={str(value).lower()}")
                elif value:
                    query_params.append(f"{param_key}={value}")

        self.ten_env.log_info(
            f"[ElevenLabs] Building websocket url with params: {query_params}"
        )

        if query_params:
            url = f"{base_url}?{'&'.join(query_params)}"
        else:
            url = base_url

        return url

    async def start(self, timeout: int = 10) -> bool:
        """
        Start ElevenLabs recognition service
        :param timeout: Connection timeout in seconds
        :return: True if connection successful, False otherwise
        """
        if self.is_connected():
            self.ten_env.log_info("[ElevenLabs] Recognition already started")
            return True

        ws_url = self._build_websocket_url()
        headers = {"xi-api-key": self.api_key}

        self.ten_env.log_info(
            f"[ElevenLabs] Connecting to ElevenLabs: {ws_url}"
        )

        self.websocket = await websockets.connect(
            ws_url, additional_headers=headers, open_timeout=timeout
        )
        self._message_task = asyncio.create_task(self._message_handler())
        self._consumer_task = asyncio.create_task(self._consume_and_send())

        self.ten_env.log_info("[ElevenLabs] WebSocket connection established")

        return True

    async def send_audio_frame(self, audio_data: bytes):
        """
        Producer side: push audio bytes into buffer.
        :param audio_data: Audio data (bytes format)
        """
        try:
            await self.audio_buffer.push_audio(audio_data)
        except Exception as e:
            if self.callback:
                await self.callback.on_error(
                    f"Failed to enqueue audio frame: {e}"
                )

    async def _consume_and_send(self):
        """Consumer loop: pull chunks from buffer and send over websocket."""

        sample_rate = self.params.get("sample_rate", 16000)

        try:
            while True:
                if not self.is_connected():
                    await asyncio.sleep(0.01)
                    continue
                else:
                    chunk = await self.audio_buffer.pull_chunk()
                    if chunk == b"":
                        break

                    if self.websocket is None:
                        break

                    duration_ms = int(len(chunk) / (sample_rate / 1000 * 2))
                    if self.audio_timeline:
                        self.audio_timeline.add_user_audio(duration_ms)

                    # ElevenLabs expects audio data in a specific JSON format
                    audio_message = {
                        "message_type": "input_audio_chunk",
                        "audio_base_64": str(base64.b64encode(chunk), "utf-8"),
                        "commit": False,  # Let VAD handle commits
                        "sample_rate": sample_rate,
                    }
                    # self.ten_env.log_info(f"[ElevenLabs] WebSocket send len :{len(chunk)}")
                    await self.websocket.send(json.dumps(audio_message))

        except asyncio.TimeoutError:
            self.ten_env.log_error(
                "[ElevenLabs] Timeout while sending audio chunk"
            )
        except ConnectionClosed:
            self.ten_env.log_error(
                "[ElevenLabs] WebSocket connection closed while consuming audio frames"
            )
        except Exception as e:
            self.ten_env.log_error(f"[ElevenLabs] Consumer loop error: {e}")
            if self.callback:
                await self.callback.on_error(f"Consumer loop error: {e}")

    async def send_final(self):
        sample_rate = self.params.get("sample_rate", 16000)

        audio_message = {
            "message_type": "input_audio_chunk",
            "audio_base_64": "",
            "commit": True,
            "sample_rate": sample_rate,
        }
        self.ten_env.log_info("[ElevenLabs] WebSocket send final")
        await self.websocket.send(json.dumps(audio_message))

    async def stop(self):
        """Stop ElevenLabs recognition"""
        if not self.is_connected():
            self.ten_env.log_info("[ElevenLabs] Recognition not started")
            return

        try:
            self.audio_buffer.close()
            if self._consumer_task:
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass

            # ElevenLabs doesn't require explicit termination message
            # Just close the connection
            self.ten_env.log_info("[ElevenLabs] Session termination initiated")

            self.is_started = False

        except ConnectionClosed:
            self.ten_env.log_info(
                "[ElevenLabs] WebSocket connection already closed"
            )
        except Exception as e:
            error_msg = f"Failed to stop recognition: {e}"
            self.ten_env.log_error(f"[ElevenLabs] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)

    async def stop_consumer(self):
        """Stop consumer task"""
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def close(self):
        """Close WebSocket connection"""
        self.ten_env.log_info("[ElevenLabs] Starting close process")

        if self.websocket:
            try:
                if self.websocket.state == State.OPEN:
                    await self.websocket.close()
            except Exception as e:
                self.ten_env.log_info(
                    f"[ElevenLabs] Error closing websocket: {e}"
                )

        await self.stop_consumer()

        if self._message_task and not self._message_task.done():
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass

        self.is_started = False

    def is_connected(self) -> bool:
        """Check if WebSocket connection is established"""

        if self.websocket is None:
            return False
        try:
            if hasattr(self.websocket, "state"):
                return self.is_started and self.websocket.state == State.OPEN
            else:
                return self.is_started
        except Exception:
            return False
