#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from datetime import datetime
import os
import traceback
from typing import Tuple

from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleType,
    ModuleVendorException,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension, RequestState
from .speechify_tts import SpeechifyTTSClient, SpeechifyTTSConfig
from ten_runtime import (
    AsyncTenEnv,
)
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT
from ten_ai_base.const import LOG_CATEGORY_VENDOR


class SpeechifyTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: SpeechifyTTSConfig = None
        self.client: SpeechifyTTSClient = None
        self.current_request_id: str = None
        self.stop_event: asyncio.Event = None
        self.recorder: PCMWriter = None
        self.request_start_ts: datetime | None = None
        self.request_total_audio_duration: int | None = None
        self.response_msgs = asyncio.Queue[Tuple[bytes, bool, str]]()
        self.recorder_map: dict[str, PCMWriter] = (
            {}
        )  # store different request id pcmwriter
        self.last_completed_request_id: str | None = None
        self.completed_request_ids: set[str] = set()
        self.msg_polling_task: asyncio.Task = None
        self.get_audio_count = 0

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            ten_env.log_debug("on_init")

            if self.config is None:
                config_json, _ = await self.ten_env.get_property_to_json("")
                self.config = SpeechifyTTSConfig.model_validate_json(
                    config_json
                )
                if not self.config.params.get("key", None):
                    raise ValueError("key is required")
                if not self.config.params.get("voice_id", None):
                    raise ValueError("voice_id is required")
                self.config.update_params()
                self.ten_env.log_info(
                    f"config: {self.config.to_str(sensitive_handling=True)}",
                    category=LOG_CATEGORY_KEY_POINT,
                )

            # Create error callback function
            async def error_callback(request_id: str, error: ModuleError):
                # If no request_id is provided, use the current request_id
                target_request_id = (
                    request_id if request_id else self.current_request_id or ""
                )

                # Check if we've received text_input_end (state is FINALIZING)
                # - If text_input_end has been received (state is FINALIZING), send tts_audio_end and finish request
                # - If text_input_end has not been received (state is PROCESSING), only send error, don't end request
                has_received_text_input_end = False
                if (
                    target_request_id
                    and target_request_id in self.request_states
                ):
                    if (
                        self.request_states[target_request_id]
                        == RequestState.FINALIZING
                    ):
                        has_received_text_input_end = True

                # Send error
                await self.send_tts_error(
                    request_id=target_request_id,
                    error=error,
                )

                # If we've received text_input_end, send tts_audio_end and finish request
                if has_received_text_input_end:
                    self.ten_env.log_info(
                        f"Error occurred after text_input_end for request {target_request_id}, sending tts_audio_end with ERROR reason",
                        category=LOG_CATEGORY_KEY_POINT,
                    )
                    request_event_interval = 0
                    request_total_audio_duration = 0
                    if self.request_total_audio_duration:
                        request_total_audio_duration = int(
                            self.request_total_audio_duration
                        )
                    await self.send_tts_audio_end(
                        request_id=target_request_id,
                        request_event_interval_ms=request_event_interval,
                        request_total_audio_duration_ms=request_total_audio_duration,
                        reason=TTSAudioEndReason.ERROR,
                    )
                    await self.finish_request(
                        request_id=target_request_id,
                        reason=TTSAudioEndReason.ERROR,
                    )
                else:
                    self.ten_env.log_debug(
                        f"Error occurred before text_input_end for request {target_request_id}, only sending error (request may continue)"
                    )

                if error.code == ModuleErrorCode.FATAL_ERROR:
                    self.ten_env.log_error(
                        f"Fatal error occurred: {error.message}"
                    )
                    await self.client.close()
                    await self.on_stop(self.ten_env)

            # Create client (connection management will be handled automatically)
            self.client = SpeechifyTTSClient(
                self.config, ten_env, error_callback, self.response_msgs
            )
            self.msg_polling_task = asyncio.create_task(self._loop())

        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            ten_env.log_debug(
                "Initialization failed but event set to prevent blocking"
            )
            await self.send_tts_error(
                request_id="",  # No request_id available during on_init
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info={},
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        # Close client connection
        if self.client:
            await self.client.close()

        if self.msg_polling_task:
            self.msg_polling_task.cancel()

        # close all PCMWriter
        for request_id, recorder in self.recorder_map.items():
            try:
                await recorder.flush()
                ten_env.log_debug(
                    f"Flushed PCMWriter for request_id: {request_id}"
                )
            except Exception as e:
                ten_env.log_error(
                    f"Error flushing PCMWriter for request_id {request_id}: {e}"
                )

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    def vendor(self) -> str:
        return "speechify"

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate

    def synthesize_audio_channels(self) -> int:
        return 1

    def synthesize_audio_sample_width(self) -> int:
        return 2

    async def _loop(self) -> None:
        """Message polling loop"""
        while True:
            try:
                audio_data, isFinal, _, ttfb_ms = (
                    await self.client.response_msgs.get()
                )
                if ttfb_ms is not None:
                    extra_metadata = {
                        "voice_id": self.config.params.get("voice_id", ""),
                        "model": self.config.params.get("model", ""),
                    }
                    await self.send_tts_ttfb_metrics(
                        request_id=self.current_request_id,
                        ttfb_ms=ttfb_ms,
                        extra_metadata=extra_metadata,
                    )
                self.ten_env.log_debug(f"Received isFinal: {isFinal}")
                self.get_audio_count += 1

                if audio_data is not None:
                    # new request_id, send TTSAudioStart event
                    if (
                        self.current_request_id
                        and self.request_start_ts is None
                    ):
                        self.request_start_ts = datetime.now()
                        await self.send_tts_audio_start(
                            request_id=self.current_request_id,
                        )

                    if (
                        self.config.dump
                        and self.current_request_id
                        and self.current_request_id in self.recorder_map
                    ):
                        await self.recorder_map[self.current_request_id].write(
                            audio_data
                        )
                        self.ten_env.log_debug(
                            f"Wrote {len(audio_data)} bytes to PCMWriter for request_id: {self.current_request_id}"
                        )

                    cur_duration = self.calculate_audio_duration(
                        len(audio_data),
                        self.synthesize_audio_sample_rate(),
                        self.synthesize_audio_channels(),
                        self.synthesize_audio_sample_width(),
                    )
                    self.ten_env.log_debug(
                        f"receive_audio:  duration: {cur_duration} of request id: {self.current_request_id}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    if self.request_total_audio_duration is None:
                        self.request_total_audio_duration = cur_duration
                    else:
                        self.request_total_audio_duration += cur_duration

                    self.ten_env.log_debug(
                        f"get_audio_count: {self.get_audio_count}"
                    )
                    self.get_audio_count += 1
                    await self.send_tts_audio_data(audio_data)

                if isFinal and self.current_request_id:
                    self.client.synthesizer.send_text_in_connection = False
                    await self.handle_completed_request(
                        TTSAudioEndReason.REQUEST_END
                    )
                    # Don't reset current_request_id here, let the next request set it
                    # Reset only timing-related variables

            except Exception:
                self.ten_env.log_error(
                    f"Error in _loop: {traceback.format_exc()}"
                )

    async def request_tts(self, t: TTSTextInput) -> None:
        """
        Override this method to handle TTS requests.
        This is called when the TTS request is made.
        """
        try:
            self.ten_env.log_info(
                f"Requesting TTS for text: {t.text}, text_input_end: {t.text_input_end} request ID: {t.request_id}"
            )

            # check if request_id has already been completed
            if (
                self.completed_request_ids
                and t.request_id in self.completed_request_ids
            ):
                error_msg = (
                    f"Request ID {t.request_id} has already been completed "
                )
                self.ten_env.log_warn(error_msg)
                self.ten_env.log_debug(
                    f"skip_tts_text_input:  {t.text} of request id: {t.request_id}",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                return
            if t.text_input_end == True:
                self.completed_request_ids.add(t.request_id)
                self.ten_env.log_info(
                    f"add completed request_id to: {t.request_id}"
                )

            # new request id
            if (
                self.current_request_id is None
                or t.request_id != self.current_request_id
            ):
                self.ten_env.log_debug(
                    f"New TTS request with ID: {t.request_id}"
                )
                self.current_request_id = t.request_id
                if (
                    self.client
                    and self.client.synthesizer
                    and self.client.synthesizer.send_text_in_connection == True
                ):
                    self.ten_env.log_debug(
                        "request id is changed, but previous request is not finished, cancel it now"
                    )
                    self.client.cancel()
                    await self.handle_completed_request(
                        TTSAudioEndReason.INTERRUPTED
                    )

                self.request_total_audio_duration = 0

                # create new PCMWriter for new request_id, and clean up old PCMWriter
                if self.config.dump:
                    # clean up old PCMWriter (except for the current new request_id)
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

                    # create new PCMWriter
                    if t.request_id not in self.recorder_map:
                        dump_file_path = os.path.join(
                            self.config.dump_path,
                            f"speechify_dump_{t.request_id}.pcm",
                        )
                        self.recorder_map[t.request_id] = PCMWriter(
                            dump_file_path
                        )
                        self.ten_env.log_info(
                            f"Created PCMWriter for request_id: {t.request_id}, file: {dump_file_path}"
                        )

            if self.client is None:
                self.ten_env.log_error(
                    "Client is not initialized, cannot process TTS request"
                )
                await self.send_tts_error(
                    request_id=t.request_id,
                    error=ModuleError(
                        message="TTS client is not initialized",
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.FATAL_ERROR,
                        vendor_info={"vendor": "speechify"},
                    ),
                )
                return

            # Send text to client
            await self.client.send_text(t)

        except ModuleVendorException as e:
            self.ten_env.log_error(
                f"ModuleVendorException in request_tts: {traceback.format_exc()}. text: {t.text}"
            )
            has_received_text_input_end = False
            request_id = self.current_request_id or t.request_id
            if request_id and request_id in self.request_states:
                if self.request_states[request_id] == RequestState.FINALIZING:
                    has_received_text_input_end = True

            await self.send_tts_error(
                request_id=request_id,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=e.error,
                ),
            )

            if has_received_text_input_end:
                self.ten_env.log_info(
                    f"Error occurred after text_input_end for request {request_id}, sending tts_audio_end with ERROR reason",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                request_event_interval = 0
                request_total_audio_duration = 0
                if self.request_total_audio_duration:
                    request_total_audio_duration = int(
                        self.request_total_audio_duration
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
        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}. text: {t.text}"
            )
            has_received_text_input_end = False
            request_id = self.current_request_id or t.request_id
            if request_id and request_id in self.request_states:
                if self.request_states[request_id] == RequestState.FINALIZING:
                    has_received_text_input_end = True

            await self.send_tts_error(
                request_id=request_id,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info={"vendor": "speechify"},
                ),
            )

            if has_received_text_input_end:
                self.ten_env.log_info(
                    f"Error occurred after text_input_end for request {request_id}, sending tts_audio_end with ERROR reason",
                    category=LOG_CATEGORY_KEY_POINT,
                )
                request_event_interval = 0
                request_total_audio_duration = 0
                if self.request_total_audio_duration:
                    request_total_audio_duration = int(
                        self.request_total_audio_duration
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

    async def cancel_tts(self) -> None:
        if self.client is None:
            self.ten_env.log_error(
                "Client is not initialized, cannot handle flush"
            )
            await self.send_tts_error(
                request_id=self.current_request_id,
                error=ModuleError(
                    message="TTS client is not initialized",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info={"vendor": "speechify"},
                ),
            )
            return

        try:
            # Cancel current in-flight stream (maintain original flush behavior)
            self.client.cancel()
            await self.handle_completed_request(TTSAudioEndReason.INTERRUPTED)
        except Exception as e:
            self.ten_env.log_error(f"Error in handle_flush: {e}")
            await self.send_tts_error(
                request_id=self.current_request_id,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info={"vendor": "speechify"},
                ),
            )

    async def handle_completed_request(self, reason: TTSAudioEndReason):
        # update request_id
        self.completed_request_ids.add(self.current_request_id)
        self.ten_env.log_info(
            f"add completed request_id to: {self.current_request_id}"
        )

        # Flush PCMWriter for the completed request
        if (
            self.config.dump
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
        if self.request_start_ts is not None:
            request_event_interval = int(
                (datetime.now() - self.request_start_ts).total_seconds() * 1000
            )
        duration_ms = (
            self.request_total_audio_duration
            if self.request_total_audio_duration is not None
            else 0
        )
        await self.send_tts_audio_end(
            request_id=self.current_request_id,
            request_event_interval_ms=request_event_interval,
            request_total_audio_duration_ms=duration_ms,
            reason=reason,
        )
        self.ten_env.log_debug(
            f"Sent tts_audio_end with {reason.name} reason for request_id: {self.current_request_id}"
        )
        self.request_start_ts = None
        self.request_total_audio_duration = None

        # Finish request to complete state transition
        await self.finish_request(
            request_id=self.current_request_id,
            reason=reason,
        )
        self.current_request_id = None

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
