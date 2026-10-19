#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import copy
import json
import ssl
import time
from typing import Callable

import websockets

from ten_ai_base.struct import TTSTextInput, TTSTextResult, TTSWord
from ten_runtime import AsyncTenEnv

from .config import MinimaxTTSWebsocketConfig


# TTS Events
EVENT_TTSSentenceStart = 350
EVENT_TTSSentenceEnd = 351
EVENT_TTSResponse = 352
EVENT_TTSTaskFinished = 353
EVENT_TTSFlush = 354
EVENT_TTSTaskFailed = 355

from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR


class MinimaxTTSTaskFailedException(Exception):
    """Exception raised when Minimax TTS task fails"""

    def __init__(self, error_msg: str, error_code: int):
        self.error_msg = error_msg
        self.error_code = error_code
        super().__init__(f"TTS task failed: {error_msg} (code: {error_code})")


class _MinimaxTTSInstance:
    """Handles a single, stateful WebSocket connection instance."""

    def __init__(
        self,
        config: MinimaxTTSWebsocketConfig,
        ten_env: AsyncTenEnv | None = None,
        vendor: str = "minimax",
        on_transcription: (
            Callable[[TTSTextResult], asyncio.Future] | None
        ) = None,
        on_error: Callable[[MinimaxTTSTaskFailedException], None] | None = None,
        on_audio_data: (
            Callable[[bytes, int, int], asyncio.Future] | None
        ) = None,
        on_usage_characters: Callable[[int], asyncio.Future] | None = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor

        self.stopping: bool = False
        self.discarding: bool = False
        self.callbacks_enabled: bool = True
        self.ws: websockets.ClientConnection | None = None
        self.session_id: str = ""
        self.session_trace_id: str = ""
        self.tts_task_queue: asyncio.Queue = asyncio.Queue()
        self.on_transcription = on_transcription
        self.on_error = on_error
        self.on_audio_data = on_audio_data
        self.on_usage_characters = on_usage_characters

        # Track current request for transcription
        self.base_request_start_ms: int = 0
        self.current_request_start_ms: int = 0  # 记录当前request的开始时间
        self.estimated_duration_this_request: int = (
            0  # 当前request的估算时长累积
        )
        self.audio_sample_rate: int = (
            16000  # 音频采样率，从extra_info中获取，默认16000
        )
        self.audio_channel: int = (
            1  # 音频声道数，从extra_info中获取，默认1（单声道）
        )
        self.request_id = -1
        self.last_word_end_ms: int = 0  # 记录上一个已处理单词的结束时间

        # Simple synchronization
        self.stopped_event: asyncio.Event = asyncio.Event()

    async def start(self):
        """Start the WebSocket processor task"""
        if self.ten_env:
            self.ten_env.log_info("Starting MinimaxTTSWebsocket processor")
        asyncio.create_task(self._process_websocket())

    async def stop(self):
        """Stop and cleanup websocket connection"""
        self.stopping = True
        await self.cancel()
        # Wait for processor to exit
        await self.stopped_event.wait()

    async def cancel(self):
        """Cancel current operations"""
        if self.ten_env:
            self.ten_env.log_info("Cancelling TTS operations")

        if self.discarding:
            return  # Already cancelling

        # Immediately disable callbacks to prevent any further data from being sent
        self.callbacks_enabled = False
        self.discarding = True

        # Immediately close WebSocket connection to stop receiving data
        if self.ws:
            try:
                await self.ws.close()
                if self.ten_env:
                    self.ten_env.log_info(
                        "WebSocket connection closed during cancel"
                    )
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_warn(
                        f"Error closing WebSocket during cancel: {e}"
                    )
            self.ws = None

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
            self.ten_env.log_debug("WebSocket processor started")

        while not self.stopping:
            session_alb_request_id = ""
            session_id = ""

            try:
                # Establish connection
                headers = {"Authorization": f"Bearer {self.config.key}"}
                ssl_context = ssl.create_default_context()

                session_start_time = time.time()
                if self.ten_env:
                    self.ten_env.log_debug(
                        f"websocket connecting to {self.config.to_str()}"
                    )

                self.ws = await websockets.connect(
                    self.config.url,
                    additional_headers=headers,
                    ssl=ssl_context,
                    max_size=1024 * 1024 * 16,
                )

                # Get trace info
                try:
                    self.session_trace_id = self.ws.response.headers.get(
                        "Trace-Id", ""
                    )
                    session_alb_request_id = self.ws.response.headers.get(
                        "alb_request_id", ""
                    )
                except Exception:
                    pass

                elapsed = int((time.time() - session_start_time) * 1000)
                if self.ten_env:
                    self.ten_env.log_info(
                        f"websocket connected, session_trace_id: {self.session_trace_id}, "
                        f"session_alb_request_id: {session_alb_request_id}, cost_time {elapsed}ms"
                    )
                    self.ten_env.log_debug(
                        f"vendor_status: connected to: {self.config.url}",
                        category=LOG_CATEGORY_VENDOR,
                    )

                # Handle init response
                init_response_bytes = await self.ws.recv()
                init_response = json.loads(init_response_bytes)
                if self.ten_env:
                    self.ten_env.log_debug(
                        f"websocket init response: {init_response}"
                    )

                if init_response.get("event") != "connected_success":
                    error_msg = init_response.get("base_resp", {}).get(
                        "status_msg", "unknown error"
                    )
                    error_code = init_response.get("base_resp", {}).get(
                        "status_code", 0
                    )
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"Websocket connection failed: {error_msg}, "
                            f"error_code: {error_code}"
                        )
                    continue

                self.session_id = init_response.get("session_id", "")
                session_id = self.session_id

                # Start task
                start_task_msg = self._create_start_task_msg()
                if self.ten_env:
                    self.ten_env.log_debug(
                        f"sending task_start: {start_task_msg}"
                    )

                await self.ws.send(json.dumps(start_task_msg))
                start_task_response_bytes = await self.ws.recv()
                start_task_response = json.loads(start_task_response_bytes)

                if self.ten_env:
                    self.ten_env.log_debug(
                        f"start task response: {start_task_response}"
                    )

                if start_task_response.get("event") != "task_started":
                    error_msg = start_task_response.get("base_resp", {}).get(
                        "status_msg", "unknown error"
                    )
                    error_code = start_task_response.get("base_resp", {}).get(
                        "status_code", 0
                    )
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"vendor_error: code: {error_code} reason: {error_msg}",
                            category=LOG_CATEGORY_VENDOR,
                        )

                    # Use callback to notify extension layer of the error
                    if self.on_error and self.callbacks_enabled:
                        exception = MinimaxTTSTaskFailedException(
                            error_msg, error_code
                        )
                        self.on_error(exception)

                    # Continue the connection loop to allow recovery on next attempt
                    await asyncio.sleep(1)
                    continue

                if self.ten_env:
                    self.ten_env.log_debug(
                        f"websocket session ready: {session_id}"
                    )

                # Process TTS tasks
                await self._process_tts_tasks(self.ws, session_id)

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
                if self.on_error and self.callbacks_enabled:
                    exception = MinimaxTTSTaskFailedException(str(e), -1)
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
            self.ten_env.log_debug("WebSocket processor exited")

    async def _process_tts_tasks(
        self, ws: websockets.ClientConnection, session_id: str
    ):
        """Process TTS tasks from the queue with keepalive mechanism"""
        keepalive_interval = 30.0  # Send keepalive every 30 seconds when idle

        while not self.stopping:
            if self.discarding:
                if self.ten_env:
                    self.ten_env.log_debug(
                        f"session_id: {session_id}, discarding all further data due to cancel."
                    )
                return

            # Wait for queue task with timeout for keepalive
            try:
                tts_input = await asyncio.wait_for(
                    self.tts_task_queue.get(), timeout=keepalive_interval
                )

                if self.ten_env:
                    self.ten_env.log_debug(
                        f"session_id: {session_id}, processing tts request: {tts_input}"
                    )

                if tts_input is None:
                    if self.ten_env:
                        self.ten_env.log_debug(
                            f"session_id: {session_id}, received sentinel None from queue, exiting _process_tts_tasks loop."
                        )
                    return  # None means stop processing (sentinel)

                # Process single TTS request
                await self._process_single_tts_request(
                    ws, tts_input, session_id
                )

            except asyncio.TimeoutError:
                # Timeout: queue is empty, send keepalive to detect connection status
                if self.ten_env:
                    self.ten_env.log_debug(
                        "No new text input, sending empty text to keep alive."
                    )
                try:
                    # Send empty text keepalive
                    keepalive_msg = {"event": "task_continue", "text": ""}
                    await ws.send(json.dumps(keepalive_msg))

                    # CRITICAL: Must consume the keepalive response immediately
                    # Otherwise it will be received by the next normal request
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    if self.ten_env:
                        response_data = json.loads(response)
                        self.ten_env.log_debug(
                            f"Keepalive response: {response_data}"
                        )
                except Exception as e:
                    if self.ten_env:
                        self.ten_env.log_error(f"Keepalive failed: {e}")
                    # Any error during keepalive means connection issue, trigger reconnection
                    raise

    async def _process_single_tts_request(
        self,
        ws: websockets.ClientConnection,
        tts_input: TTSTextInput,
        session_id: str,
    ):
        """Process a single TTS request with send-receive pattern"""
        if self.discarding or self.stopping:
            return

        # Handle empty text
        if len(tts_input.text.strip()) == 0:
            if self.ten_env:
                self.ten_env.log_debug(
                    f"session_id: {session_id}, tts request text is empty, skipping."
                )
            if tts_input.text_input_end:
                final_transcription = self._create_tts_text_result(
                    text="",
                    words=[],
                    request_id=tts_input.request_id,
                    metadata=tts_input.metadata or {},
                    text_result_end=tts_input.text_input_end,
                )
                await self._send_transcription_if_enabled(final_transcription)

                # Send sentence end event for empty text via callback if available
                if self.on_audio_data and self.callbacks_enabled:
                    try:
                        await self.on_audio_data(b"", EVENT_TTSSentenceEnd, 0)
                    except Exception as e:
                        if self.ten_env:
                            self.ten_env.log_error(
                                f"Error in sentence end callback for empty text: {e}"
                            )
            return

        # Send request
        ws_req = {"event": "task_continue", "text": tts_input.text}

        if self.ten_env:
            self.ten_env.log_debug(
                f"send_text_to_tts_server: {tts_input.text} of request_id: {tts_input.request_id}",
                category=LOG_CATEGORY_VENDOR,
            )

        await ws.send(json.dumps(ws_req))

        # Update request tracking
        if self.request_id != tts_input.request_id:
            self.request_id = tts_input.request_id

        self.current_request_start_ms = self.base_request_start_ms
        self.estimated_duration_this_request = 0
        self.last_word_end_ms = 0  # Reset for new request

        chunk_counter = 0

        # Receive responses until is_final/task_finished/task_failed
        while not self.stopping and not self.discarding:
            try:
                tts_response_bytes = await ws.recv()
                tts_response = json.loads(tts_response_bytes)

                # Log response without data field
                tts_response_for_print = tts_response.copy()
                tts_response_for_print.pop("data", None)
                if self.ten_env:
                    self.ten_env.log_info(
                        f"recv from websocket: {tts_response_for_print}"
                    )

                tts_response_event = tts_response.get("event")
                if tts_response_event == "task_failed":
                    error_msg = tts_response.get("base_resp", {}).get(
                        "status_msg", "unknown error"
                    )
                    error_code = tts_response.get("base_resp", {}).get(
                        "status_code", 0
                    )
                    if self.ten_env:
                        self.ten_env.log_error(
                            f"vendor_error: code: {error_code} reason: {error_msg}",
                            category=LOG_CATEGORY_VENDOR,
                        )

                    # Send task finished event via callback if available
                    if (
                        tts_input.text_input_end
                        and self.on_audio_data
                        and self.callbacks_enabled
                    ):
                        try:
                            await self.on_audio_data(
                                b"", EVENT_TTSTaskFailed, 0
                            )
                        except Exception as e:
                            if self.ten_env:
                                self.ten_env.log_error(
                                    f"Error in task finished callback: {e}"
                                )

                    if self.on_error and self.callbacks_enabled:
                        exception = MinimaxTTSTaskFailedException(
                            error_msg, error_code
                        )
                        self.on_error(exception)
                    break
                if tts_response_event == "task_finished":
                    if self.ten_env:
                        self.ten_env.log_debug("tts gracefully finished")

                    # Send task finished event via callback if available
                    if self.on_audio_data and self.callbacks_enabled:
                        try:
                            await self.on_audio_data(
                                b"", EVENT_TTSTaskFinished, 0
                            )
                        except Exception as e:
                            if self.ten_env:
                                self.ten_env.log_error(
                                    f"Error in task finished callback: {e}"
                                )
                    break

                if tts_response.get("is_final", False):
                    if self.ten_env:
                        self.ten_env.log_debug("tts is_final received")

                    # Update audio parameters at is_final for timestamp calculation
                    if "extra_info" in tts_response:
                        extra_info = tts_response["extra_info"]

                        if (
                            "usage_characters" in extra_info
                            and self.on_usage_characters
                            and self.callbacks_enabled
                        ):
                            usage_characters = int(
                                extra_info["usage_characters"]
                            )
                            try:
                                await self.on_usage_characters(usage_characters)
                            except Exception as e:
                                if self.ten_env:
                                    self.ten_env.log_error(
                                        f"Error in on_usage_characters callback: {e}"
                                    )

                        if "audio_sample_rate" in extra_info:
                            self.audio_sample_rate = int(
                                extra_info["audio_sample_rate"]
                            )
                            if self.ten_env:
                                self.ten_env.log_debug(
                                    f"Updated audio_sample_rate to {self.audio_sample_rate}Hz from extra_info"
                                )

                        if "audio_channel" in extra_info:
                            self.audio_channel = int(
                                extra_info["audio_channel"]
                            )
                            if self.ten_env:
                                self.ten_env.log_debug(
                                    f"Updated audio_channel to {self.audio_channel} from extra_info"
                                )

                    self.base_request_start_ms = (
                        self.current_request_start_ms
                        + self.estimated_duration_this_request
                    )

                    # Only send sentence end event if this is truly the end of the sentence
                    if (
                        tts_input.text_input_end
                        and self.on_audio_data
                        and self.callbacks_enabled
                    ):
                        try:
                            await self.on_audio_data(
                                b"", EVENT_TTSSentenceEnd, 0
                            )
                            if self.ten_env:
                                self.ten_env.log_debug(
                                    f"Sent EVENT_TTSSentenceEnd for request_id: {tts_input.request_id}"
                                )
                        except Exception as e:
                            if self.ten_env:
                                self.ten_env.log_error(
                                    f"Error in sentence end callback: {e}"
                                )
                    break

                # Process audio data
                if "data" in tts_response and "audio" in tts_response["data"]:
                    audio = tts_response["data"]["audio"]
                    audio_bytes = bytes.fromhex(audio)

                    # If this is the first audio frame and current_request_start_ms is 0, set to current physical time
                    if self.current_request_start_ms == 0:
                        self.base_request_start_ms = int(time.time() * 1000)
                        self.current_request_start_ms = (
                            self.base_request_start_ms
                        )
                        if self.ten_env:
                            self.ten_env.log_debug(
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
                            self.ten_env.log_debug(
                                f"receive_audio: duration: {estimated_chunk_duration} of request id: {tts_input.request_id}",
                                category=LOG_CATEGORY_VENDOR,
                            )

                    # Process subtitle data for transcription if enabled
                    if (
                        "subtitle" in tts_response["data"]
                        and self.config.enable_words
                        and self.on_transcription
                    ):
                        subtitle_data = tts_response["data"]["subtitle"]
                        if self.ten_env:
                            self.ten_env.log_debug(
                                f"receive_words: receive_words: {subtitle_data} of request id: {tts_input.request_id}",
                                category=LOG_CATEGORY_VENDOR,
                            )

                        subtitle_text = subtitle_data.get("text", "")

                        base_timestamp = (
                            self.last_word_end_ms
                            if self.last_word_end_ms > 0
                            else self.current_request_start_ms
                        )
                        words = self._process_subtitle_data(
                            subtitle_data, base_timestamp
                        )
                        if self.ten_env:
                            self.ten_env.log_debug(
                                f"generate_words: generate_words: {words} of request id: {tts_input.request_id}",
                                category=LOG_CATEGORY_KEY_POINT,
                            )

                        # Create transcription result with complete information
                        if words and len(words) > 0:
                            # Calculate duration based on words
                            first_word = words[0]
                            last_word = words[-1]
                            duration_ms = (
                                last_word.start_ms
                                + last_word.duration_ms
                                - first_word.start_ms
                            )
                            self.last_word_end_ms = (
                                last_word.start_ms + last_word.duration_ms
                            )
                            transcription_start_ms = first_word.start_ms
                        else:
                            duration_ms = 0
                            transcription_start_ms = (
                                self.current_request_start_ms
                            )

                        transcription = TTSTextResult(
                            request_id=tts_input.request_id,
                            text=subtitle_text,
                            start_ms=transcription_start_ms,
                            duration_ms=duration_ms,
                            words=words or [],
                            text_result_end=tts_input.text_input_end,
                            metadata=tts_input.metadata or {},
                        )

                        await self._send_transcription_if_enabled(transcription)

                    # Accumulate estimated duration for this request
                    self.estimated_duration_this_request += (
                        estimated_chunk_duration
                    )

                    chunk_counter += 1
                    # Send audio data via callback if available
                    if (
                        self.on_audio_data
                        and len(audio_bytes) > 0
                        and self.callbacks_enabled
                    ):
                        try:
                            await self.on_audio_data(
                                audio_bytes, EVENT_TTSResponse, audio_timestamp
                            )
                        except Exception as e:
                            if self.ten_env:
                                self.ten_env.log_error(
                                    f"Error in audio data callback: {e}"
                                )
                else:
                    if self.ten_env:
                        self.ten_env.log_warn(
                            f"tts response no audio data: {tts_response}"
                        )
                    break

            except websockets.exceptions.ConnectionClosedOK:
                if self.ten_env:
                    self.ten_env.log_warn(
                        "Websocket connection closed OK during TTS processing"
                    )
                break
            except websockets.exceptions.ConnectionClosed:
                if self.ten_env:
                    self.ten_env.log_warn(
                        "Websocket connection closed during TTS processing"
                    )
                break
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_error(
                        f"Error processing TTS response: {e}"
                    )
                raise

    def _create_start_task_msg(self) -> dict:
        """Create task start message"""
        start_msg = copy.deepcopy(self.config.params)
        start_msg["event"] = "task_start"
        return start_msg

    def _process_subtitle_data(
        self, subtitle_data: dict, audio_start_timestamp: int
    ) -> list[TTSWord]:
        """Process subtitle data, convert to TTSWord objects list"""
        words = []

        if "timestamped_words" in subtitle_data:
            timestamped_words = subtitle_data["timestamped_words"]

            # Handle None or empty timestamped_words
            if not timestamped_words:
                if self.ten_env:
                    self.ten_env.log_debug(
                        f"timestamped_words is None or empty for subtitle: {subtitle_data.get('text', '')}"
                    )
                return words

            if self.ten_env:
                self.ten_env.log_debug(
                    f"Processing {len(timestamped_words)} timestamped words with base timestamp: {audio_start_timestamp}"
                )

            # Merge consecutive words with same word_begin and word_end
            merged_timestamped_words = []
            current_word_data = timestamped_words[0].copy()
            for i in range(1, len(timestamped_words)):
                next_word_data = timestamped_words[i]
                if next_word_data.get("word_begin") == current_word_data.get(
                    "word_begin"
                ) and next_word_data.get("word_end") == current_word_data.get(
                    "word_end"
                ):
                    current_word_data["time_end"] = next_word_data.get(
                        "time_end", current_word_data.get("time_end", 0)
                    )
                else:
                    merged_timestamped_words.append(current_word_data)
                    current_word_data = next_word_data.copy()
            merged_timestamped_words.append(current_word_data)

            first_word_start_offset_ms = 0
            for word_data in merged_timestamped_words:
                if len(words) == 0:
                    first_word_start_offset_ms = word_data.get("time_begin", 0)

                time_begin = word_data.get("time_begin", 0)
                time_end = word_data.get("time_end", 0)

                # Use audio segment base timestamp + relative time from subtitle
                absolute_start_ms = int(
                    audio_start_timestamp
                    + time_begin
                    - first_word_start_offset_ms
                )

                # Handle special markers: [SPACE] -> space
                word_text = word_data.get("word", "")
                if word_text == "[SPACE]":
                    word_text = " "
                    if self.ten_env:
                        self.ten_env.log_debug(
                            f"Converted [SPACE] to actual space character at {absolute_start_ms}ms"
                        )

                word = TTSWord(
                    word=word_text,
                    start_ms=absolute_start_ms,
                    duration_ms=int(time_end - time_begin),
                )
                words.append(word)

        return words

    def _create_tts_text_result(
        self,
        text: str,
        words: list[TTSWord],
        request_id: str = "",
        start_ms: int = 0,
        duration_ms: int = 0,
        metadata: dict | None = None,
        text_result_end: bool = False,
    ) -> TTSTextResult:
        """Create TTSTextResult object"""
        actual_start_ms = (
            words[0].start_ms
            if words
            else (start_ms or self.current_request_start_ms)
        )
        if self.ten_env:
            self.ten_env.log_debug(
                f"create_tts_text_result text={text}, start_ms={actual_start_ms}"
            )

        return TTSTextResult(
            request_id=request_id,
            text=text,
            start_ms=actual_start_ms,
            duration_ms=duration_ms,
            words=words or [],
            text_result_end=text_result_end,
            metadata=metadata or {},
        )

    async def _send_transcription_if_enabled(
        self, transcription: TTSTextResult
    ) -> None:
        """Send transcription data if enabled"""
        if (
            self.config.enable_words
            and self.on_transcription
            and self.callbacks_enabled
        ):
            try:
                await self.on_transcription(transcription)
                if self.ten_env:
                    self.ten_env.log_info(
                        f"send tts_text_result: {transcription} of request id: {transcription.request_id}",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_error(f"Failed to send transcription: {e}")


class MinimaxTTSWebsocket:
    """
    Manages Minimax TTS client instances, providing a stable interface
    that handles non-blocking cancels and reconnections via instance swapping.
    """

    def __init__(
        self,
        config: MinimaxTTSWebsocketConfig,
        ten_env: AsyncTenEnv | None = None,
        vendor: str = "minimax",
        on_transcription: (
            Callable[[TTSTextResult], asyncio.Future] | None
        ) = None,
        on_error: Callable[[MinimaxTTSTaskFailedException], None] | None = None,
        on_audio_data: (
            Callable[[bytes, int, int], asyncio.Future] | None
        ) = None,
        on_usage_characters: Callable[[int], asyncio.Future] | None = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor
        self.on_transcription = on_transcription
        self.on_error = on_error
        self.on_audio_data = on_audio_data
        self.on_usage_characters = on_usage_characters
        self.current_client: _MinimaxTTSInstance = self._create_new_client()
        self.old_clients: list[_MinimaxTTSInstance] = []
        self.cleanup_task: asyncio.Task | None = None

    def _create_new_client(self) -> "_MinimaxTTSInstance":
        return _MinimaxTTSInstance(
            config=self.config,
            ten_env=self.ten_env,
            vendor=self.vendor,
            on_transcription=self.on_transcription,
            on_error=self.on_error,
            on_audio_data=self.on_audio_data,
            on_usage_characters=self.on_usage_characters,
        )

    async def start(self):
        """Start the WebSocket processor and the cleanup task."""
        if self.ten_env:
            self.ten_env.log_info("Starting MinimaxTTSWebsocket Manager")
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
