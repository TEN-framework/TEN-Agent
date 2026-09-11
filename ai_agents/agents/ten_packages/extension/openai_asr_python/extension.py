#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
import time
from typing import Any
from typing_extensions import override
from pathlib import Path
import samplerate
import numpy as np

from ten_runtime import (
    AudioFrame,
    AsyncTenEnv,
)
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorVendorInfo,
    ModuleErrorCode,
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
)

from .openai_asr_client import (
    OpenAIAsrClient,
    AsyncOpenAIAsrListener,
    TranscriptionParam,
    TranscriptionResultDelta,
    TranscriptionResultCompleted,
    TranscriptionResultCommitted,
    Error,
    Session,
)
from .openai_asr_client.schemas import build_ga_session_update
from .config import OpenAIASRConfig
from ten_ai_base.dumper import Dumper


class OpenAIASRExtension(AsyncASRBaseExtension, AsyncOpenAIAsrListener):
    def __init__(self, name: str):
        super().__init__(name)
        self.client: OpenAIAsrClient | None = None
        self.config: OpenAIASRConfig | None = None
        self.transcription_param: TranscriptionParam | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        self.audio_dumper: Dumper | None = None
        self.incompleted_transcript: str = ""
        self.resampler = samplerate.Resampler("sinc_best")

    @override
    def vendor(self) -> str:
        return "openai"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        transcription = self.config.params.model_dump().get(
            "input_audio_transcription", {}
        )
        model = (
            transcription.get("model")
            if isinstance(transcription, dict)
            else None
        )
        return {"model": model} if model else {}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        config_json, _ = await ten_env.get_property_to_json()
        dump_file_path = None
        try:
            self.config = OpenAIASRConfig.model_validate_json(config_json)
            self.transcription_param = (
                self.config.params.to_transcription_param()
            )
            ten_env.log_info(
                f"config: {self.config.model_dump_json()}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if self.config.dump:
                dump_file_path = Path(self.config.dump_path)
                if dump_file_path.suffix != ".pcm":
                    dump_file_path = dump_file_path / "openai_asr_in.pcm"
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

        assert self.config is not None
        assert self.transcription_param is not None

        try:
            log_path = None
            if dump_file_path is not None:
                log_path = str(dump_file_path.parent)
            self.client = OpenAIAsrClient(
                params=self.transcription_param,
                api_key=self.config.params.api_key,
                organization=self.config.params.organization,
                project=self.config.params.project,
                base_url=self.config.params.base_url,
                listener=self,
                log_level=self.config.params.log_level,
                log_path=log_path,
            )
            self.ten_env.log_info(
                "vendor_status_changed: OpenAI ASR client started",
                category=LOG_CATEGORY_VENDOR,
            )
            self.audio_timeline.reset()
            self.sent_user_audio_duration_ms_before_last_reset = 0
            self.last_finalize_timestamp = 0
        except Exception as e:
            ten_env.log_error(
                f"vendor_error: failed to create OpenAIAsrClient {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            self.config = None
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def start_connection(self) -> None:
        if self.client is None:
            return
        asyncio.create_task(self.client.start())

    @override
    def is_connected(self) -> bool:
        return (
            self.client is not None
            and self.client.is_connected()
            and self.client.is_ready()
        )

    @override
    async def stop_connection(self) -> None:
        if self.client:
            await self.client.stop()
        if self.audio_dumper:
            await self.audio_dumper.stop()

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return self.config.params.sample_rate

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        if not self.is_connected():
            return False
        assert self.client is not None
        try:
            # openai only supports 24000hz
            buf = frame.lock_buf()
            if self.input_audio_sample_rate() != 24000:
                input_data = np.frombuffer(buf, dtype=np.int16).astype(
                    np.float32
                )
                ratio = 24000 / self.input_audio_sample_rate()
                resampled_data = self.resampler.process(input_data, ratio)
                output_buffer = resampled_data.astype(np.int16).tobytes()
            else:
                output_buffer = bytes(buf)

            if self.audio_dumper:
                await self.audio_dumper.push_bytes(bytes(buf))
            self.audio_timeline.add_user_audio(
                int(len(buf) / (self.input_audio_sample_rate() / 1000 * 2))
            )
            await self.client.send_pcm_data(output_buffer)
        except Exception as e:
            self.ten_env.log_error(f"failed to send audio: {e}")
            return False
        finally:
            frame.unlock_buf(buf)
        return True

    @override
    async def finalize(self, session_id: str | None) -> None:
        if not self.is_connected():
            return None
        assert self.client is not None
        assert self.config is not None

        self.last_finalize_timestamp = int(time.time() * 1000)
        _ = self.ten_env.log_debug(
            f"finalize start at {self.last_finalize_timestamp}]"
        )
        await self.client.send_end_of_stream()

    # openai asr client event handler
    @override
    async def on_asr_start(self, response: Session[TranscriptionParam]):
        ga_payload = build_ga_session_update(response.session)
        self.ten_env.log_info(
            f"vendor_status_changed: on_asr_start {json.dumps(ga_payload)}",
            category=LOG_CATEGORY_VENDOR,
        )
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()

    @override
    async def on_asr_server_error(self, response: Session[Error]):
        self.ten_env.log_error(
            f"vendor_error: on_asr_server_error {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )

        await self.send_asr_error(
            ModuleError(
                module="asr",
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=response.session.message or "unknown error",
                vendor_info=ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code=str(response.session.code),
                    message=str(response.session),
                ),
            ),
        )

    @override
    async def on_asr_client_error(
        self, response: Any, error: Exception | None = None
    ):
        self.ten_env.log_error(
            f"vendor_error: on_asr_client_error {str(error)}",
            category=LOG_CATEGORY_VENDOR,
        )

        await self.send_asr_error(
            ModuleError(
                module="asr",
                code=ModuleErrorCode.FATAL_ERROR.value,
                message=str(error),
            ),
        )

    def _get_language(self) -> str:
        assert self.transcription_param is not None
        language = self.transcription_param.input_audio_transcription.get(
            "language", "en"
        )

        language_to_iso_639_1 = {
            "zh": "zh-CN",
            "en": "en-US",
            "ja": "ja-JP",
            "fr": "fr-FR",
            "de": "de-DE",
        }

        return language_to_iso_639_1.get(language, language) or "en-US"

    @override
    async def on_asr_delta(self, response: TranscriptionResultDelta):
        self.ten_env.log_info(
            f"vendor_result: on_asr_delta: {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        self.incompleted_transcript += response.delta

        # TODO: duration_ms, start_ms is not correct
        asr_result = ASRResult(
            id=response.event_id,
            text=self.incompleted_transcript,
            final=False,
            start_ms=0,
            duration_ms=10,
            language=self._get_language(),
            words=[],
        )

        await self.send_asr_result(asr_result)

    @override
    async def on_asr_completed(self, response: TranscriptionResultCompleted):
        self.ten_env.log_debug(
            f"vendor_result: on_asr_completed: {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        if self.last_finalize_timestamp != 0:
            timestamp = int(time.time() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_debug(
                f"finalize end at {timestamp}, counter: {latency}"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

        # TODO: duration_ms, start_ms is not correct
        duration_ms = 10
        if response.usage is not None and response.usage.seconds is not None:
            duration_ms = int(response.usage.seconds * 1000)

        asr_result = ASRResult(
            id=response.event_id,
            text=response.transcript,
            final=True,
            start_ms=0,
            duration_ms=duration_ms,
            language=self._get_language(),
            words=[],
        )

        self.incompleted_transcript = ""

        await self.send_asr_result(asr_result)

    @override
    async def on_asr_committed(self, response: TranscriptionResultCommitted):
        self.ten_env.log_info(
            f"vendor_result: on_asr_committed: {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )

        self.incompleted_transcript = ""

    @override
    async def on_other_event(self, response: dict):
        self.ten_env.log_info(
            f"vendor_result: on_other_event: {response}",
            category=LOG_CATEGORY_VENDOR,
        )

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeDiscard()
