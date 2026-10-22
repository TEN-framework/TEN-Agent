#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import time
from typing_extensions import override
from pathlib import Path

from ten_runtime import (
    AudioFrame,
    AsyncTenEnv,
)
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_ai_base.asr import (
    ASRResult,
    AsyncASRBaseExtension,
    ASRBufferConfig,
    ASRBufferConfigModeDiscard,
)

from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_TRANSCRIPTS,
)

from ten_ai_base.struct import ASRWord
from ten_ai_base.dumper import Dumper

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.model import StartStreamTranscriptionEventStream
from amazon_transcribe.model import TranscriptEvent

from .config import AWSASRConfig
from .reconnect_manager import ReconnectManager


class AWSASRExtension(AsyncASRBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.client: TranscribeStreamingClient | None = None
        self.stream: StartStreamTranscriptionEventStream | None = None
        self.config: AWSASRConfig | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        self.audio_dumper: Dumper | None = None
        self.connected: bool = False
        self.reconnect_manager: ReconnectManager | None = None

    @override
    def vendor(self) -> str:
        return "amazon"

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        config_json, _ = await ten_env.get_property_to_json()
        dump_file_path = None
        try:
            self.config = AWSASRConfig.model_validate_json(config_json)
            ten_env.log_info(
                f"config: {self.config.model_dump_json()}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if self.config.dump:
                dump_file_path = Path(self.config.dump_path)
                if dump_file_path.suffix != ".pcm":
                    dump_file_path = dump_file_path / "aws_asr_in.pcm"
                dump_file_path.parent.mkdir(parents=True, exist_ok=True)
                self.audio_dumper = Dumper(str(dump_file_path))
                await self.audio_dumper.start()
        except Exception as e:
            ten_env.log_error(
                f"invalid property: {e}", category=LOG_CATEGORY_KEY_POINT
            )
            self.config = None
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

        # Initialize reconnection manager
        self.reconnect_manager = ReconnectManager(logger=ten_env)
        self.audio_timeline.reset()

    @override
    async def start_connection(self) -> None:
        assert self.config is not None
        self.connected = False

        try:
            self.client = TranscribeStreamingClient(
                **self.config.params.to_client_params()
            )
            self.ten_env.log_info(
                "vendor_status_changed: AWS ASR client started",
                category=LOG_CATEGORY_VENDOR,
            )
            self.sent_user_audio_duration_ms_before_last_reset += (
                self.audio_timeline.get_total_user_audio_duration()
            )
            self.audio_timeline.reset()
            self.last_finalize_timestamp = 0
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: failed to create AWS ASR client {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )
        assert self.client is not None

        try:
            self.stream = await self.client.start_stream_transcription(
                **self.config.params.to_transcription_params()
            )
            self.connected = True
            if self.reconnect_manager:
                self.reconnect_manager.mark_connection_successful()
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: failed to start stream transcription {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            self.config = None
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(e),
                ),
                ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code="1000",
                    message=str(e),
                ),
            )

        async def _handle_events():
            try:
                if self.stream is None:
                    raise RuntimeError("stream is None")
                async for event in self.stream.output_stream:
                    if isinstance(event, TranscriptEvent):
                        try:
                            await self._handle_transcript_event(event)
                        except Exception as e:
                            self.ten_env.log_error(
                                f"vendor_error: failed to handle transcript event {e}",
                                category=LOG_CATEGORY_VENDOR,
                            )
                            await self.send_asr_error(
                                ModuleError(
                                    module="asr",
                                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                                    message=str(e),
                                ),
                            )
            except Exception as e:
                self.ten_env.log_info(
                    f"vendor_status_changed: stream closed, exception: {e}",
                    category=LOG_CATEGORY_VENDOR,
                )
                self.connected = False
                await self._reconnect_aws()

        asyncio.create_task(_handle_events())

    @override
    def is_connected(self) -> bool:
        return (
            self.stream is not None
            and not self.stream.input_stream._input_stream.closed  # pylint: disable=protected-access
            and self.connected
        )

    @override
    async def stop_connection(self) -> None:
        await self._disconnect_aws()
        if self.audio_dumper:
            await self.audio_dumper.stop()

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return self.config.params.media_sample_rate_hz

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        assert self.stream is not None
        try:
            buf = frame.lock_buf()
            if self.audio_dumper:
                await self.audio_dumper.push_bytes(bytes(buf))
            self.audio_timeline.add_user_audio(
                int(len(buf) / (self.input_audio_sample_rate() / 1000 * 2))
            )
            await self.stream.input_stream.send_audio_event(
                audio_chunk=bytes(buf)
            )
        except IOError as e:
            # when the stream is closed, it will raise IOError, we need to reconnect
            self.ten_env.log_error(
                f"vendor_error: failed to send audio {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            self.connected = False
            await self._reconnect_aws()
            return False
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: failed to send audio {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            return False

        finally:
            frame.unlock_buf(buf)

        return True

    @override
    async def finalize(self, session_id: str | None) -> None:
        if not self.is_connected():
            return None
        assert self.config is not None
        assert self.client is not None
        assert self.stream is not None

        self.last_finalize_timestamp = int(time.time() * 1000)
        _ = self.ten_env.log_debug(
            f"finalize start at {self.last_finalize_timestamp}]"
        )
        if self.config.params.finalize_mode == "disconnect":
            await self._handle_finalize_disconnect()
        elif self.config.params.finalize_mode == "mute_pkg":
            await self._handle_finalize_mute_pkg()
        else:
            raise ValueError(
                f"invalid finalize mode: {self.config.params.finalize_mode}"
            )

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeDiscard()

    async def _handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        self.ten_env.log_debug(
            f"vendor_result: transcript_event: {results}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )
        assert self.config is not None
        for result in results:
            if (
                result is None
                or result.alternatives is None
                or len(result.alternatives) == 0
            ):
                continue

            # send finalize end if the result is not partial and the last finalize timestamp is not 0
            if not result.is_partial and self.last_finalize_timestamp > 0:
                timestamp = int(time.time() * 1000)
                latency = timestamp - self.last_finalize_timestamp
                self.ten_env.log_debug(
                    f"finalize end at {timestamp}, counter: {latency}"
                )
                self.last_finalize_timestamp = 0
                await self.send_asr_finalize_end()

            alt = result.alternatives[0]
            items = alt.items
            words = []
            for item in items:
                if item.content is not None and len(item.content) > 0:
                    stable = item.stable
                    if stable is None:
                        stable = False
                    start_ms = (
                        int(item.start_time * 1000)
                        if item.start_time is not None
                        else 0
                    )
                    duration_ms = (
                        int((item.end_time - item.start_time) * 1000)
                        if item.end_time is not None
                        and item.start_time is not None
                        else 0
                    )
                    actual_start_ms = int(
                        self.audio_timeline.get_audio_duration_before_time(
                            start_ms
                        )
                        + self.sent_user_audio_duration_ms_before_last_reset
                    )

                    words.append(
                        ASRWord(
                            word=item.content,
                            start_ms=start_ms,
                            duration_ms=duration_ms,
                            stable=stable,
                        )
                    )

            # timestamp processing
            start_ms = (
                int(result.start_time * 1000)
                if result.start_time is not None
                else 0
            )
            duration_ms = (
                int((result.end_time - result.start_time) * 1000)
                if result.end_time is not None and result.start_time is not None
                else 0
            )

            actual_start_ms = int(
                self.audio_timeline.get_audio_duration_before_time(start_ms)
                + self.sent_user_audio_duration_ms_before_last_reset
            )

            await self.send_asr_result(
                asr_result=ASRResult(
                    text=alt.transcript,
                    final=not result.is_partial,
                    start_ms=actual_start_ms,
                    duration_ms=duration_ms,
                    language=self.config.params.language_code,
                    words=words,
                )
            )

    async def _disconnect_aws(self):
        try:
            if self.stream:
                await self.stream.input_stream.end_stream()
        except Exception:
            # ignore this error, it's normal when the stream is closed
            ...

        self.client = None
        self.stream = None
        self.connected = False

    async def _reconnect_aws(self):
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return

        # Check if we can still retry
        if not self.reconnect_manager.can_retry():
            self.ten_env.log_warn("No more reconnection attempts allowed")
            return

        # Attempt a single reconnection
        success = await self.reconnect_manager.handle_reconnect(
            connection_func=self.start_connection,
            error_handler=self.send_asr_error,
        )
        if success:
            self.ten_env.log_debug(
                "Reconnection attempt initiated successfully"
            )
        else:
            info = self.reconnect_manager.get_attempts_info()
            self.ten_env.log_debug(
                f"Reconnection attempt failed. Status: {info}"
            )

    async def _handle_finalize_disconnect(self):
        if not self.is_connected():
            _ = self.ten_env.log_debug(
                "finalize disconnect: client is not connected"
            )
            return

        assert self.stream is not None
        await self.stream.input_stream.end_stream()
        _ = self.ten_env.log_debug("finalize disconnect completed")

    async def _handle_finalize_mute_pkg(self):
        assert self.config is not None
        if not self.is_connected():
            _ = self.ten_env.log_debug(
                "finalize disconnect: client is not connected"
            )
            return
        assert self.stream is not None
        empty_audio_bytes_len = int(
            self.config.params.mute_pkg_duration_ms
            * self.input_audio_sample_rate()
            / 1000
            * 2
        )
        frame = bytearray(empty_audio_bytes_len)
        await self.stream.input_stream.send_audio_event(
            audio_chunk=bytes(frame)
        )
        self.audio_timeline.add_silence_audio(
            self.config.params.mute_pkg_duration_ms
        )
        self.ten_env.log_debug("finalize mute pkg completed")
