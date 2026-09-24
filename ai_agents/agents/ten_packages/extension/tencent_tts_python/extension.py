#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from datetime import datetime
import os
import traceback

from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleType,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_VENDOR,
)
from ten_runtime import AsyncTenEnv

from .config import TencentTTSConfig
from .tencent_tts import (
    MESSAGE_TYPE_PCM,
    MESSAGE_TYPE_CMD_ERROR,
    MESSAGE_TYPE_CMD_METRIC,
    TencentTTSClient,
    TencentTTSTaskFailedException,
)


class TencentTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.client: TencentTTSClient | None = None
        self.config: TencentTTSConfig | None = None
        self.current_request_finished: bool = True
        self.current_request_id: str | None = None
        self.current_turn_id: int = -1
        self.name: str = name
        self.recorder_map: dict[str, PCMWriter] = {}
        self.request_start_ts: datetime | None = None
        self.request_total_audio_duration = 0
        self.request_first_received: bool = True
        self.last_completed_request_id: str | None = None
        self.audio_processor_task: asyncio.Task | None = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            ten_env.log_debug("on_init")

            if self.config is None:
                config_json, _ = await self.ten_env.get_property_to_json("")
                self.config = TencentTTSConfig.model_validate_json(config_json)
                # Update params from config
                self.config.update_params()
                # Validate params
                self.config.validate_params()

                ten_env.log_info(
                    f"LOG_CATEGORY_KEY_POINT: {self.config.to_str(sensitive_handling=True)}",
                    category=LOG_CATEGORY_KEY_POINT,
                )

            # Initialize Tencent TTS client
            self.client = TencentTTSClient(self.config, ten_env, self.vendor())
            asyncio.create_task(self.client.start())
            self.audio_processor_task = asyncio.create_task(
                self._process_audio_data()
            )
        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id=self.current_request_id or "",
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

    async def _handle_tts_audio_end(
        self,
        reason: TTSAudioEndReason = TTSAudioEndReason.REQUEST_END,
        error: ModuleError | None = None,
    ) -> None:
        """
        Centralized method for properly ending a TTS request.
        Flushes PCMWriter, sends audio_end event, and calls finish_request.
        """
        if self.request_start_ts is not None:
            request_event_interval = int(
                (datetime.now() - self.request_start_ts).total_seconds() * 1000
            )

            # Flush PCMWriter for current request to ensure dump file is written
            if (
                self.config
                and self.config.dump
                and self.current_request_id
                and self.current_request_id in self.recorder_map
            ):
                try:
                    await self.recorder_map[self.current_request_id].flush()
                    self.ten_env.log_debug(
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
                request_total_audio_duration_ms=self.request_total_audio_duration,
                reason=reason,
            )

            self.ten_env.log_debug(
                f"Sent audio_end for request ID: {self.current_request_id}, "
                f"request_event_interval: {request_event_interval}ms, "
                f"total_audio_duration: {self.request_total_audio_duration}ms, "
                f"reason: {reason}"
            )

            # Send usage metrics
            await self.send_usage_metrics(self.current_request_id or "")

            # Finish request to complete state transition
            await self.finish_request(
                request_id=self.current_request_id,
                reason=reason,
                error=error,
            )

            # Clear current request
            self.current_request_id = None

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        if self.audio_processor_task:
            self.audio_processor_task.cancel()
            try:
                await self.audio_processor_task
            except asyncio.CancelledError:
                ten_env.log_debug("Audio processor task cancelled.")
            self.audio_processor_task = None

        if self.client:
            self.client.close()
            self.client = None

        # Clean up all PCMWriters
        await self._cleanup_all_pcm_writers()

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def cancel_tts(self) -> None:
        if self.current_request_id:
            self.ten_env.log_debug(
                f"Current request {self.current_request_id} is being cancelled. Sending INTERRUPTED."
            )
            if self.client:
                await self.client.stop()

            # Handle audio end if there's an active request
            # This will send audio_end and call finish_request
            if self.request_start_ts:
                await self._handle_tts_audio_end(TTSAudioEndReason.INTERRUPTED)
            # Mark request as finished before handling audio end
            self.current_request_finished = True
        else:
            self.ten_env.log_warn(
                "No current request found, skipping TTS cancellation."
            )

    async def request_tts(self, t: TTSTextInput) -> None:
        """
        Override this method to handle TTS requests.
        This is called when the TTS request is made.
        """
        try:
            self.ten_env.log_info(
                f"Requesting TTS for text: {t.text}, text_input_end: {t.text_input_end} request ID: {t.request_id}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )
            if self.client is None:
                self.client = TencentTTSClient(
                    self.config, self.ten_env, self.vendor()
                )
                asyncio.create_task(self.client.start())
                self.ten_env.log_debug("TTS client reinitialized successfully.")

            if (
                self.last_completed_request_id
                and t.request_id == self.last_completed_request_id
            ):
                error_msg = f"Request ID {t.request_id} has already been completed (last completed: {self.last_completed_request_id})"
                self.ten_env.log_warn(error_msg)
                await self.send_tts_error(
                    request_id=t.request_id,
                    error=ModuleError(
                        message=error_msg,
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.NON_FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    ),
                )
                return
            if t.request_id != self.current_request_id:
                self.ten_env.log_debug(
                    f"New TTS request with ID: {t.request_id}"
                )
                self.current_request_id = t.request_id
                self.current_request_finished = False
                if t.metadata is not None:
                    self.current_turn_id = t.metadata.get("turn_id", -1)
                self.request_total_audio_duration = 0
                self.request_start_ts = datetime.now()
                self.request_first_received = True

                if self.config.dump:
                    old_request_ids = [
                        rid
                        for rid in self.recorder_map.keys()
                        if rid != t.request_id
                    ]
                    for old_rid in old_request_ids:
                        try:
                            await self.recorder_map[old_rid].flush()
                            del self.recorder_map[old_rid]
                            self.ten_env.log_debug(
                                f"Cleaned up old PCMWriter for request_id: {old_rid}"
                            )
                        except Exception as e:
                            self.ten_env.log_error(
                                f"Error cleaning up PCMWriter for request_id {old_rid}: {e}"
                            )

                    if t.request_id not in self.recorder_map:
                        dump_file_path = os.path.join(
                            self.config.dump_path,
                            f"tencent_dump_{t.request_id}.pcm",
                        )
                        self.recorder_map[t.request_id] = PCMWriter(
                            dump_file_path
                        )
                        self.ten_env.log_debug(
                            f"Created PCMWriter for request_id: {t.request_id}, file: {dump_file_path}"
                        )

            if t.text.strip() != "":
                self.ten_env.log_debug(
                    f"send_text_to_tts_server:  {t.text} of request_id: {t.request_id}",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )
                # Track character metrics
                self.metrics_add_output_characters(len(t.text))
                await self.client.synthesize_audio(t.text, t.text_input_end)
            if t.text_input_end:
                self.ten_env.log_debug(
                    f"finish session for request ID: {t.request_id}"
                )

                self.last_completed_request_id = t.request_id
                self.current_request_finished = True
                self.ten_env.log_debug(
                    f"Updated last completed request_id to: {t.request_id}"
                )
                self.client.complete()

        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}. text: {t.text}"
            )
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            # Only finish request if we've received text_input_end (request is complete)
            if self.current_request_finished or t.text_input_end:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
            else:
                # Just send error, request might continue with more text chunks
                await self.send_tts_error(
                    request_id=self.current_request_id or "",
                    error=error,
                )

    async def _process_audio_data(self) -> None:
        """
        Independent audio data process loop.
        This runs in the background and processes audio data from the client.
        """

        try:
            self.ten_env.log_debug("Starting audio process loop")

            while True:  # Loop until we get a done signal or error
                try:
                    # Get audio data from client
                    done, message_type, data = (
                        await self.client.get_audio_data()
                    )

                    self.ten_env.log_debug(
                        f"Received done: {done}, message_type: {message_type}, current_request_id: {self.current_request_id}, current_turn_id: {self.current_turn_id}"
                    )

                    # Process PCM audio chunks
                    if message_type == MESSAGE_TYPE_PCM:
                        audio_data = data
                        if (
                            audio_data is not None
                            and isinstance(audio_data, bytes)
                            and len(audio_data) > 0
                        ):
                            if self.request_first_received:
                                self.request_first_received = False
                            self.ten_env.log_debug(
                                f"Received audio data for request ID: {self.current_request_id}, audio_data_len: {len(audio_data)}"
                            )
                            if (
                                self.config.dump
                                and self.current_request_id
                                and self.current_request_id in self.recorder_map
                            ):
                                asyncio.create_task(
                                    self.recorder_map[
                                        self.current_request_id
                                    ].write(audio_data)
                                )
                            self.request_total_audio_duration += (
                                self.calculate_audio_duration(
                                    len(audio_data),
                                    self.synthesize_audio_sample_rate(),
                                    self.synthesize_audio_channels(),
                                    self.synthesize_audio_sample_width(),
                                )
                            )
                            # Track audio metrics
                            self.metrics_add_recv_audio_chunks(audio_data)
                            await self.send_tts_audio_data(audio_data)
                        else:
                            self.ten_env.log_error(
                                "Received empty payload for TTS response"
                            )

                    elif message_type == MESSAGE_TYPE_CMD_ERROR:
                        self.ten_env.log_error(
                            f"Received error message from client: {data}"
                        )
                        if isinstance(data, TencentTTSTaskFailedException):
                            # Error code 10001 is authentication/key error - FATAL_ERROR
                            error_code = (
                                ModuleErrorCode.FATAL_ERROR
                                if data.error_code == 10001
                                else ModuleErrorCode.NON_FATAL_ERROR
                            )
                            await self.send_tts_error(
                                request_id=self.current_request_id,
                                error=ModuleError(
                                    message=str(data),
                                    module=ModuleType.TTS,
                                    code=error_code,
                                    vendor_info=ModuleErrorVendorInfo(
                                        vendor=self.vendor(),
                                        code=str(data.error_code),
                                        message=data.error_message,
                                    ),
                                ),
                            )

                    elif message_type == MESSAGE_TYPE_CMD_METRIC:
                        if data is not None and isinstance(data, int):
                            await self.send_tts_audio_start(
                                request_id=self.current_request_id,
                            )
                            extra_metadata = {
                                "voice_type": self.config.voice_type,
                            }
                            await self.send_tts_ttfb_metrics(
                                request_id=self.current_request_id,
                                ttfb_ms=data,
                                extra_metadata=extra_metadata,
                            )
                            self.ten_env.log_debug(
                                f"Sent TTFB metrics for request ID: {self.current_request_id}, elapsed time: {data}ms"
                            )

                    # Handle TTS audio end - this is when we should stop
                    if done:
                        self.ten_env.log_debug(
                            f"Session finished for request ID: {self.current_request_id}"
                        )
                        await self._handle_tts_audio_end()
                        await self.client.stop()

                except asyncio.CancelledError:
                    self.ten_env.log_info("Audio consumer task was cancelled.")
                    break
                except Exception as e:
                    self.ten_env.log_error(f"Error in audio consumer loop: {e}")
                    self.ten_env.log_error(
                        "Audio consumer loop breaking due to exception"
                    )
                    # Finish request with error if there's an active request
                    error = ModuleError(
                        message=str(e),
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.NON_FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    )
                    if (
                        self.current_request_id
                        and self.current_request_finished
                    ):
                        await self._handle_tts_audio_end(
                            reason=TTSAudioEndReason.ERROR,
                            error=error,
                        )
                    else:
                        await self.send_tts_error(
                            request_id=self.current_request_id or "",
                            error=error,
                        )

        except Exception as e:
            self.ten_env.log_error(f"error in audio consumer: {e}")
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
            )
            if self.current_request_id and self.current_request_finished:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR,
                    error=error,
                )
            else:
                await self.send_tts_error(
                    request_id=self.current_request_id or "",
                    error=error,
                )

    def synthesize_audio_sample_rate(self) -> int:
        """
        Get the sample rate for the TTS audio.
        """
        return self.config.sample_rate

    def vendor(self) -> str:
        """
        Get the vendor name for the TTS audio.
        """
        return "tencent"

    def calculate_audio_duration(
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
                self.ten_env.log_debug(
                    f"Flushed PCMWriter for request_id: {request_id}"
                )
            except Exception as e:
                self.ten_env.log_error(
                    f"Error flushing PCMWriter for request_id {request_id}: {e}"
                )

        # Clear the recorder map
        self.recorder_map.clear()

    async def _flush(self) -> None:
        """
        Flush the TTS request.
        """
        if self.client:
            self.ten_env.log_debug(
                f"Flushing TTS for request ID: {self.current_request_id}"
            )
            await self.client.stop()
