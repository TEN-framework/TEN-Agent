#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
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
from ten_ai_base.tts2 import AsyncTTS2BaseExtension, RequestState

from .config import GoogleTTSConfig
from .google_tts import (
    GoogleTTS,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_REQUEST_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_INVALID_KEY_ERROR,
)
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
    LOG_CATEGORY_VENDOR,
)
from ten_runtime import AsyncTenEnv


class GoogleTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: GoogleTTSConfig | None = None
        self.client: GoogleTTS | None = None
        self.sent_ts: datetime | None = None
        self.current_request_id: str | None = None
        self.total_audio_bytes: int = 0
        self.current_request_finished: bool = False
        self.recorder_map: dict[str, PCMWriter] = (
            {}
        )  # Store PCMWriter instances for different request_ids
        self.last_complete_request_id: str | None = None
        self._flush_requested = False  # Track if flush has been requested

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            config_json_str, _ = await self.ten_env.get_property_to_json("")

            if not config_json_str or config_json_str.strip() == "{}":
                raise ValueError(
                    "Configuration is empty. Required parameter 'credentials' is missing."
                )

            self.config = GoogleTTSConfig.model_validate_json(config_json_str)
            self.config.update_params()
            ten_env.log_info("Google TTS streaming mode enabled by default")
            ten_env.log_info(
                f"LOG_CATEGORY_KEY_POINT: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            if not self.config.credentials:
                raise ValueError(
                    "Configuration is empty. Required parameter 'credentials' is missing."
                )

            self.client = GoogleTTS(
                config=self.config,
                ten_env=ten_env,
            )
        except ValueError as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    message=f"Initialization failed: {e}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )
        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    message=f"Initialization failed: {e}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("GoogleTTS extension on_stop started")

        # Clean up client
        if self.client:
            try:
                self.client.clean()
            except Exception as e:
                ten_env.log_error(f"Error cleaning GoogleTTS client: {e}")
            finally:
                self.client = None

        # Clean up all PCMWriters
        # Create a copy of items to avoid "dictionary keys changed during iteration" error
        recorder_items = list(self.recorder_map.items())
        for request_id, recorder in recorder_items:
            try:
                await recorder.flush()
                ten_env.log_debug(
                    f"Flushed PCMWriter for request_id: {request_id}"
                )
            except Exception as e:
                ten_env.log_error(
                    f"Error flushing PCMWriter for request_id {request_id}: {e}"
                )

        # Clear all maps and sets
        self.recorder_map.clear()

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    def vendor(self) -> str:
        return "google"

    def synthesize_audio_sample_rate(self) -> int:
        if self.config and self.config.params:
            audio_params = self.config.params.get("AudioConfig", {})
            if audio_params.get("sample_rate_hertz"):
                return audio_params.get("sample_rate_hertz")
        return 24000  # Google TTS default sample rate

    def _calculate_audio_duration_ms(self) -> int:
        if self.config is None:
            return 0

        bytes_per_sample = 2  # 16-bit PCM
        channels = 1  # Mono
        duration_sec = self.total_audio_bytes / (
            self.synthesize_audio_sample_rate() * bytes_per_sample * channels
        )
        return int(duration_sec * 1000)

    def _reset_request_state(self) -> None:
        """Reset request state for new requests"""
        self.total_audio_bytes = 0
        self.current_request_finished = False
        self.sent_ts = None

    async def cancel_tts(self) -> None:
        self._flush_requested = True
        try:
            if self.client is not None:
                self.ten_env.log_info(
                    "Flushing Google TTS client - cleaning old connection"
                )
                self.client.clean()  # Clean up old connection first

                await self.client.reset()  # Initialize new connection
            else:
                self.ten_env.log_warn(
                    "Client is not initialized, skipping reset"
                )
        except Exception as e:
            self.ten_env.log_error(f"Error in handle_flush: {e}")

            await self.send_tts_error(
                request_id=self.current_request_id,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

        await self.handle_completed_request(TTSAudioEndReason.INTERRUPTED)

    async def handle_completed_request(self, reason: TTSAudioEndReason):
        # update request_id
        if self.last_complete_request_id == self.current_request_id:
            self.ten_env.log_debug(
                f"{self.current_request_id} was completed, skip."
            )
            return
        self.last_complete_request_id = self.current_request_id
        self.ten_env.log_debug(
            f"update last_complete_request_id to: {self.current_request_id}"
        )
        # Flush PCMWriter for the completed request
        if (
            self.config
            and self.config.dump
            and self.current_request_id
            and self.current_request_id in self.recorder_map
        ):
            try:
                await self.recorder_map[self.current_request_id].flush()
                self.ten_env.log_debug(
                    f"Flushed PCMWriter for completed request_id: {self.current_request_id}"
                )
            except Exception as e:
                self.ten_env.log_error(
                    f"Error flushing PCMWriter for completed request_id {self.current_request_id}: {e}"
                )
        # send audio_end
        request_event_interval = 0
        if self.sent_ts is not None:
            request_event_interval = int(
                (datetime.now() - self.sent_ts).total_seconds() * 1000
            )
        await self.send_tts_audio_end(
            request_id=self.current_request_id or "",
            request_event_interval_ms=request_event_interval,
            request_total_audio_duration_ms=self._calculate_audio_duration_ms(),
            reason=reason,
        )
        self.ten_env.log_debug(
            f"Sent tts_audio_end with {reason.name} reason for request_id: {self.current_request_id}"
        )

        # Send usage metrics
        await self.send_usage_metrics(self.current_request_id or "")

        # Finish request to complete state transition
        await self.finish_request(
            request_id=self.current_request_id or "",
            reason=reason,
        )

    async def request_tts(self, t: TTSTextInput) -> None:
        try:
            if not self.client or not self.config:
                raise RuntimeError("Extension is not initialized properly.")

            # Check if request_id has already been completed
            if self.last_complete_request_id == t.request_id:
                self.ten_env.log_debug(
                    f"Request ID {t.request_id} has already been completed, ignoring TTS request"
                )
                return

            # Handle new request_id
            if t.request_id != self.current_request_id:
                self.current_request_id = t.request_id
                self._reset_request_state()
                # Reset flush flag for new request
                self._flush_requested = False

                # reset connection if needed
                if self.client and self.client.send_text_in_connection == True:
                    self.ten_env.log_debug(
                        "Resetting Google TTS client since request id changed and old connection already sent request"
                    )
                    await self.handle_completed_request(
                        TTSAudioEndReason.INTERRUPTED
                    )
                    self.client.clean()
                    await self.client.reset()

                # Create new PCMWriter for new request_id and clean up old ones
                if self.config and self.config.dump:
                    # Clean up old PCMWriters (except current request_id)
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

                    # Create new PCMWriter
                    if t.request_id not in self.recorder_map:
                        dump_file_path = os.path.join(
                            self.config.dump_path,
                            f"google_dump_{t.request_id}.pcm",
                        )
                        self.recorder_map[t.request_id] = PCMWriter(
                            dump_file_path
                        )
                        self.ten_env.log_info(
                            f"Created PCMWriter for request_id: {t.request_id}, file: {dump_file_path}"
                        )

            self.ten_env.log_debug(
                f"send_text_to_tts_server:  {t.text} of request_id: {t.request_id}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            # Process audio chunks
            audio_generator = None
            if t.text.strip() != "":

                try:
                    if self.client:
                        # Track character metrics
                        self.metrics_add_output_characters(len(t.text))
                        audio_generator = self.client.get(t.text, t.request_id)
                    else:
                        return
                    async for audio_chunk, event, ttfb_ms in audio_generator:
                        # Check if flush has been requested
                        if self._flush_requested:
                            self.ten_env.log_debug(
                                "Flush requested, stopping audio processing"
                            )
                            break

                        if event == EVENT_TTS_RESPONSE and audio_chunk:
                            self.total_audio_bytes += len(audio_chunk)
                            # Track audio metrics
                            self.metrics_add_recv_audio_chunks(audio_chunk)
                            duration_ms = (
                                self.total_audio_bytes
                                / (self.synthesize_audio_sample_rate() * 2 * 1)
                                * 1000
                            )

                            self.ten_env.log_debug(
                                f"receive_audio:  duration: {duration_ms} of request id: {t.request_id}",
                                category=LOG_CATEGORY_VENDOR,
                            )

                            if self.sent_ts is None and self.current_request_id:
                                self.sent_ts = datetime.now()

                                await self.send_tts_audio_start(
                                    request_id=self.current_request_id,
                                )
                                extra_metadata = {
                                    "name": self.config.params.get(
                                        "VoiceSelectionParams", {}
                                    ).get("name", ""),
                                }
                                if ttfb_ms is not None:
                                    await self.send_tts_ttfb_metrics(
                                        request_id=self.current_request_id,
                                        ttfb_ms=ttfb_ms,
                                        extra_metadata=extra_metadata,
                                    )

                            if (
                                self.config.dump
                                and self.current_request_id
                                and self.current_request_id in self.recorder_map
                            ):
                                await self.recorder_map[
                                    self.current_request_id
                                ].write(audio_chunk)

                            await self.send_tts_audio_data(audio_chunk)

                        elif event == EVENT_TTS_REQUEST_END:
                            break

                        elif event == EVENT_TTS_INVALID_KEY_ERROR:
                            error_msg = (
                                audio_chunk.decode("utf-8")
                                if audio_chunk
                                else "Unknown API key error"
                            )
                            request_id = self.current_request_id or t.request_id
                            # Check if we've received text_input_end (state is FINALIZING)
                            has_received_text_input_end = False
                            if request_id and request_id in self.request_states:
                                if (
                                    self.request_states[request_id]
                                    == RequestState.FINALIZING
                                ):
                                    has_received_text_input_end = True

                            await self.send_tts_error(
                                request_id=request_id,
                                error=ModuleError(
                                    message=error_msg,
                                    module=ModuleType.TTS,
                                    code=ModuleErrorCode.FATAL_ERROR,
                                    vendor_info=ModuleErrorVendorInfo(
                                        vendor=self.vendor()
                                    ),
                                ),
                            )

                            # If we've received text_input_end, send tts_audio_end and finish request
                            if has_received_text_input_end:
                                self.ten_env.log_info(
                                    f"Error occurred after text_input_end for request {request_id}, sending tts_audio_end with ERROR reason",
                                    category=LOG_CATEGORY_KEY_POINT,
                                )
                                request_event_interval = 0
                                request_total_audio_duration = 0
                                if self.total_audio_bytes:
                                    request_total_audio_duration = int(
                                        self.total_audio_bytes
                                        / (
                                            self.synthesize_audio_sample_rate()
                                            * 2
                                            * 1
                                        )
                                        * 1000
                                    )
                                await self.send_tts_audio_end(
                                    request_id=request_id,
                                    request_event_interval_ms=request_event_interval,
                                    request_total_audio_duration_ms=request_total_audio_duration,
                                    reason=TTSAudioEndReason.ERROR,
                                )
                                await self.finish_request(
                                    request_id=request_id,
                                    reason=TTSAudioEndReason.ERROR,
                                )
                            return  # Exit early on error

                        elif event == EVENT_TTS_ERROR:
                            error_msg = (
                                audio_chunk.decode("utf-8")
                                if audio_chunk
                                else "Unknown client error"
                            )
                            raise RuntimeError(error_msg)
                except Exception as e:
                    # Handle exceptions from the async for loop
                    self.ten_env.log_error(
                        f"Error in audio processing: {traceback.format_exc()}"
                    )
                    request_id = self.current_request_id or t.request_id
                    # Check if we've received text_input_end (state is FINALIZING)
                    has_received_text_input_end = False
                    if request_id and request_id in self.request_states:
                        if (
                            self.request_states[request_id]
                            == RequestState.FINALIZING
                        ):
                            has_received_text_input_end = True

                    await self.send_tts_error(
                        request_id=request_id,
                        error=ModuleError(
                            message=str(e),
                            module=ModuleType.TTS,
                            code=ModuleErrorCode.NON_FATAL_ERROR,
                            vendor_info=ModuleErrorVendorInfo(
                                vendor=self.vendor()
                            ),
                        ),
                    )

                    # If we've received text_input_end, send tts_audio_end and finish request
                    if has_received_text_input_end:
                        self.ten_env.log_info(
                            f"Error occurred after text_input_end for request {request_id}, sending tts_audio_end with ERROR reason",
                            category=LOG_CATEGORY_KEY_POINT,
                        )
                        request_event_interval = 0
                        request_total_audio_duration = 0
                        if self.total_audio_bytes:
                            request_total_audio_duration = int(
                                self.total_audio_bytes
                                / (self.synthesize_audio_sample_rate() * 2 * 1)
                                * 1000
                            )
                        await self.send_tts_audio_end(
                            request_id=request_id,
                            request_event_interval_ms=request_event_interval,
                            request_total_audio_duration_ms=request_total_audio_duration,
                            reason=TTSAudioEndReason.ERROR,
                        )
                        await self.finish_request(
                            request_id=request_id,
                            reason=TTSAudioEndReason.ERROR,
                        )

                finally:
                    # Ensure the async generator is properly closed
                    if audio_generator is not None:
                        try:
                            await audio_generator.aclose()
                        except Exception as e:
                            self.ten_env.log_error(
                                f"Error closing audio generator: {e}"
                            )
            else:
                self.ten_env.log_debug(
                    f"Empty text received for request_id: {t.request_id}"
                )

            # Handle end of request (only if no error occurred)
            if t.text_input_end:
                self.current_request_finished = True
                # Only send audio_end if not flushed
                await self.handle_completed_request(
                    TTSAudioEndReason.REQUEST_END
                )
                # reset connection if needed
                if self.client and self.client.send_text_in_connection == True:
                    self.ten_env.log_debug(
                        "Resetting Google TTS client since request id changed and old connection already sent request"
                    )
                    self.client.clean()
                    await self.client.reset()

            # Ensure all async operations are completed
            self.ten_env.log_debug(
                f"TTS request {t.request_id} processing completed"
            )

        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}"
            )
            request_id = self.current_request_id or t.request_id
            # Check if we've received text_input_end (state is FINALIZING)
            has_received_text_input_end = False
            if request_id and request_id in self.request_states:
                if self.request_states[request_id] == RequestState.FINALIZING:
                    has_received_text_input_end = True

            await self.send_tts_error(
                request_id=request_id,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

            # If we've received text_input_end, send tts_audio_end and finish request
            if has_received_text_input_end:
                self.ten_env.log_info(
                    f"Error occurred after text_input_end for request {request_id}, sending tts_audio_end with ERROR reason",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                request_event_interval = 0
                request_total_audio_duration = 0
                if self.total_audio_bytes:
                    request_total_audio_duration = int(
                        self.total_audio_bytes
                        / (self.synthesize_audio_sample_rate() * 2 * 1)
                        * 1000
                    )
                await self.send_tts_audio_end(
                    request_id=request_id,
                    request_event_interval_ms=request_event_interval,
                    request_total_audio_duration_ms=request_total_audio_duration,
                    reason=TTSAudioEndReason.ERROR,
                )
                await self.finish_request(
                    request_id=request_id,
                    reason=TTSAudioEndReason.ERROR,
                )
