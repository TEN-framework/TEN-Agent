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
    ModuleType,
    ModuleErrorVendorInfo,
    ModuleVendorException,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_TRANSCRIPTS
from .config import MurfTTSConfig
from .const import INVALID_TEXT_LIST

from .murf_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
    MurfTTSClient,
)
from ten_runtime import AsyncTenEnv


class MurfTTSExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: MurfTTSConfig = None
        self.client: MurfTTSClient = None
        self.current_request_id: str = None
        self.stop_event: asyncio.Event = None
        self.msg_polling_task: asyncio.Task = None
        self.sent_tts: bool = False
        self.request_start_ts: datetime | None = None
        self.request_total_audio_duration: int = 0
        self.response_msgs: asyncio.Queue[tuple[int, bytes | int]] = (
            asyncio.Queue(maxsize=100)
        )
        self.recorder_map: dict[str, PCMWriter] = {}
        self.last_completed_request_id: str | None = None
        self.last_completed_has_cleared_synthesizer = True
        self.current_request_finished: bool = True
        self.current_turn_id: int | None = None
        self.request_lock = asyncio.Lock()
        self.pcm_write_tasks: set[asyncio.Task] = set()

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            ten_env.log_info("on_init")

            config_json, _ = await self.ten_env.get_property_to_json("")
            if not config_json or config_json.strip() == "{}":
                raise ValueError(
                    "Configuration is empty. Required parameter 'api_key' is missing."
                )

            self.config = MurfTTSConfig.model_validate_json(config_json)
            self.config.update_params()

            ten_env.log_info(
                f"LOG_CATEGORY_KEY_POINT: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if not self.config.api_key:
                raise ValueError("api_key is required")

            # Create client (connection management will be handled automatically)
            self.client = MurfTTSClient(
                self.config, self.ten_env, self.vendor(), self.response_msgs
            )
            self.msg_polling_task = asyncio.create_task(self._loop())
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
        if self.client:
            await self.client.close()

        if self.msg_polling_task:
            self.msg_polling_task.cancel()

        if self.pcm_write_tasks:
            for task in list(self.pcm_write_tasks):
                task.cancel()
            await asyncio.gather(*self.pcm_write_tasks, return_exceptions=True)
            self.pcm_write_tasks.clear()

        for request_id, recorder in self.recorder_map.items():
            try:
                await recorder.flush()
                ten_env.log_info(
                    f"Flushed PCMWriter for request_id: {request_id}"
                )
            except Exception as e:
                ten_env.log_error(
                    f"Error flushing PCMWriter for request_id {request_id}: {e}"
                )

        await super().on_stop(ten_env)
        ten_env.log_info("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_info("on_deinit")

    def vendor(self) -> str:
        return "murf"

    async def _get_current_request_id(self) -> str | None:
        async with self.request_lock:
            return self.current_request_id

    async def _set_current_request_id(self, request_id: str | None) -> None:
        async with self.request_lock:
            self.current_request_id = request_id

    def _track_task(self, task: asyncio.Task) -> None:
        self.pcm_write_tasks.add(task)
        task.add_done_callback(self.pcm_write_tasks.discard)

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate

    async def _loop(self) -> None:
        while True:
            try:
                event, data = await self.client.response_msgs.get()
                current_request_id = await self._get_current_request_id()

                if event == EVENT_TTS_RESPONSE:  # Audio data event
                    if data is not None and isinstance(data, bytes):
                        self.ten_env.log_debug(
                            f"Received audio data for request ID: {current_request_id}, audio_data_len: {len(data)}"
                        )

                        if (
                            self.config.dump
                            and current_request_id
                            and current_request_id in self.recorder_map
                        ):
                            write_task = asyncio.create_task(
                                self.recorder_map[current_request_id].write(
                                    data
                                )
                            )
                            self._track_task(write_task)
                        self.request_total_audio_duration += (
                            self.calculate_audio_duration(
                                len(data),
                                self.synthesize_audio_sample_rate(),
                                self.synthesize_audio_channels(),
                                self.synthesize_audio_sample_width(),
                            )
                        )
                        await self.send_tts_audio_data(data)
                    else:
                        self.ten_env.log_debug(
                            "Received empty payload for TTS response"
                        )
                elif event == EVENT_TTS_TTFB_METRIC:
                    if data is not None and isinstance(data, int):
                        self.request_start_ts = datetime.now()
                        ttfb = data
                        await self.send_tts_audio_start(
                            request_id=current_request_id,
                        )
                        extra_metadata = {
                            "voiceId": self.config.params.get("voiceId", ""),
                            "model": self.config.model,
                        }
                        await self.send_tts_ttfb_metrics(
                            request_id=current_request_id,
                            ttfb_ms=ttfb,
                            extra_metadata=extra_metadata,
                        )

                        self.ten_env.log_debug(
                            f"Sent TTS audio start and TTFB metrics: {ttfb}ms"
                        )
                elif event == EVENT_TTS_END:
                    self.ten_env.log_debug(
                        f"Session finished for request ID: {current_request_id}"
                    )
                    await self._handle_tts_audio_end()
                    if self.stop_event:
                        self.stop_event.set()
                        self.stop_event = None
                elif event == EVENT_TTS_ERROR:
                    error_msg = (
                        data.decode() if isinstance(data, bytes) else str(data)
                    )
                    self.ten_env.log_error(
                        f"TTS error for request ID {current_request_id}: {error_msg}"
                    )
                    error = ModuleError(
                        message=error_msg,
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                    )
                    if self.current_request_finished:
                        await self._handle_tts_audio_end(
                            reason=TTSAudioEndReason.ERROR, error=error
                        )
                    else:
                        await self.send_tts_error(
                            request_id=current_request_id or "",
                            error=error,
                        )
                    if self.stop_event:
                        self.stop_event.set()
                        self.stop_event = None

            except Exception:
                self.ten_env.log_error(
                    f"Error in _loop: {traceback.format_exc()}"
                )
                if self.stop_event:
                    self.stop_event.set()
                    self.stop_event = None

    async def _handle_tts_audio_end(
        self,
        reason: TTSAudioEndReason = TTSAudioEndReason.REQUEST_END,
        error: ModuleError | None = None,
    ) -> None:
        """Centralized method for properly ending a TTS request."""
        if self.request_start_ts is not None:
            current_request_id = await self._get_current_request_id()
            request_event_interval = int(
                (datetime.now() - self.request_start_ts).total_seconds() * 1000
            )

            # Flush PCMWriter for current request to ensure dump file is written
            if (
                self.config.dump
                and current_request_id
                and current_request_id in self.recorder_map
            ):
                try:
                    await self.recorder_map[current_request_id].flush()
                    self.ten_env.log_debug(
                        f"Flushed PCMWriter for request_id: {current_request_id}"
                    )
                except Exception as e:
                    self.ten_env.log_error(
                        f"Error flushing PCMWriter for request_id {current_request_id}: {e}"
                    )

            # Send TTS audio end event
            await self.send_tts_audio_end(
                request_id=current_request_id,
                request_event_interval_ms=request_event_interval,
                request_total_audio_duration_ms=self.request_total_audio_duration,
                reason=reason,
            )

            self.ten_env.log_debug(
                f"Sent TTS audio end for request ID: {current_request_id}, "
                f"interval: {request_event_interval}ms, duration: {self.request_total_audio_duration}ms, "
                f"reason: {reason}"
            )

            # Finish request to complete state transition
            await self.finish_request(
                request_id=current_request_id,
                reason=reason,
                error=error,
            )

            # Clear current request
            await self._set_current_request_id(None)

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

            current_request_id = await self._get_current_request_id()
            self.ten_env.log_debug(
                f"current_request_id: {current_request_id}, new request_id: {t.request_id}"
            )
            if self.client is None:
                self.client = MurfTTSClient(
                    self.config, self.ten_env, self.vendor(), self.response_msgs
                )
                self.ten_env.log_info("TTS client reinitialized successfully.")

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
            if t.request_id != current_request_id:
                self.ten_env.log_debug(
                    f"New TTS request with ID: {t.request_id}"
                )
                if not self.last_completed_has_cleared_synthesizer:
                    self.client.clear_synthesizer(current_request_id)
                self.last_completed_has_cleared_synthesizer = False

                await self._set_current_request_id(t.request_id)
                self.current_request_finished = False
                if t.metadata is not None:
                    self.session_id = t.metadata.get("session_id", "")
                    self.current_turn_id = t.metadata.get("turn_id", -1)
                self.request_start_ts = datetime.now()
                self.request_total_audio_duration = 0
                self.sent_tts = False

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

                    # Create a new PCMWriter for this request
                    if t.request_id not in self.recorder_map:
                        dump_file_path = os.path.join(
                            self.config.dump_path,
                            f"murf_dump_{t.request_id}.pcm",
                        )
                        self.recorder_map[t.request_id] = PCMWriter(
                            dump_file_path
                        )
                        self.ten_env.log_debug(
                            f"Created PCMWriter for request_id: {t.request_id}, file: {dump_file_path}"
                        )

            if t.text in INVALID_TEXT_LIST:
                error_msg = f"Invalid text input: {t.text!r}"
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

            if t.text.strip() != "":
                self.sent_tts = True

            await self.client.send_text(t)

            if t.text_input_end:
                self.current_request_finished = True
                self.ten_env.log_debug(
                    f"text_input_end received for request ID: {t.request_id}"
                )

                if (
                    self.request_start_ts
                    and t.text.strip() == ""
                    and not self.sent_tts
                ):
                    # Empty text with text_input_end - finish immediately
                    await self._handle_tts_audio_end()
                    self.ten_env.log_debug(
                        f"Sent TTS audio end event, text is empty for request ID: {t.request_id}"
                    )

                self.last_completed_request_id = t.request_id
                self.ten_env.log_info(
                    f"Updated last completed request_id to: {t.request_id}"
                )

        except ModuleVendorException as e:
            self.sent_tts = False
            self.ten_env.log_error(
                f"ModuleVendorException in request_tts: {traceback.format_exc()}. text: {t.text}"
            )
            error = ModuleError(
                message=str(e),
                module=ModuleType.TTS,
                code=ModuleErrorCode.NON_FATAL_ERROR,
                vendor_info=e.error,
            )
            if self.current_request_finished or t.text_input_end:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
            else:
                await self.send_tts_error(
                    request_id=await self._get_current_request_id() or "",
                    error=error,
                )
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
            if self.current_request_finished or t.text_input_end:
                await self._handle_tts_audio_end(
                    reason=TTSAudioEndReason.ERROR, error=error
                )
            else:
                await self.send_tts_error(
                    request_id=await self._get_current_request_id() or "",
                    error=error,
                )

    async def cancel_tts(self) -> None:
        current_request_id = await self._get_current_request_id()
        if current_request_id:
            self.ten_env.log_debug(
                f"Current request {current_request_id} is being cancelled. Sending INTERRUPTED."
            )
            if self.client:
                self.client.cancel(current_request_id)
                self.last_completed_has_cleared_synthesizer = True

            # If there's a waiting stop_event, set it to release request_tts waiting
            if self.stop_event:
                self.stop_event.set()
                self.stop_event = None

            await self._handle_tts_audio_end(TTSAudioEndReason.INTERRUPTED)
            self.current_request_finished = True
        else:
            self.ten_env.log_warn(
                "No current request found, skipping TTS cancellation."
            )

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
