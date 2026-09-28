#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from datetime import datetime
import os
import traceback

from websocket import WebSocketConnectionClosedException
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR
from ten_ai_base.helper import generate_file_name, PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleType,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_runtime import AsyncTenEnv

from .config import CosyTTSConfig
from .cosy_tts import (
    MESSAGE_TYPE_PCM,
    MESSAGE_TYPE_CMD_ERROR,
    MESSAGE_TYPE_CMD_CANCEL,
    MESSAGE_TYPE_CMD_RESULT_GENERATED,
    CosyTTSClient,
)


class CosyTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)

        # TTS client for Cosy TTS service
        self.client: CosyTTSClient | None = None
        # Configuration for TTS settings
        self.config: CosyTTSConfig | None = None
        # Flag indicating if current request is finished
        self.current_request_finished: bool = True
        # ID of the current TTS request being processed
        self.current_request_id: str | None = None
        # Extension name for logging and identification
        self.name: str = name
        # Store PCMWriter instances for different request_ids
        self.recorder_map: dict[str, PCMWriter] = {}
        # Timestamp when TTS request was sent to service
        self.request_start_ts: datetime | None = None
        # Total audio duration for current request in milliseconds
        self.request_total_audio_duration_ms: int | None = None
        # Time to first byte for current request in milliseconds
        self.request_ttfb: int | None = None
        # Total audio bytes received for current request
        self.total_audio_bytes: int = 0
        # Background task for processing audio data
        self.audio_processor_task: asyncio.Task | None = None
        # Flag indicating if the first chunk has been processed
        self.first_chunk: bool = True
        # Count of audio chunks received
        self.chunk_count: int = 0
        # Flag indicating if the first request is being processed
        self.is_first_message_of_request: bool = False

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            ten_env.log_debug("on_init")

            if self.config is None:
                config_json, _ = await self.ten_env.get_property_to_json("")
                self.config = CosyTTSConfig.model_validate_json(config_json)
                # Update params from config
                self.config.update_params()
                # Validate params
                self.config.validate_params()

                self.ten_env.log_info(
                    f"config: {self.config.to_str(sensitive_handling=True)}",
                    category=LOG_CATEGORY_KEY_POINT,
                )

            # Initialize Cosy TTS client
            self.client = CosyTTSClient(self.config, ten_env, self.vendor())
            self.client.start()
            self.audio_processor_task = asyncio.create_task(
                self._process_audio_data()
            )
        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.FATAL_ERROR.value,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            await self.send_tts_error(
                request_id="",
                error=error,
            )

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        if self.audio_processor_task:
            self.audio_processor_task.cancel()
            try:
                await self.audio_processor_task
            except asyncio.CancelledError:
                ten_env.log_info("Audio processor task cancelled.")
            self.audio_processor_task = None

        if self.client:
            # The new client is stateless, no stop method needed.
            self.client = None

        # Clean up all PCMWriters
        await self._cleanup_all_pcm_writers()

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def cancel_tts(self) -> None:
        """
        Override cancel_tts to implement TTS-specific cancellation logic.
        This is called when a flush request is received for the current request.

        Responsibilities:
        1. Cancel vendor-specific TTS operations
        2. Send audio_end event with actual metrics (via _handle_tts_audio_end)
        3. Call finish_request to complete state transition (via _handle_tts_audio_end)
        """
        self.ten_env.log_info(
            f"cancel_tts called, current_request_id: {self.current_request_id}"
        )

        # Cancel the TTS client
        if self.client:
            self.ten_env.log_info(
                f"Cancelling TTS client for request ID: {self.current_request_id}"
            )
            self.client.cancel()

        # Handle audio end if there's an active request
        # This will send audio_end and call finish_request
        if self.request_start_ts and self.current_request_id:
            await self._handle_tts_audio_end(TTSAudioEndReason.INTERRUPTED)
            self.current_request_finished = True

    async def request_tts(self, t: TTSTextInput) -> None:
        """
        Override this method to handle TTS requests.
        This is called when the TTS request is made.
        """
        try:
            self.ten_env.log_info(
                f"KEYPOINT Requesting TTS for text: {t.text}, text_input_end: {t.text_input_end}, request_id: {t.request_id}, current_request_id: {self.current_request_id}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            if self.client is None:
                self.ten_env.log_error("Client is not initialized")
                return

            # Check if audio processor task is still running, restart if needed
            if (
                self.audio_processor_task is None
                or self.audio_processor_task.done()
            ):
                self.ten_env.log_info(
                    "Audio processor task not running, restarting..."
                )
                self.audio_processor_task = asyncio.create_task(
                    self._process_audio_data()
                )
                self.ten_env.log_info("Audio processor task restarted")

            if t.request_id != self.current_request_id:
                self.ten_env.log_info(
                    f"KEYPOINT New TTS request with ID: {t.request_id}"
                )
                if not self.current_request_finished:
                    self.client.complete()
                    self.current_request_finished = True

                self.current_request_id = t.request_id
                self.current_request_finished = False
                self.total_audio_bytes = 0  # Reset for new request
                self.request_ttfb = None
                self.first_chunk = True
                self.chunk_count = 0
                self.request_start_ts = datetime.now()
                self.is_first_message_of_request = True

                # Manage PCMWriter instances for audio recording
                await self._manage_pcm_writers(t.request_id)

            elif self.current_request_finished:
                error_msg = f"Received a message for a finished request_id '{t.request_id}' with text_input_end={t.text_input_end}."
                self.ten_env.log_error(error_msg)
                return

            # Get audio stream from Cosy TTS
            self.ten_env.log_debug(
                f"send_text_to_tts_server: {t.text} of request_id: {t.request_id}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            if (
                self.is_first_message_of_request
                and t.text.strip() == ""
                and t.text_input_end
            ):
                self.ten_env.log_info(
                    f"KEYPOINT skip empty text, request_id: {t.request_id}"
                )
                await self._handle_tts_audio_end()
                return

            # Start audio synthesis (returns immediately)
            if t.text.strip() == "":
                self.ten_env.log_info(
                    f"KEYPOINT skip empty text, request_id: {t.request_id}"
                )
            else:
                # Add output characters to metrics
                char_count = len(t.text)
                self.metrics_add_output_characters(char_count)
                self.ten_env.log_info(
                    f"KEYPOINT add output characters to metrics: {char_count}, request_id: {t.request_id}"
                )

                # Start audio synthesis
                self.client.synthesize_audio(t.text, t.text_input_end)
                self.is_first_message_of_request = False

            # Handle text input end
            if t.text_input_end:
                self.ten_env.log_info(
                    f"KEYPOINT finish session for request ID: {t.request_id}, current_request_id: {self.current_request_id}"
                )
                self.client.complete()
                self.current_request_finished = True

        except WebSocketConnectionClosedException as e:
            self.ten_env.log_error(f"WebSocket connection closed, {e}")
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            # Only finish request if we've received text_input_end (request is complete)
            if self.current_request_finished:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
            else:
                # Just send error, request might continue with more text chunks
                await self.send_tts_error(
                    request_id=self.current_request_id or "",
                    error=error,
                )
            self.client.cancel()

        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}. text: {t.text}, current_request_id: {self.current_request_id}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.FATAL_ERROR.value,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            # Only finish request if we've received text_input_end (request is complete)
            if self.current_request_finished:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
            else:
                # Just send error, request might continue with more text chunks
                await self.send_tts_error(
                    request_id=self.current_request_id or "",
                    error=error,
                )
            self.client.cancel()

    async def _process_audio_data(self) -> None:
        """
        Independent audio data process loop.
        This runs in the background and processes audio data from the client.
        Continuously processes data stream for multiple requests.
        done=True only marks end of current request, loop continues for next request.
        Only breaks on errors, reconnection happens on next synthesize_audio call.
        """
        try:
            self.ten_env.log_info("Starting audio process loop")

            while True:  # Continuous loop for processing multiple requests
                try:
                    self.ten_env.log_info(
                        "Waiting for audio data from client..."
                    )
                    # Get audio data from client
                    done, message_type, data = (
                        await self.client.get_audio_data()
                    )

                    self.ten_env.log_info(
                        f"Received done: {done}, message_type: {message_type}, current_request_id: {self.current_request_id}"
                    )

                    # Process PCM audio chunks
                    if message_type == MESSAGE_TYPE_PCM:
                        audio_chunk = data

                        if (
                            audio_chunk is not None
                            and len(audio_chunk) > 0
                            and isinstance(audio_chunk, bytes)
                        ):
                            # Add recv audio chunks to metrics
                            self.metrics_add_recv_audio_chunks(audio_chunk)
                            self.chunk_count += 1
                            self.total_audio_bytes += len(audio_chunk)
                            # Calculate audio duration for this chunk
                            chunk_duration_ms = self._calculate_audio_duration(
                                len(audio_chunk), self.config.sample_rate
                            )
                            self.ten_env.log_debug(
                                f"receive_audio: duration: {chunk_duration_ms}ms of request_id: {self.current_request_id}",
                                category=LOG_CATEGORY_VENDOR,
                            )

                            # Send TTS audio start on first chunk
                            if self.first_chunk:
                                await self._handle_first_audio_chunk()
                                self.first_chunk = False

                            # Write to dump file if enabled
                            await self._write_audio_to_dump_file(audio_chunk)

                            # Send audio data
                            await self.send_tts_audio_data(audio_chunk)
                        else:
                            self.ten_env.log_info(
                                f"Received empty or invalid payload for TTS response, current_request_id: {self.current_request_id}"
                            )
                    elif message_type == MESSAGE_TYPE_CMD_RESULT_GENERATED:
                        if isinstance(data, int):
                            self.metrics_add_input_characters(data)
                    elif message_type == MESSAGE_TYPE_CMD_ERROR:
                        self.ten_env.log_error(
                            f"vendor_error: {data}",
                            category=LOG_CATEGORY_VENDOR,
                        )
                        error = ModuleError(
                            message=str(data),
                            module=ModuleType.TTS,
                            code=ModuleErrorCode.NON_FATAL_ERROR.value,
                            vendor_info=ModuleErrorVendorInfo(
                                vendor=self.vendor()
                            ),
                        )
                        # Only finish request if we've received text_input_end
                        if self.current_request_finished:
                            await self._handle_tts_audio_end(
                                reason=TTSAudioEndReason.ERROR,
                                error=error,
                            )
                        else:
                            # Just send error, request might continue
                            await self.send_tts_error(
                                request_id=self.current_request_id or "",
                                error=error,
                            )

                    elif message_type == MESSAGE_TYPE_CMD_CANCEL:
                        self.ten_env.log_info(
                            f"Received cancel message from client: {data}"
                        )

                    # Handle TTS audio end - current request done, continue for next
                    if done:
                        self.ten_env.log_info(
                            f"Current request done (request_id: {self.current_request_id}), ready for next request"
                        )
                        await self._handle_tts_audio_end()

                except asyncio.CancelledError:
                    self.ten_env.log_info("Audio consumer task was cancelled.")
                    break
                except Exception as e:
                    self.ten_env.log_error(f"Error in audio consumer loop: {e}")
                    self.ten_env.log_error(
                        "Audio consumer loop breaking due to exception"
                    )
                    # Finish request with error if there's an active request
                    if (
                        self.current_request_id
                        and not self.current_request_finished
                    ):
                        error = ModuleError(
                            message=str(e),
                            module=ModuleType.TTS,
                            code=ModuleErrorCode.NON_FATAL_ERROR.value,
                            vendor_info=ModuleErrorVendorInfo(
                                vendor=self.vendor()
                            ),
                        )
                        await self._handle_tts_audio_end(
                            reason=TTSAudioEndReason.ERROR,
                            error=error,
                        )
                        self.current_request_finished = True
                    # Break loop on error, will reconnect on next synthesize_audio
                    break

        except Exception as e:
            self.ten_env.log_error(f"Fatal error in audio consumer: {e}")
            # Finish request with error if there's an active request
            if self.current_request_id and not self.current_request_finished:
                error = ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                )
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
                self.current_request_finished = True

    def synthesize_audio_sample_rate(self) -> int:
        """
        Get the sample rate for the TTS audio.
        """
        return self.config.sample_rate

    def vendor(self) -> str:
        """
        Get the vendor name for the TTS audio.
        """
        return "cosy"

    def _calculate_ttfb_ms(self, start_time: datetime) -> int:
        """
        Calculate Time To First Byte (TTFB) in milliseconds.

        Args:
            start_time: The timestamp when the request was sent

        Returns:
            TTFB in milliseconds
        """
        return int((datetime.now() - start_time).total_seconds() * 1000)

    def _calculate_audio_duration(
        self,
        bytes_length: int,
        sample_rate: int,
        channels: int = 1,
        sample_width: int = 2,
    ) -> int:
        """
        Calculate audio duration in milliseconds.

        Parameters:
        - bytes_length: Length of the audio data in bytes
        - sample_rate: Sample rate in Hz (e.g., 16000)
        - channels: Number of audio channels (default: 1 for mono)
        - sample_width: Number of bytes per sample (default: 2 for 16-bit PCM)

        Returns:
        - Duration in milliseconds (rounded down to nearest int)
        """
        bytes_per_second = sample_rate * channels * sample_width
        duration_seconds = bytes_length / bytes_per_second
        return int(duration_seconds * 1000)

    async def _cleanup_all_pcm_writers(self) -> None:
        """
        Clean up all PCMWriter instances.
        This is typically called during shutdown or cleanup operations.
        """
        for request_id, recorder in self.recorder_map.items():
            try:
                await recorder.flush()
                self.ten_env.log_info(
                    f"Flushed PCMWriter for request_id: {request_id}"
                )
            except Exception as e:
                self.ten_env.log_error(
                    f"Error flushing PCMWriter for request_id {request_id}: {e}"
                )

        # Clear the recorder map
        self.recorder_map.clear()

    def _get_pcm_dump_file_path(self, request_id: str) -> str:
        """
        Get the PCM dump file path.

        Returns:
            str: The complete path of the PCM dump file
        """
        if self.config is None:
            raise ValueError(
                "Configuration not initialized, cannot get PCM dump file path"
            )

        return os.path.join(
            self.config.dump_path,
            generate_file_name(f"{self.name}_out_{request_id}"),
        )

    async def _handle_first_audio_chunk(self) -> None:
        """
        Handle the first audio chunk from TTS service.

        This method:
        1. Sends TTS audio start event
        2. Calculates and records TTFB (Time To First Byte)
        3. Sends TTFB metrics
        4. Logs the operation
        """
        if self.request_start_ts:
            await self.send_tts_audio_start(
                self.current_request_id,
            )

            self.request_ttfb = self._calculate_ttfb_ms(self.request_start_ts)
            await self.send_tts_ttfb_metrics(
                request_id=self.current_request_id,
                ttfb_ms=self.request_ttfb,
                extra_metadata={
                    "model": (self.config.model if self.config else ""),
                    "voice": (self.config.voice if self.config else ""),
                },
            )

            self.ten_env.log_info(
                f"KEYPOINT Sent TTS audio start and TTFB metrics: {self.request_ttfb}ms, current_request_id: {self.current_request_id}"
            )

    async def _handle_tts_audio_end(
        self,
        reason: TTSAudioEndReason = TTSAudioEndReason.REQUEST_END,
        error: ModuleError | None = None,
    ) -> None:
        """
        Handle TTS audio end processing.

        This method:
        1. Calculates total audio duration
        2. Calculates request event interval
        3. Flushes PCMWriter for current request
        4. Sends TTS audio end event
        5. Logs the operation
        """
        if self.request_start_ts:
            self.request_total_audio_duration_ms = (
                self._calculate_audio_duration(
                    self.total_audio_bytes, self.config.sample_rate
                )
            )
            request_event_interval = int(
                (datetime.now() - self.request_start_ts).total_seconds() * 1000
            )

            # Flush PCMWriter for current request to ensure dump file is written
            if (
                self.current_request_id
                and self.current_request_id in self.recorder_map
            ):
                try:
                    await self.recorder_map[self.current_request_id].flush()
                    self.ten_env.log_info(
                        f"Flushed PCMWriter for request_id: {self.current_request_id}"
                    )
                except Exception as e:
                    self.ten_env.log_error(
                        f"Error flushing PCMWriter for request_id {self.current_request_id}: {e}"
                    )

            # Send TTS audio end event
            await self.send_tts_audio_end(
                request_id=self.current_request_id,
                request_event_interval_ms=request_event_interval,
                request_total_audio_duration_ms=self.request_total_audio_duration_ms,
                reason=reason,
            )
            # Send usage metrics
            await self.send_usage_metrics(self.current_request_id)
            # Finish request to complete state transition
            await self.finish_request(
                request_id=self.current_request_id,
                reason=reason,
                error=error,
            )

            self.current_request_id = None
            self.is_first_message_of_request = False

            self.ten_env.log_info(
                f"KEYPOINT Sent TTS audio end event, interval: {request_event_interval}ms, duration: {self.request_total_audio_duration_ms}ms, current_request_id: {self.current_request_id}"
            )

    async def _manage_pcm_writers(self, request_id: str) -> None:
        """
        Manage PCMWriter instances for audio recording.
        Creates new PCMWriter for current request and cleans up old ones.

        Args:
            request_id: Current request ID to keep active
        """
        if not self.config or not self.config.dump:
            return

        # Clean up old PCMWriters (except current request_id)
        old_request_ids = [
            rid for rid in self.recorder_map.keys() if rid != request_id
        ]

        for old_rid in old_request_ids:
            try:
                await self.recorder_map[old_rid].flush()
                del self.recorder_map[old_rid]
                self.ten_env.log_info(
                    f"Cleaned up old PCMWriter for request_id: {old_rid}"
                )
            except Exception as e:
                self.ten_env.log_error(
                    f"Error cleaning up PCMWriter for request_id {old_rid}: {e}"
                )

        # Create new PCMWriter if needed
        if request_id not in self.recorder_map:
            dump_file_path = self._get_pcm_dump_file_path(request_id)
            self.recorder_map[request_id] = PCMWriter(dump_file_path)
            self.ten_env.log_info(
                f"Created PCMWriter for request_id: {request_id}, file: {dump_file_path}"
            )

    async def _write_audio_to_dump_file(self, audio_chunk: bytes) -> None:
        """
        Write audio chunk to dump file if enabled.
        """
        if (
            self.config
            and self.config.dump
            and self.current_request_id
            and self.current_request_id in self.recorder_map
        ):
            self.ten_env.log_info(
                f"KEYPOINT Writing audio chunk to dump file, dump path: {self.config.dump_path}, request_id: {self.current_request_id}"
            )
            asyncio.create_task(
                self.recorder_map[self.current_request_id].write(audio_chunk)
            )
