#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import base64
import copy
import json
import ssl
import time
import websockets
import io
import wave
from typing import Callable, Optional

from ten_runtime import AsyncTenEnv
from .config import StepFunTTSConfig
from ten_ai_base.struct import TTSTextInput, TTSTextResult
from ten_ai_base.const import LOG_CATEGORY_VENDOR

# TTS Events
EVENT_TTSSentenceStart = 350
EVENT_TTSSentenceEnd = 351
EVENT_TTSResponse = 352
EVENT_TTSTaskFinished = 353
EVENT_TTSFlush = 354

# TTS ERROR
ERROR_CODE_HANDSHAKE_FAILED = -100


class StepFunTTSTaskFailedException(Exception):
    """Exception raised when StepFun TTS task fails"""

    def __init__(self, error_msg: str, error_code: int):
        self.error_msg = error_msg
        self.error_code = error_code
        super().__init__(f"TTS task failed: {error_msg} (code: {error_code})")


def wav_to_pcm(wav_data: bytes) -> bytes:
    """Convert WAV format audio data to PCM format"""
    try:
        # Create a BytesIO object from the WAV data
        wav_io = io.BytesIO(wav_data)

        # Open the WAV data with wave module
        with wave.open(wav_io, "rb") as wav_file:
            # Read all frames (PCM data)
            pcm_data = wav_file.readframes(wav_file.getnframes())
            return pcm_data

    except Exception:
        # If conversion fails, return original data
        # This handles cases where the data might already be PCM
        return wav_data


class _StepFunTTSInstance:
    """Handles a single, stateful WebSocket connection instance."""

    def __init__(
        self,
        config: StepFunTTSConfig,
        ten_env: AsyncTenEnv | None = None,
        vendor: str = "stepfun",
        on_transcription: Optional[
            Callable[[TTSTextResult], asyncio.Future]
        ] = None,
        on_error: Optional[
            Callable[[StepFunTTSTaskFailedException], None]
        ] = None,
        on_audio_data: Optional[
            Callable[[bytes, int, int], asyncio.Future]
        ] = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor

        self.stopping: bool = False
        self.discarding: bool = False
        self.ws: websockets.ClientConnection | None = None
        self.session_id: str = ""
        self.tts_task_queue: asyncio.Queue = asyncio.Queue()
        self.on_transcription = on_transcription
        self.on_error = on_error
        self.on_audio_data = on_audio_data
        self.receive_task: asyncio.Task | None = None

        # Track current request for transcription
        self.base_request_start_ms: int = 0
        self.current_request_start_ms: int = 0
        self.estimated_duration_this_request: int = 0
        self.audio_sample_rate: int = 16000  # Default sample rate
        self.audio_channel: int = 1  # Mono
        self.request_id = -1
        self.last_sentence_end_sent: bool = False

        # Simple synchronization
        self.stopped_event: asyncio.Event = asyncio.Event()

    async def start(self):
        """Start the WebSocket processor task"""
        if self.ten_env:
            self.ten_env.log_info("Starting StepFunTTS processor")
        asyncio.create_task(self._process_websocket())

    async def stop(self):
        """Stop and cleanup websocket connection"""
        self.stopping = True
        if self.receive_task and not self.receive_task.done():
            self.receive_task.cancel()
        await self.cancel()
        # Wait for processor to exit
        await self.stopped_event.wait()

    async def cancel(self):
        """Cancel current operations"""
        if self.ten_env:
            self.ten_env.log_info("Cancelling TTS operations")

        if self.discarding:
            return  # Already cancelling

        self.discarding = True
        if self.receive_task and not self.receive_task.done():
            self.receive_task.cancel()

        # Clear the task queue
        while not self.tts_task_queue.empty():
            try:
                self.tts_task_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Insert sentinel to wake up queue.get()
        await self.tts_task_queue.put(None)

    async def close(self):
        """Close the websocket connection"""
        self.stopping = True
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass  # Ignore close errors
            self.ws = None

    async def get(self, tts_input: TTSTextInput):
        """Send TTS request. Audio data will be sent via callback."""
        if self.discarding:
            if self.ten_env:
                self.ten_env.log_info(
                    "Discarding get() request because client is in cancelling state."
                )
            return

        # Simply put request in task queue - audio will be sent via callback
        await self.tts_task_queue.put(tts_input)

    async def _process_websocket(self) -> None:
        """Main WebSocket connection management loop"""
        if self.ten_env:
            self.ten_env.log_info("WebSocket processor started")

        while not self.stopping:
            session_id = ""

            try:
                # Establish connection
                headers = {"Authorization": f"Bearer {self.config.api_key}"}
                ssl_context = ssl.create_default_context()

                session_start_time = time.time()
                if self.ten_env:
                    self.ten_env.log_info(
                        f"websocket connecting to {self.config.base_url}"
                    )

                self.ws = await websockets.connect(
                    self.config.base_url + "?model=" + self.config.get_model(),
                    additional_headers=headers,
                    ssl=ssl_context,
                    max_size=1024 * 1024 * 16,
                )

                elapsed = int((time.time() - session_start_time) * 1000)
                if self.ten_env:
                    self.ten_env.log_info(
                        f"websocket connected, cost_time {elapsed}ms"
                    )
                    self.ten_env.log_info(
                        f"vendor_status: connected to: {self.config.base_url}",
                        category=LOG_CATEGORY_VENDOR,
                    )

                # Wait for connection done event
                connection_response_bytes = await self.ws.recv()
                connection_response = json.loads(connection_response_bytes)
                if self.ten_env:
                    self.ten_env.log_info(
                        f"connection response: {connection_response}"
                    )

                if connection_response.get("type") != "tts.connection.done":
                    error_msg = f"Expected tts.connection.done, got {connection_response.get('type')}"
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"Connection failed: {error_msg}"
                        )
                    continue

                self.session_id = connection_response.get("data", {}).get(
                    "session_id", ""
                )
                session_id = self.session_id

                if self.ten_env:
                    self.ten_env.log_info(
                        f"websocket session ready: {session_id}"
                    )

                # Create session
                await self._create_session()

                # Process TTS tasks with concurrent send/receive (like Aliyun)
                self.receive_task = asyncio.create_task(
                    self._receive_loop(self.ws)
                )
                send_task = asyncio.create_task(self._send_loop(self.ws))
                await asyncio.gather(send_task, self.receive_task)

            except StepFunTTSTaskFailedException as e:
                if self.ten_env:
                    self.ten_env.log_error(
                        f"vendor_error: code: {e.error_code} reason: {e.error_msg}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                if self.on_error:
                    self.on_error(e)
                await asyncio.sleep(1)
            except websockets.exceptions.ConnectionClosedError as e:
                if self.ten_env:
                    self.ten_env.log_warn(
                        f"session_id: {session_id}, websocket ConnectionClosedError: {e}"
                    )
            except websockets.exceptions.ConnectionClosedOK as e:
                if self.ten_env:
                    self.ten_env.log_warn(
                        f"session_id: {session_id}, websocket ConnectionClosedOK: {e}"
                    )
            except websockets.exceptions.InvalidHandshake as e:
                if self.ten_env:
                    self.ten_env.log_warn(
                        f"session_id: {session_id}, websocket InvalidHandshake: {e}"
                    )
                if self.on_error:
                    exception = StepFunTTSTaskFailedException(
                        str(e), ERROR_CODE_HANDSHAKE_FAILED
                    )
                    self.on_error(exception)
                await asyncio.sleep(1)  # Wait before reconnect
            except websockets.exceptions.WebSocketException as e:
                if self.ten_env:
                    self.ten_env.log_warn(
                        f"session_id: {session_id}, websocket exception: {e}"
                    )
                await asyncio.sleep(1)  # Wait before reconnect
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_warn(
                        f"session_id: {session_id}, unexpected exception: {e}"
                    )
                await asyncio.sleep(1)  # Wait before reconnect
            finally:
                self.ws = None
                self.discarding = False
                if self.ten_env:
                    self.ten_env.log_info(
                        f"session_id: {session_id}, WebSocket processor cycle finished"
                    )

        self.stopped_event.set()
        if self.ten_env:
            self.ten_env.log_info("WebSocket processor exited")

    async def _create_session(self):
        """Create TTS session"""
        if not self.ws:
            return

        # Update audio sample rate from config
        self.audio_sample_rate = self.config.get_sample_rate()

        # Use params passthrough principle: start with config.params
        data = copy.deepcopy(self.config.params)

        # Hardcode required fields
        data["session_id"] = self.session_id
        data["response_format"] = "wav"
        data["mode"] = "default"

        create_msg = {
            "type": "tts.create",
            "data": data,
        }

        if self.ten_env:
            self.ten_env.log_info(f"sending tts.create: {create_msg}")

        await self.ws.send(json.dumps(create_msg))

        # Wait for response
        create_response_bytes = await self.ws.recv()
        create_response = json.loads(create_response_bytes)

        if self.ten_env:
            self.ten_env.log_info(f"create session response: {create_response}")

        if create_response.get("type") != "tts.response.created":
            error_msg = f"Expected tts.response.created, got {create_response.get('type')}"
            raise StepFunTTSTaskFailedException(error_msg, -1)

    async def _send_loop(self, ws: websockets.ClientConnection):
        """Continuously send TTS tasks from the queue without waiting for responses."""
        while not self.stopping:
            if self.discarding:
                return

            tts_input = await self.tts_task_queue.get()
            if tts_input is None:
                return  # Sentinel

            if self.request_id != tts_input.request_id:
                self.request_id = tts_input.request_id
                self.last_sentence_end_sent = False

            try:
                if tts_input.text:
                    # Send text delta
                    text_delta_msg = {
                        "type": "tts.text.delta",
                        "data": {
                            "session_id": self.session_id,
                            "text": tts_input.text,
                        },
                    }
                    await ws.send(json.dumps(text_delta_msg))
                    if self.ten_env:
                        self.ten_env.log_info(
                            f"send_text_to_tts_server: {tts_input.text} of request_id: {self.request_id}",
                            category=LOG_CATEGORY_VENDOR,
                        )

                if tts_input.text_input_end:
                    # Send text done
                    text_done_msg = {
                        "type": "tts.text.done",
                        "data": {"session_id": self.session_id},
                    }
                    await ws.send(json.dumps(text_done_msg))
                    if self.ten_env:
                        self.ten_env.log_info("sent tts.text.done")

            except websockets.exceptions.ConnectionClosed:
                if self.ten_env:
                    self.ten_env.log_warn(
                        "Connection closed during send, putting task back."
                    )
                await self.tts_task_queue.put(
                    tts_input
                )  # Put it back for next connection
                break
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_error(f"Error in send loop: {e}")
                break

    async def _receive_loop(self, ws: websockets.ClientConnection):
        """Continuously receive messages from websocket and handle them."""
        while not self.stopping and not self.discarding:
            try:
                tts_response_bytes = await ws.recv()
                tts_response = json.loads(tts_response_bytes)
                await self._handle_response(tts_response)
            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosedOK as e:
                if self.ten_env:
                    self.ten_env.log_info(f"Connection closed OK: {e}")
                break
            except websockets.exceptions.ConnectionClosed:
                if self.ten_env:
                    self.ten_env.log_warn(
                        "Connection closed during receive loop."
                    )
                break
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_error(f"Error in receive loop: {e}")
                if self.on_error:
                    self.on_error(StepFunTTSTaskFailedException(str(e), -1))
                break

    async def _handle_response(self, tts_response: dict):
        """Handle individual TTS response"""
        tts_response_without_audio = copy.deepcopy(tts_response)
        tts_response_without_audio.pop("data", None)
        if self.ten_env:
            self.ten_env.log_info(
                f"recv from websocket: {tts_response_without_audio}"
            )

        response_type = tts_response.get("type")

        if response_type == "tts.response.error":
            error_data = tts_response.get("data", {})
            error_code = error_data.get("code", "unknown")
            error_msg = error_data.get("message", "unknown error")
            if self.ten_env:
                self.ten_env.log_error(
                    f"vendor_error: code: {error_code} reason: {error_msg}",
                    category=LOG_CATEGORY_VENDOR,
                )
            if self.on_error:
                exception = StepFunTTSTaskFailedException(
                    error_msg, int(error_code) if error_code.isdigit() else -1
                )
                self.on_error(exception)

        elif response_type == "tts.response.sentence.start":
            if self.ten_env:
                self.ten_env.log_info("Received sentence start event")
            # Send sentence start event via callback if available
            if self.on_audio_data:
                try:
                    await self.on_audio_data(b"", EVENT_TTSSentenceStart, 0)
                except Exception as e:
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"Error in sentence start callback: {e}"
                        )

        elif response_type == "tts.response.sentence.end":
            if self.ten_env:
                self.ten_env.log_info("Received sentence end event")

            self.base_request_start_ms = (
                self.current_request_start_ms
                + self.estimated_duration_this_request
            )

            # Send sentence end event via callback if available
            if self.on_audio_data and not self.last_sentence_end_sent:
                try:
                    await self.on_audio_data(b"", EVENT_TTSSentenceEnd, 0)
                    self.last_sentence_end_sent = True
                except Exception as e:
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"Error in sentence end callback: {e}"
                        )

        elif response_type == "tts.response.audio.delta":
            await self._handle_audio_delta(tts_response)

        elif response_type == "tts.response.audio.done":
            if self.ten_env:
                self.ten_env.log_info("TTS audio generation completed")
            # Send task finished event via callback if available
            if self.on_audio_data:
                try:
                    await self.on_audio_data(b"", EVENT_TTSTaskFinished, 0)
                except Exception as e:
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"Error in task finished callback: {e}"
                        )

        elif response_type == "tts.text.flushed":
            if self.ten_env:
                self.ten_env.log_info("Text flushed - audio should follow")

        else:
            if self.ten_env:
                self.ten_env.log_warn(f"Unknown response type: {response_type}")

    async def _handle_audio_delta(self, tts_response: dict):
        """Handle audio delta response"""
        audio_data = tts_response.get("data", {})
        audio_b64 = audio_data.get("audio", "")

        if audio_b64:
            try:
                # Decode base64 to get WAV data
                wav_bytes = base64.b64decode(audio_b64)
                # Convert WAV to PCM
                audio_bytes = wav_to_pcm(wav_bytes)

                if self.ten_env:
                    self.ten_env.log_info(
                        f"Converted WAV ({len(wav_bytes)} bytes) to PCM ({len(audio_bytes)} bytes)"
                    )

            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_error(
                        f"Failed to decode/convert audio: {e}"
                    )
                return

            # If this is the first audio frame and current_request_start_ms is 0, set to current physical time
            if self.current_request_start_ms == 0:
                self.base_request_start_ms = int(time.time() * 1000)
                self.current_request_start_ms = self.base_request_start_ms
                if self.ten_env:
                    self.ten_env.log_info(
                        f"Set current_request_start_ms to physical time: {self.current_request_start_ms}ms on first audio chunk"
                    )

            # Calculate audio timestamp
            audio_timestamp = (
                self.current_request_start_ms
                + self.estimated_duration_this_request
            )

            # Estimate current audio chunk duration
            estimated_chunk_duration = 0
            if len(audio_bytes) > 0:
                bytes_per_sample = 2  # 16bit = 2 bytes
                estimated_chunk_duration = (
                    len(audio_bytes)
                    * 1000
                    // (
                        self.audio_sample_rate
                        * bytes_per_sample
                        * self.audio_channel
                    )
                )
                if self.ten_env:
                    self.ten_env.log_info(
                        f"receive_audio: duration: {estimated_chunk_duration} of request id: {self.request_id}",
                        category=LOG_CATEGORY_VENDOR,
                    )

            # Accumulate estimated duration for this request
            self.estimated_duration_this_request += estimated_chunk_duration

            # Send audio data via callback if available
            if self.on_audio_data and len(audio_bytes) > 0:
                try:
                    await self.on_audio_data(
                        audio_bytes, EVENT_TTSResponse, audio_timestamp
                    )
                except Exception as e:
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"Error in audio data callback: {e}"
                        )


class StepFunTTSWebsocket:
    """
    Manages StepFun TTS client instances, providing a stable interface
    that handles non-blocking cancels and reconnections via instance swapping.
    """

    def __init__(
        self,
        config: StepFunTTSConfig,
        ten_env: AsyncTenEnv | None = None,
        vendor: str = "stepfun",
        on_transcription: Optional[
            Callable[[TTSTextResult], asyncio.Future]
        ] = None,
        on_error: Optional[
            Callable[[StepFunTTSTaskFailedException], None]
        ] = None,
        on_audio_data: Optional[
            Callable[[bytes, int, int], asyncio.Future]
        ] = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor
        self.on_transcription = on_transcription
        self.on_error = on_error
        self.on_audio_data = on_audio_data
        self.current_client: _StepFunTTSInstance = self._create_new_client()
        self.old_clients: list[_StepFunTTSInstance] = []
        self.cleanup_task: asyncio.Task | None = None

    def _create_new_client(self) -> "_StepFunTTSInstance":
        return _StepFunTTSInstance(
            config=self.config,
            ten_env=self.ten_env,
            vendor=self.vendor,
            on_transcription=self.on_transcription,
            on_error=self.on_error,
            on_audio_data=self.on_audio_data,
        )

    async def start(self):
        """Start the WebSocket processor and the cleanup task."""
        if self.ten_env:
            self.ten_env.log_info("Starting StepFunTTSWebsocket Manager")
        asyncio.create_task(self.current_client.start())
        self.cleanup_task = asyncio.create_task(self._cleanup_old_clients())

    async def stop(self):
        """Stop the current client and all old clients."""
        if self.cleanup_task:
            self.cleanup_task.cancel()

        tasks = [self.current_client.stop()]
        for client in self.old_clients:
            tasks.append(client.stop())
        await asyncio.gather(*tasks)

    async def cancel(self):
        """
        Perform a non-blocking cancel by swapping the client instance.
        The old client is stopped in the background.
        """
        if self.ten_env:
            self.ten_env.log_info(
                "Manager received cancel request, swapping instance."
            )

        if self.current_client:
            old_client = self.current_client
            # Immediately create and start a new client BEFORE cancelling the old one
            # This prevents new requests from being routed to the cancelled client
            self.current_client = self._create_new_client()
            asyncio.create_task(self.current_client.start())

            # Now cancel and cleanup the old client
            self.old_clients.append(old_client)
            await old_client.cancel()  # Use await to ensure cancel completes
            asyncio.create_task(
                old_client.stop()
            )  # Schedule stop to run in background
        else:
            # No current client, just create a new one
            self.current_client = self._create_new_client()
            asyncio.create_task(self.current_client.start())

        if self.ten_env:
            self.ten_env.log_info(
                "New TTS client instance created after cancel."
            )

    async def get(self, tts_input: TTSTextInput):
        """Delegate the get call to the current active client instance."""
        await self.current_client.get(tts_input)

    async def _cleanup_old_clients(self):
        """Periodically clean up old clients that have finished stopping."""
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds
            stopped_clients = [
                client
                for client in self.old_clients
                if client.stopped_event.is_set()
            ]
            for client in stopped_clients:
                if self.ten_env:
                    self.ten_env.log_info(
                        f"Cleaning up stopped client: {id(client)}"
                    )
                self.old_clients.remove(client)
