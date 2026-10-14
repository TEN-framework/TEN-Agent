from datetime import datetime
import json
import os
from typing import Any

from typing_extensions import override

from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_KEY_POINT,
)

from .const import (
    FINALIZE_MODE_DISCONNECT,
    FINALIZE_MODE_MUTE_PKG,
    DUMP_FILE_NAME,
    MODULE_NAME_ASR,
    FATAL_ERROR_CODES,
    AZURE_LANGUAGE_ID_MODE_KEY,
    DEFAULT_TRANSPORT_RECONNECT_GRACE_SEC,
    DEFAULT_TRANSPORT_HANDSHAKE_TIMEOUT_SEC,
    RECONNECT_MAX_ATTEMPTS,
)
from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorVendorInfo,
    ModuleErrorCode,
)
from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
)

import asyncio
import azure.cognitiveservices.speech as speechsdk
from .config import AzureASRConfig
from ten_ai_base.dumper import Dumper
from .reconnect_manager import ReconnectManager


class AzureASRExtension(AsyncASRBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.connected: bool = False
        self.client: speechsdk.SpeechRecognizer | None = None
        self.connection: speechsdk.Connection | None = None
        self.stream: speechsdk.audio.PushAudioInputStream | None = None
        self.config: AzureASRConfig | None = None
        self.audio_dumper: Dumper | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        self.connection_start_timestamp: int = 0

        # Reconnection manager with unlimited retries and backoff strategy
        self.reconnect_manager: ReconnectManager | None = None
        self._recognizer_epoch: int = 0
        # Session (recognizer) vs transport (Connection websocket) are separate on Azure.
        self._transport_connected: bool = False
        self._transport_connected_epoch: int = 0
        self._transport_recovery_task: asyncio.Task[None] | None = None
        self._transport_recovery_in_flight: bool = False
        self._reconnect_in_flight: bool = False
        self._expected_disconnect: bool = False
        self._expected_disconnect_reported: bool = False
        self._init_failed: bool = False
        self._transport_handshake_ready: asyncio.Event = asyncio.Event()
        self._finalize_reconnect_task: asyncio.Task[None] | None = None

    @override
    def vendor(self) -> str:
        return "microsoft"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        fields = {"key": self.config.key, "region": self.config.region}
        return {k: v for k, v in fields.items() if v}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        # Initialize reconnection manager
        self.reconnect_manager = ReconnectManager(
            logger=ten_env, max_attempts=RECONNECT_MAX_ATTEMPTS
        )

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            self.config = AzureASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)
            ten_env.log_info(
                f"config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
                await self.audio_dumper.start()
        except Exception as e:
            ten_env.log_error(
                f"invalid property: {e}", category=LOG_CATEGORY_KEY_POINT
            )
            self._init_failed = True
            self.config = AzureASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await self._cancel_finalize_reconnect()
        await self._cancel_transport_recovery()
        await super().on_deinit(ten_env)

        if self.audio_dumper:
            await self.audio_dumper.stop()

    @override
    async def start_connection(self) -> None:
        if self._init_failed:
            return
        assert self.config is not None
        self.ten_env.log_info("start_connection")
        self._expected_disconnect = False
        self._expected_disconnect_reported = False
        self._reset_transport_handshake_state()

        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=self.config.key, region=self.config.region
            )
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: start_connection failed: invalid vendor config: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            error = ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=str(e),
            )
            await self.send_asr_error(error)
            await self.on_disconnected(code=error.code, message=error.message)
            return

        stream_format = speechsdk.audio.AudioStreamFormat(
            channels=self.input_audio_channels(),
            samples_per_second=self.input_audio_sample_rate(),
            bits_per_sample=self.input_audio_sample_width() * 8,
            wave_stream_format=speechsdk.audio.AudioStreamWaveFormat.PCM,
        )

        self.stream = speechsdk.audio.PushAudioInputStream(
            stream_format=stream_format
        )
        audio_config = speechsdk.audio.AudioConfig(stream=self.stream)

        # Set the silence timeout to 100ms by default.
        speech_config.set_property(
            speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "100"
        )

        # Dump the Azure SDK log to the dump path if dump is enabled.
        if self.config.dump and self.config.dump_path:
            azure_log_file_path = os.path.join(
                self.config.dump_path, "azure_sdk.log"
            )
            speech_config.set_property(
                speechsdk.PropertyId.Speech_LogFilename, azure_log_file_path
            )

        language_id_mode_set_in_advanced = False
        if self.config.advanced_params_json:
            try:
                params: dict[str, str] = json.loads(
                    self.config.advanced_params_json
                )
                if AZURE_LANGUAGE_ID_MODE_KEY in params:
                    language_id_mode_set_in_advanced = True
                for key, value in params.items():
                    self.ten_env.log_debug(
                        f"set azure param: {key} = {value}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    speech_config.set_property_by_name(key, value)
            except Exception as e:
                self.ten_env.log_error(
                    f"vendor_error: set azure param failed: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )

        if len(self.config.language_list) > 1:
            if not language_id_mode_set_in_advanced:
                speech_config.set_property(
                    speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode,
                    "Continuous",
                )
            # Continuous mode is used to recognize the language of the audio in real time.
            # https://learn.microsoft.com/zh-cn/azure/ai-services/speech-service/language-identification?pivots=programming-language-python&tabs=once#recognize-once-or-continuous
            self.client = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config,
                auto_detect_source_language_config=speechsdk.AutoDetectSourceLanguageConfig(
                    languages=self.config.language_list
                ),
            )
        else:
            self.client = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config,
                language=self.config.primary_language(),
            )

        if len(self.config.phrase_list) > 0:
            phrase_list_grammar = speechsdk.PhraseListGrammar.from_recognizer(
                self.client
            )
            for phrase in self.config.phrase_list:
                phrase_list_grammar.addPhrase(phrase)

        self._recognizer_epoch += 1
        recognizer_epoch = self._recognizer_epoch
        await self._register_azure_event_handlers(recognizer_epoch)

        # Record timestamp before starting continuous recognition
        self.connection_start_timestamp = int(datetime.now().timestamp() * 1000)

        self.client.start_continuous_recognition()
        self.ten_env.log_debug("start_connection completed")

    @override
    async def finalize(self, session_id: str | None) -> None:
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        _ = self.ten_env.log_info(
            f"finalize start at {self.last_finalize_timestamp}]",
        )
        if self.config.finalize_mode == FINALIZE_MODE_DISCONNECT:
            await self._handle_finalize_disconnect()
        elif self.config.finalize_mode == FINALIZE_MODE_MUTE_PKG:
            await self._handle_finalize_mute_pkg()
        else:
            _ = self.ten_env.log_error(
                f"Unknown finalize mode: {self.config.finalize_mode}"
            )

    async def _register_azure_event_handlers(self, recognizer_epoch: int):
        loop = asyncio.get_running_loop()
        assert self.client is not None
        self.client.recognizing.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_recognizing(evt, recognizer_epoch),
            )
        )
        self.client.recognized.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_recognized(evt, recognizer_epoch),
            )
        )
        self.client.session_started.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_session_started(
                    evt, recognizer_epoch
                ),
            )
        )
        self.client.session_stopped.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_session_stopped(
                    evt, recognizer_epoch
                ),
            )
        )
        self.client.canceled.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_canceled(evt, recognizer_epoch),
            )
        )
        self.client.speech_start_detected.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_speech_start_detected(evt),
            )
        )
        self.client.speech_end_detected.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_speech_end_detected(evt),
            )
        )

        self.connection = speechsdk.Connection.from_recognizer(self.client)
        self.connection.connected.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_connected(evt, recognizer_epoch),
            )
        )
        self.connection.disconnected.connect(
            lambda evt: loop.call_soon_threadsafe(
                asyncio.create_task,
                self._azure_event_handler_on_disconnected(
                    evt, recognizer_epoch
                ),
            )
        )

    async def _handle_asr_result(
        self,
        text: str,
        final: bool,
        start_ms: int = 0,
        duration_ms: int = 0,
        language: str = "",
    ):
        """Handle the ASR result from Azure ASR."""
        assert self.config is not None

        if final:
            await self._finalize_end()

        asr_result = ASRResult(
            text=text,
            final=final,
            start_ms=start_ms,
            duration_ms=duration_ms,
            language=language,
            words=[],
        )

        await self.send_asr_result(asr_result)

    async def _azure_event_handler_on_recognizing(
        self, evt: speechsdk.SpeechRecognitionEventArgs, recognizer_epoch: int
    ):
        """Handle the recognizing event from Azure ASR."""
        if recognizer_epoch != self._recognizer_epoch:
            return

        assert self.config is not None

        text = evt.result.text
        start_ms = evt.result.offset // 10000
        duration_ms = evt.result.duration // 10000
        actual_start_ms = int(
            self.audio_timeline.get_audio_duration_before_time(start_ms)
            + self.sent_user_audio_duration_ms_before_last_reset
        )
        language = self.config.primary_language()
        if len(self.config.language_list) > 1:
            try:
                result_json = json.loads(evt.result.json)
                language_in_result: str = result_json["PrimaryLanguage"][
                    "Language"
                ]
                if language_in_result != "":
                    language = language_in_result
            except Exception as e:
                self.ten_env.log_error(
                    f"get language from result json failed: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )

        if evt.result.no_match_details:
            self.ten_env.log_error(
                f"vendor_error: azure event callback on_recognizing: no match details: {evt.result.no_match_details}",
                category=LOG_CATEGORY_VENDOR,
            )

        self.ten_env.log_debug(
            f"vendor_result: on_recognizing: {text}, language: {language}, full_json: {evt.result.json}",
            category=LOG_CATEGORY_VENDOR,
        )

        await self._handle_asr_result(
            text,
            final=False,
            start_ms=actual_start_ms,
            duration_ms=duration_ms,
            language=language,
        )

    async def _azure_event_handler_on_recognized(
        self, evt: speechsdk.SpeechRecognitionEventArgs, recognizer_epoch: int
    ):
        """Handle the recognized event from Azure ASR."""
        if recognizer_epoch != self._recognizer_epoch:
            return

        assert self.config is not None

        text = evt.result.text
        start_ms = evt.result.offset // 10000
        duration_ms = evt.result.duration // 10000
        actual_start_ms = int(
            self.audio_timeline.get_audio_duration_before_time(start_ms)
            + self.sent_user_audio_duration_ms_before_last_reset
        )
        language = self.config.primary_language()
        if len(self.config.language_list) > 1:
            try:
                result_json = json.loads(evt.result.json)
                language_in_result: str = result_json["PrimaryLanguage"][
                    "Language"
                ]
                if language_in_result != "":
                    language = language_in_result
            except Exception as e:
                self.ten_env.log_error(
                    f"get language from result json failed: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )

        if evt.result.no_match_details:
            self.ten_env.log_error(
                f"vendor_error: azure event callback on_recognized: no match details: {evt.result.no_match_details}",
                category=LOG_CATEGORY_VENDOR,
            )

        self.ten_env.log_debug(
            f"vendor_result: on_recognized: {text}, language: {language}, full_json: {evt.result.json}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._handle_asr_result(
            text,
            final=True,
            start_ms=actual_start_ms,
            duration_ms=duration_ms,
            language=language,
        )

    async def _azure_event_handler_on_session_started(
        self, evt: speechsdk.SessionEventArgs, recognizer_epoch: int
    ):
        """Handle the session started event from Azure ASR."""
        if recognizer_epoch != self._recognizer_epoch:
            return

        self.ten_env.log_debug(
            f"azure event callback on_session_started, session_id: {evt.session_id}"
        )
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()
        self.connected = True

    async def _azure_event_handler_on_session_stopped(
        self, evt: speechsdk.SessionEventArgs, recognizer_epoch: int
    ):
        """Handle the session stopped event from Azure ASR."""
        if recognizer_epoch != self._recognizer_epoch:
            self.ten_env.log_debug(
                f"ignore stale on_session_stopped, epoch {recognizer_epoch} != {self._recognizer_epoch}",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        if self._transport_recovery_in_flight:
            # stop_connection() inside recovery will drive session_stopped; transport
            # disconnected already reported vendor loss — do not start a second reconnect.
            self.ten_env.log_debug(
                "ignore on_session_stopped during transport recovery",
                category=LOG_CATEGORY_VENDOR,
            )
            self.connected = False
            return

        self.ten_env.log_info(
            f"vendor_status_changed: on_session_stopped, session_id: {evt.session_id}",
            category=LOG_CATEGORY_VENDOR,
        )
        self.connected = False

        expected_disconnect = self._expected_disconnect
        self._expected_disconnect = False
        if expected_disconnect:
            if not self._expected_disconnect_reported:
                await self.on_disconnected(code=0, message="closed")
            self._expected_disconnect_reported = False
            if not self.stopped:
                self._schedule_finalize_reconnect()
            return

        await self.on_disconnected(code=0, message="closed")
        if not self.stopped:
            self.ten_env.log_warn(
                "vendor_error: azure session stopped unexpectedly. Reconnecting...",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._request_unexpected_reconnect(immediate=True)

    async def _azure_event_handler_on_canceled(
        self,
        evt: speechsdk.SpeechRecognitionCanceledEventArgs,
        recognizer_epoch: int,
    ):
        """Handle the canceled event from Azure ASR."""
        if recognizer_epoch != self._recognizer_epoch:
            return

        cancellation_details = evt.cancellation_details

        if cancellation_details.reason != speechsdk.CancellationReason.Error:
            self.ten_env.log_info(
                f"vendor_status_changed: canceled, reason: {cancellation_details.reason}",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        self.ten_env.log_error(
            f"vendor_error: code: {cancellation_details.code}, reason: {cancellation_details.reason}, error_details: {cancellation_details.error_details}",
            category=LOG_CATEGORY_VENDOR,
        )

        is_fatal = cancellation_details.code in FATAL_ERROR_CODES

        if is_fatal:
            # Stop retrying for fatal errors
            self.stopped = True

        vendor_info = ModuleErrorVendorInfo(
            vendor=self.vendor(),
            code=str(cancellation_details.code),
            message=cancellation_details.error_details,
        )

        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=(
                    ModuleErrorCode.FATAL_ERROR.value
                    if is_fatal
                    else ModuleErrorCode.NON_FATAL_ERROR.value
                ),
                message=cancellation_details.error_details,
            ),
            vendor_info,
        )

        await self.on_disconnected(
            code=(
                ModuleErrorCode.FATAL_ERROR.value
                if is_fatal
                else ModuleErrorCode.NON_FATAL_ERROR.value
            ),
            message=cancellation_details.error_details,
            vendor_info=vendor_info,
        )

    async def _azure_event_handler_on_speech_start_detected(
        self, evt: speechsdk.RecognitionEventArgs
    ):
        """Handle the speech start detected event from Azure ASR."""
        self.ten_env.log_debug(
            f"azure event callback on_speech_start_detected, session_id: {evt.session_id}",
            category=LOG_CATEGORY_VENDOR,
        )

    async def _azure_event_handler_on_speech_end_detected(
        self, evt: speechsdk.RecognitionEventArgs
    ):
        """Handle the speech end detected event from Azure ASR."""
        self.ten_env.log_debug(
            f"azure event callback on_speech_end_detected, session_id: {evt.session_id}",
            category=LOG_CATEGORY_VENDOR,
        )

    def _connected_callback_may_publish(self, recognizer_epoch: int) -> bool:
        return not self.stopped and recognizer_epoch == self._recognizer_epoch

    def _discard_stale_connected_callback(self, recognizer_epoch: int) -> None:
        if self._transport_connected_epoch == recognizer_epoch:
            self._reset_transport_handshake_state()

    async def _azure_event_handler_on_connected(
        self, evt: speechsdk.ConnectionEventArgs, recognizer_epoch: int
    ):
        """Handle the connected event from Azure ASR."""
        if not self._connected_callback_may_publish(recognizer_epoch):
            return

        self._transport_connected = True
        self._transport_connected_epoch = recognizer_epoch
        self._transport_handshake_ready.set()
        await self._cancel_transport_recovery()
        if not self._connected_callback_may_publish(recognizer_epoch):
            self._discard_stale_connected_callback(recognizer_epoch)
            return

        connection_delay_ms = (
            int(datetime.now().timestamp() * 1000)
            - self.connection_start_timestamp
        )

        self.ten_env.log_info(
            f"vendor_status_changed: on_connected, session_id: {evt.session_id}, connection_delay_ms: {connection_delay_ms}",
            category=LOG_CATEGORY_VENDOR,
        )

        await self.send_connect_delay_metrics(connection_delay_ms)
        if not self._connected_callback_may_publish(recognizer_epoch):
            self._discard_stale_connected_callback(recognizer_epoch)
            return

        # Notify reconnect manager that connection is successful
        if self.reconnect_manager:
            self.reconnect_manager.mark_connection_successful()

        await self.on_connected()

    async def _azure_event_handler_on_disconnected(
        self, evt: speechsdk.ConnectionEventArgs, recognizer_epoch: int
    ):
        """Handle the disconnected event from Azure ASR."""
        if recognizer_epoch != self._recognizer_epoch:
            return

        self.ten_env.log_info(
            f"vendor_status_changed: on_disconnected, session_id: {evt.session_id}",
            category=LOG_CATEGORY_VENDOR,
        )
        self._transport_connected = False
        if self._expected_disconnect:
            if not self._expected_disconnect_reported:
                await self.on_disconnected(code=0, message="closed")
                self._expected_disconnect_reported = True
            return

        await self.on_disconnected(code=0, message="closed")
        if not self.stopped:
            await self._request_unexpected_reconnect(immediate=False)

    async def _cancel_transport_recovery(self) -> None:
        task = self._transport_recovery_task
        self._transport_recovery_task = None
        if task is asyncio.current_task():
            return
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _request_unexpected_reconnect(self, *, immediate: bool) -> None:
        """Single extension entry for reconnect after unexpected vendor loss."""
        if self.stopped or self._reconnect_in_flight:
            return
        if immediate:
            await self._cancel_transport_recovery()
            await self._handle_reconnect()
            return
        await self._schedule_transport_recovery()

    async def _schedule_transport_recovery(self) -> None:
        if self.stopped or self._transport_recovery_in_flight:
            return

        await self._cancel_transport_recovery()
        if self.stopped:
            return

        recognizer_epoch = self._recognizer_epoch
        task = asyncio.create_task(
            self._transport_recovery_after_grace(recognizer_epoch)
        )
        self._transport_recovery_task = task
        task.add_done_callback(self._clear_transport_recovery_task)

    def _clear_transport_recovery_task(self, task: asyncio.Task[None]) -> None:
        if self._transport_recovery_task is task:
            self._transport_recovery_task = None

    def _grace_sec(self) -> float:
        if self.config is None:
            return float(DEFAULT_TRANSPORT_RECONNECT_GRACE_SEC)
        return float(self.config.transport_reconnect_grace_sec)

    async def _transport_recovery_after_grace(
        self, scheduled_epoch: int
    ) -> None:
        grace_sec = self._grace_sec()
        await asyncio.sleep(grace_sec)

        if (
            self.stopped
            or self._transport_connected
            or self._reconnect_in_flight
            or scheduled_epoch != self._recognizer_epoch
        ):
            return

        self.ten_env.log_warn(
            "vendor_error: Azure transport disconnected and SDK did not reconnect "
            f"within {grace_sec}s. Reconnecting...",
            category=LOG_CATEGORY_VENDOR,
        )
        self._transport_recovery_in_flight = True
        try:
            await self.stop_connection()
            if self.stopped:
                return
            await self._handle_reconnect()
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: transport recovery failed: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
        finally:
            self._transport_recovery_in_flight = False

        if (
            not self.stopped
            and not self._transport_connected
            and not self._reconnect_in_flight
        ):
            if self.reconnect_manager and self.reconnect_manager.can_retry():
                await self._schedule_transport_recovery()
            else:
                await self._emit_reconnect_ceiling_fatal()

    async def _handle_finalize_disconnect(self):
        assert self.config is not None

        if self.client is None:
            _ = self.ten_env.log_debug(
                "finalize disconnect: client is not connected"
            )
            return

        await self._cancel_transport_recovery()
        self._expected_disconnect = True
        self._expected_disconnect_reported = False
        self.connected = False
        self._transport_connected = False

        # Close the stream first so the SDK pump thread exits cleanly
        # before calling stop_continuous_recognition.
        if self.stream is not None:
            self.stream.close()
            self.stream = None

        self.client.stop_continuous_recognition()
        _ = self.ten_env.log_debug("finalize disconnect completed")

    async def _handle_finalize_mute_pkg(self):
        assert self.config is not None

        if self.stream is None:
            _ = self.ten_env.log_debug(
                "finalize mute pkg: stream is not initialized"
            )
            return

        empty_audio_bytes_len = int(
            self.config.mute_pkg_duration_ms
            * self.config.sample_rate
            / 1000
            * 2
        )
        frame = bytearray(empty_audio_bytes_len)
        self.stream.write(bytes(frame))
        self.audio_timeline.add_silence_audio(self.config.mute_pkg_duration_ms)
        self.ten_env.log_debug("finalize mute pkg completed")

    def _reset_transport_handshake_state(self) -> None:
        self._transport_connected = False
        self._transport_connected_epoch = 0
        self._transport_handshake_ready.clear()

    def _handshake_timeout_sec(self) -> float:
        return float(DEFAULT_TRANSPORT_HANDSHAKE_TIMEOUT_SEC)

    def _transport_handshake_complete(self, expected_epoch: int) -> bool:
        return (
            self._transport_connected
            and self._transport_connected_epoch == expected_epoch
            and self._recognizer_epoch == expected_epoch
        )

    async def _wait_for_transport_handshake(self, expected_epoch: int) -> bool:
        if self._transport_handshake_complete(expected_epoch):
            return True
        timeout_sec = self._handshake_timeout_sec()
        try:
            await asyncio.wait_for(
                self._transport_handshake_ready.wait(), timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            self.ten_env.log_warn(
                f"vendor_error: Azure transport handshake timed out after "
                f"{timeout_sec}s (expected epoch {expected_epoch})",
                category=LOG_CATEGORY_VENDOR,
            )
            return False
        return self._transport_handshake_complete(expected_epoch)

    async def _teardown_failed_handshake_attempt(self, message: str) -> None:
        """Vendor start returned without a usable transport handshake."""
        await self.stop_connection()
        if self.stopped:
            return
        await self.on_disconnected(
            code=ModuleErrorCode.NON_FATAL_ERROR.value,
            message=message,
        )

    async def _emit_reconnect_ceiling_fatal(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        message = "Azure ASR reconnect attempts exhausted"
        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=message,
            ),
        )

    async def _cancel_finalize_reconnect(self) -> None:
        task = self._finalize_reconnect_task
        self._finalize_reconnect_task = None
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    def _schedule_finalize_reconnect(self) -> None:
        if self.stopped:
            return
        task = self._finalize_reconnect_task
        if task is not None and not task.done():
            return
        task = asyncio.create_task(self._reconnect_after_finalize())
        self._finalize_reconnect_task = task
        task.add_done_callback(self._clear_finalize_reconnect_task)

    def _clear_finalize_reconnect_task(self, task: asyncio.Task[None]) -> None:
        if self._finalize_reconnect_task is task:
            self._finalize_reconnect_task = None

    async def _reconnect_after_finalize(self) -> None:
        if self.stopped:
            return
        try:
            await self.stop_connection()
            if self.stopped:
                return
            await self.start_connection()
            expected_epoch = self._recognizer_epoch
            if not await self._wait_for_transport_handshake(expected_epoch):
                await self._teardown_failed_handshake_attempt(
                    "Azure transport handshake timed out after finalize reconnect"
                )
                if not self.stopped and self.reconnect_manager:
                    if self.reconnect_manager.can_retry():
                        await self._handle_reconnect()
                    else:
                        await self._emit_reconnect_ceiling_fatal()
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: post-finalize reconnect failed: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            if not self.stopped:
                await self._request_unexpected_reconnect(immediate=True)

    async def _handle_reconnect(self) -> bool:
        """
        Handle a single reconnection attempt using the ReconnectManager.
        Returns True only after the vendor transport handshake completes.
        """
        if self._reconnect_in_flight:
            self.ten_env.log_debug("reconnect already in flight")
            return False

        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return False

        if not self.reconnect_manager.can_retry():
            await self._emit_reconnect_ceiling_fatal()
            return False

        self._reconnect_in_flight = True
        try:
            initiated = await self.reconnect_manager.handle_reconnect(
                connection_func=self.start_connection,
                error_handler=self.send_asr_error,
            )

            if not initiated:
                info = self.reconnect_manager.get_attempts_info()
                self.ten_env.log_debug(
                    f"Reconnection attempt failed. Status: {info}"
                )
                return False

            expected_epoch = self._recognizer_epoch
            if await self._wait_for_transport_handshake(expected_epoch):
                self.ten_env.log_debug("Reconnection handshake completed")
                return True

            await self._teardown_failed_handshake_attempt(
                "Azure transport handshake timed out during reconnect"
            )
            info = self.reconnect_manager.get_attempts_info()
            self.ten_env.log_debug(
                f"Reconnection handshake failed. Status: {info}"
            )
            return False
        finally:
            self._reconnect_in_flight = False

    async def _finalize_end(self) -> None:
        if self.last_finalize_timestamp != 0:
            timestamp = int(datetime.now().timestamp() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_info(
                f"finalize end at {timestamp}, counter: {latency}"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    @override
    async def stop_connection(self) -> None:
        finalize_task = self._finalize_reconnect_task
        if finalize_task is not asyncio.current_task():
            await self._cancel_finalize_reconnect()
        await self._cancel_transport_recovery()
        self.connected = False
        # Retire callbacks from the recognizer being torn down before stop returns.
        self._recognizer_epoch += 1
        self._reset_transport_handshake_state()

        if self.stream:
            self.stream.close()
            self.stream = None

        if self.client:
            start_ms = int(datetime.now().timestamp() * 1000)
            self.client.stop_continuous_recognition()
            stop_ms = int(datetime.now().timestamp() * 1000)
            stop_duration_ms = stop_ms - start_ms
            self.client = None

            self.ten_env.log_info(
                f"stop_continuous_recognition took {stop_duration_ms}ms"
            )
            await self.send_vendor_metrics(
                {"stop_continuous_recognition_ms": stop_duration_ms}
            )

        self.connection = None
        self.ten_env.log_info("azure connection stopped")

    @override
    def is_connected(self) -> bool:
        return (
            self.connected
            and self._transport_connected
            and self.client is not None
        )

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None

        return self.config.sample_rate

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        assert self.config is not None

        if self.stream is None:
            self.ten_env.log_warn("stream is not initialized")
            return False

        buf = frame.get_buf()
        if self.audio_dumper:
            await self.audio_dumper.push_bytes(bytes(buf))
        self.audio_timeline.add_user_audio(
            int(len(buf) / (self.config.sample_rate / 1000 * 2))
        )
        self.stream.write(bytes(buf))

        return True
