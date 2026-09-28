import asyncio
import json
import re

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


class AssemblyAIWSRecognitionCallback:
    """AssemblyAI WebSocket Speech Recognition Callback Interface"""

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


class AssemblyAIWSRecognition:
    """Async WebSocket-based AssemblyAI speech recognition client"""

    def __init__(
        self,
        api_key: str,
        ws_url: str = "wss://streaming.assemblyai.com/v3/",
        audio_timeline=AudioTimeline,
        ten_env=AsyncTenEnv,
        config: Optional[Dict[str, Any]] = None,
        callback: Optional[AssemblyAIWSRecognitionCallback] = None,
    ):
        """
        Initialize AssemblyAI WebSocket speech recognition
        :param api_key: AssemblyAI API key
        :param ws_url: WebSocket URL endpoint
        :param audio_timeline: Audio timeline for timestamp management
        :param ten_env: Ten environment object for logging
        :param config: Configuration parameter dictionary
        :param callback: Callback instance for handling events
        """
        self.api_key = api_key
        self.ws_url = ws_url
        self.audio_timeline = audio_timeline
        self.ten_env = ten_env
        self.config = config or {}
        self.callback = callback
        self.websocket = None
        self.is_started = False
        self._message_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None

        self.audio_buffer = AudioBufferManager(
            ten_env=self.ten_env, threshold=1600
        )

    async def _handle_message(self, message: str):
        """Handle WebSocket message from AssemblyAI"""
        try:
            message_data = json.loads(message)
            # self._log_debug(f"Received message: {message}")
            self.ten_env.log_debug(
                f"vendor_result: on_recognized: {message}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            message_type = message_data.get("type", "")

            if message_type == "Begin":
                session_id = message_data.get("id")
                expires_at = message_data.get("expires_at")
                self.ten_env.log_info(
                    f"[AssemblyAI] Session started: {session_id}, expires at: {expires_at}"
                )
                if self.callback:
                    await self.callback.on_open()
                    self.is_started = True

            elif message_type == "Turn":
                if self.callback:
                    await self.callback.on_result(message_data)

            elif message_type == "Termination":
                reason = message_data.get("reason", "Unknown")
                self.ten_env.log_info(
                    f"[AssemblyAI] Session terminated: {reason}"
                )
                if self.callback:
                    await self.callback.on_event(message_data)

            else:
                # Unrecognized message types (e.g. "SpeechStarted") are
                # informational vendor events, not errors. Routing them to
                # on_error would feed a dict into ModuleError(message=str) and
                # raise a Pydantic validation error, so surface them as events.
                self.ten_env.log_info(
                    f"[AssemblyAI] Unknown message: {message_data}"
                )
                if self.callback:
                    await self.callback.on_event(message_data)

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse message JSON: {e}"
            self.ten_env.log_error(f"[AssemblyAI] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)
        except Exception as e:
            error_msg = f"Error processing message: {e}"
            self.ten_env.log_error(f"[AssemblyAI] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)

    async def _message_handler(self):
        """Handle incoming WebSocket messages"""
        if self.websocket is None:
            self.ten_env.log_info(
                "[AssemblyAI] WebSocket connection not established, skipping message handler"
            )
            return
        try:
            async for message in self.websocket:
                try:
                    await self._handle_message(message)
                except Exception as e:
                    self.ten_env.log_error(
                        f"[AssemblyAI] Error handling message: {e}"
                    )
                    continue
        except ConnectionClosed as e:
            code_match = re.search(r"(\d{3,4})", str(e))
            code = int(code_match.group(1)) if code_match else 0
            self.ten_env.log_info(
                f"[AssemblyAI] WebSocket connection closed (code={code}, reason='{e}')"
            )
            if self.callback:
                if code != 0:
                    await self.callback.on_error(str(e), str(code))

        except WebSocketException as e:
            error_msg = f"WebSocket error: {e}"
            self.ten_env.log_error(f"[AssemblyAI] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)
        except Exception as e:
            # Note: asyncio.CancelledError derives from BaseException, so it is
            # not caught here and propagates after the finally block runs
            # on_close() — normal task cancellation during shutdown.
            if self.callback:
                await self.callback.on_error(str(e))
        finally:
            self.is_started = False
            if self.callback:
                await self.callback.on_close()

    def _build_websocket_url(self) -> str:
        """Build WebSocket URL with query parameters"""
        base_url = self.ws_url
        params = []

        sample_rate = self.config.get("sample_rate", 16000)
        params.append(f"sample_rate={sample_rate}")
        encoding = self.config.get("encoding", "pcm_s16le")
        if encoding:
            params.append(f"encoding={encoding}")

        end_of_turn_confidence_threshold = self.config.get(
            "end_of_turn_confidence_threshold"
        )
        if end_of_turn_confidence_threshold is not None:
            params.append(
                f"end_of_turn_confidence_threshold={end_of_turn_confidence_threshold}"
            )

        format_turns = self.config.get("format_turns")
        if format_turns is not None:
            params.append(f"format_turns={str(format_turns).lower()}")

        keyterms_prompt = self.config.get("keyterms_prompt", [])
        if keyterms_prompt:
            keyterms_str = ",".join(keyterms_prompt)
            params.append(f"keyterms_prompt={keyterms_str}")

        min_end_of_turn_silence_when_confident = self.config.get(
            "min_end_of_turn_silence_when_confident"
        )
        if min_end_of_turn_silence_when_confident is not None:
            params.append(
                f"min_end_of_turn_silence_when_confident={min_end_of_turn_silence_when_confident}"
            )

        max_turn_silence = self.config.get("max_turn_silence")
        if max_turn_silence is not None:
            params.append(f"max_turn_silence={max_turn_silence}")

        self.ten_env.log_info(
            f"[AssemblyAI] Building websocket url with params: {params}"
        )
        if params:
            url = f"{base_url}?{'&'.join(params)}"
        else:
            url = base_url

        return url

    async def start(self, timeout: int = 10) -> bool:
        """
        Start AssemblyAI recognition service
        :param timeout: Connection timeout in seconds
        :return: True if connection successful, False otherwise
        """
        if self.is_connected():
            self.ten_env.log_info("[AssemblyAI] Recognition already started")
            return True

        ws_url = self._build_websocket_url()
        headers = {"Authorization": self.api_key}

        self.ten_env.log_info(
            f"[AssemblyAI] Connecting to AssemblyAI: {ws_url}"
        )

        self.websocket = await websockets.connect(
            ws_url, additional_headers=headers, open_timeout=timeout
        )
        self._message_task = asyncio.create_task(self._message_handler())
        self._consumer_task = asyncio.create_task(self._consume_and_send())

        self.ten_env.log_info("[AssemblyAI] WebSocket connection established")

        return True

    async def send_audio_frame(self, audio_data: bytes):
        """
        Producer side: push audio bytes into buffer.
        :param audio_data: Audio data (bytes format)
        """
        try:
            await self.audio_buffer.push_audio(audio_data)
        except Exception as e:
            self.ten_env.log_error(
                f"[AssemblyAI] Failed to enqueue audio frame: {e}"
            )
            if self.callback:
                await self.callback.on_error(
                    f"Failed to enqueue audio frame: {e}"
                )

    async def _consume_and_send(self):
        """Consumer loop: pull chunks from buffer and send over websocket."""
        sample_rate = self.config.get("sample_rate", 16000)
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

                    # self.ten_env.log_info(f"[AssemblyAI] Sending audio chunk: {len(chunk)} bytes")
                    await self.websocket.send(chunk)
                # self._log_debug(f"Sent audio chunk: {len(chunk)} bytes")

        except asyncio.TimeoutError:
            self.ten_env.log_error(
                "[AssemblyAI] Timeout while sending audio chunk"
            )
        except ConnectionClosed:
            self.ten_env.log_error(
                "[AssemblyAI] WebSocket connection closed while consuming audio frames"
            )
        except Exception as e:
            self.ten_env.log_error(f"[AssemblyAI] Consumer loop error: {e}")
            if self.callback:
                await self.callback.on_error(f"Consumer loop error: {e}")

    async def send_update_configuration(self, config_update: Dict[str, Any]):
        """
        Send configuration update during active session
        :param config_update: Configuration parameters to update
        """
        if not self.is_connected():
            self.ten_env.log_info(
                "[AssemblyAI] Recognition not started, cannot send config update"
            )
            return

        try:
            message = {"type": "updateConfiguration", **config_update}
            await self.websocket.send(json.dumps(message))
            self.ten_env.log_info(
                f"[AssemblyAI] Sent configuration update: {config_update}"
            )

        except ConnectionClosed:
            self.ten_env.log_error(
                "[AssemblyAI] WebSocket connection closed while sending config update"
            )
        except Exception as e:
            error_msg = f"Failed to send configuration update: {e}"
            self.ten_env.log_error(f"[AssemblyAI] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)

    async def force_endpoint(self):
        """Manually force an endpoint in the transcription"""
        if not self.is_connected():
            self.ten_env.log_info(
                "[AssemblyAI] Recognition not started, cannot force endpoint"
            )
            return

        try:
            message = {"type": "forceEndpoint"}
            await self.websocket.send(json.dumps(message))
            self.ten_env.log_info("[AssemblyAI] Sent force endpoint signal")

        except ConnectionClosed:
            self.ten_env.log_error(
                "[AssemblyAI] WebSocket connection closed while forcing endpoint"
            )
        except Exception as e:
            error_msg = f"Failed to force endpoint: {e}"
            self.ten_env.log_error(f"[AssemblyAI] {error_msg}")
            if self.callback:
                await self.callback.on_error(error_msg)

    async def stop(self):
        """Stop AssemblyAI recognition"""
        if not self.is_connected():
            self.ten_env.log_info("[AssemblyAI] Recognition not started")
            return

        try:
            self.audio_buffer.close()
            if self._consumer_task:
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass
            terminate_message = {"type": "Terminate"}
            await self.websocket.send(json.dumps(terminate_message))
            self.ten_env.log_info(
                "[AssemblyAI] Session termination signal sent"
            )

            self.is_started = False

        except ConnectionClosed:
            self.ten_env.log_info(
                "[AssemblyAI] WebSocket connection already closed"
            )
        except Exception as e:
            error_msg = f"Failed to stop recognition: {e}"
            self.ten_env.log_error(f"[AssemblyAI] {error_msg}")
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
        self.ten_env.log_info("[AssemblyAI] Starting close process")

        if self.websocket:
            try:
                if self.websocket.state == State.OPEN:
                    await self.websocket.close()
            except Exception as e:
                self.ten_env.log_info(
                    f"[AssemblyAI] Error closing websocket: {e}"
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
