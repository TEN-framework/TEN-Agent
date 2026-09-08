#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import time
from typing import Any
from typing_extensions import override
from pathlib import Path

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
    ASRBufferConfigModeKeep,
)

from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_KEY_POINT,
)

from .tencent_asr_client import (
    TencentAsrClient,
    AsyncTencentAsrListener,
    ResponseData,
    RecoginizeResult,
)
from .config import TencentASRConfig, RequestParams
from .reconnect_manager import ReconnectManager
from ten_ai_base.dumper import Dumper


class TencentASRExtension(AsyncASRBaseExtension, AsyncTencentAsrListener):
    def __init__(self, name: str):
        super().__init__(name)
        self.client: TencentAsrClient | None = None
        self.listener: AsyncTencentAsrListener | None = None
        self.config: TencentASRConfig | None = None
        self.request_params: RequestParams | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        self.audio_dumper: Dumper | None = None
        self.reconnect_manager: ReconnectManager | None = None
        self._skip_close_reconnect: bool = False

    # 9998: WebSocket transport errors (connect/send/recv). Session is dead.
    # 9999: TencentAsrClient message parse errors. Connection stays open.
    _WEBSOCKET_ERROR_CODE = 9998
    _CLIENT_PARSE_ERROR_CODE = 9999

    @classmethod
    def _is_reconnectable_asr_error(cls, error_code: int) -> bool:
        return error_code == cls._WEBSOCKET_ERROR_CODE

    @override
    def vendor(self) -> str:
        return "tencent"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None or self.request_params is None:
            return {}
        metadata: dict[str, Any] = {}
        if self.request_params.appid:
            metadata["appid"] = self.request_params.appid
        if self.request_params.secretid:
            metadata["key"] = self.request_params.secretid
        url = self.request_params.base_uri()
        if url:
            metadata["url"] = url
        if self.request_params.engine_model_type:
            metadata["model"] = self.request_params.engine_model_type
        return metadata

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_init")

        await super().on_init(ten_env)
        self.reconnect_manager = ReconnectManager(logger=ten_env)
        config_json, _ = await ten_env.get_property_to_json()
        dump_file_path = None
        try:
            self.config = TencentASRConfig.model_validate_json(config_json)
            self.request_params = self.config.params.to_request_params()
            ten_env.log_info(
                f"config: {self.config.model_dump_json()}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if self.config.dump:
                dump_file_path = Path(self.config.dump_path)
                if dump_file_path.is_dir():
                    dump_file_path = dump_file_path / "tencent_asr_in.pcm"
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

        if self.config is None:
            self.ten_env.log_error(
                "config is None, skip init", category=LOG_CATEGORY_KEY_POINT
            )
            return

        try:
            log_path = None
            if dump_file_path is not None:
                log_path = str(dump_file_path.parent)
            assert self.request_params is not None
            self.client = TencentAsrClient(
                params=self.request_params,
                keep_alive_interval=self.config.params.keep_alive_interval,
                keep_alive_data=b"",
                listener=self,
                log_level=self.config.params.log_level,
                log_path=log_path,
                auto_reconnect=False,
            )
            self.ten_env.log_info(
                "vendor_status_changed: Tencent ASR client started",
                category=LOG_CATEGORY_VENDOR,
            )
            self.audio_timeline.reset()
            self.sent_user_audio_duration_ms_before_last_reset = 0
            self.last_finalize_timestamp = 0
        except Exception as e:
            self.ten_env.log_error(
                f"vendor_error: failed to create TencentAsrClient {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def start_connection(self) -> None:
        if self.stopped:
            return
        if self.client is None:
            error = ModuleError(
                module="asr",
                code=ModuleErrorCode.FATAL_ERROR.value,
                message="Tencent ASR client not initialized",
            )
            await self.send_asr_error(error)
            await self.on_disconnected(code=error.code, message=error.message)
            return
        asyncio.create_task(self._restart_client())

    async def _restart_client(self) -> None:
        if self.stopped or self.client is None:
            return
        if self.client.is_running():
            await self.client.stop()
        if not self.stopped:
            asyncio.create_task(self.client.start())

    @override
    def is_connected(self) -> bool:
        return self.client is not None and self.client.is_connected()

    @override
    async def stop_connection(self) -> None:
        if self.client:
            await self.client.stop()
        if self.audio_dumper:
            await self.audio_dumper.stop()

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.request_params is not None
        if self.config is None:
            return 16000
        sample_rate = self.request_params.input_sample_rate
        if sample_rate is None:
            return 16000
        return sample_rate

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        if not self.is_connected():
            return False
        assert self.client is not None

        try:
            buf = frame.get_buf()
            if self.audio_dumper:
                await self.audio_dumper.push_bytes(bytes(buf))
            self.audio_timeline.add_user_audio(
                int(len(buf) / (self.input_audio_sample_rate() / 1000 * 2))
            )
            await self.client.send_pcm_data(bytes(buf))
        except Exception as e:
            self.ten_env.log_error(f"failed to send audio: {e}")
            return False
        return True

    @override
    async def finalize(self, session_id: str | None) -> None:
        if not self.is_connected():
            return None
        assert self.client is not None
        assert self.config is not None

        self.last_finalize_timestamp = int(time.time() * 1000)
        _ = self.ten_env.log_debug(
            f"KEYPOINT finalize start at {self.last_finalize_timestamp}]"
        )
        if (
            self.config.params.finalize_mode
            == self.config.params.FinalizeMode.DISCONNECT
        ):
            await self.client.send_end_of_stream()
        elif (
            self.config.params.finalize_mode
            == self.config.params.FinalizeMode.VENDOR_DEFINED
        ):
            await self.client.send_end_of_stream()
        elif (
            self.config.params.finalize_mode
            == self.config.params.FinalizeMode.MUTE_PKG
        ):
            assert self.config.params.mute_pkg_duration_ms is not None
            empty_audio_bytes_len = int(
                self.config.params.mute_pkg_duration_ms
                * self.input_audio_sample_rate()
                / 1000
                * 2
            )
            frame = bytearray(empty_audio_bytes_len)
            await self.client.send_pcm_data(bytes(frame))
            self.audio_timeline.add_silence_audio(
                self.config.params.mute_pkg_duration_ms
            )
        else:
            _ = self.ten_env.log_error(
                f"Unknown finalize mode: {self.config.params.finalize_mode}"
            )

    # tencent asr client event handler
    @override
    async def on_asr_start(self, response: ResponseData):
        self.ten_env.log_info(
            f"vendor connection opened: {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()
        await self.on_connected()
        if self.reconnect_manager:
            self.reconnect_manager.mark_connection_successful()

    @override
    async def on_asr_close(self, code: int, reason: str):
        self.ten_env.log_info(
            f"vendor connection closed: code={code}, reason={reason}",
            category=LOG_CATEGORY_VENDOR,
        )
        vendor_info = None
        if code not in (0, 1000):
            vendor_info = ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=str(code),
                message=reason or "closed",
            )
        await self.on_disconnected(
            code=0, message="closed", vendor_info=vendor_info
        )
        if self._skip_close_reconnect:
            # on_asr_fail may have already scheduled reconnect for the same drop.
            self._skip_close_reconnect = False
            return
        if not self.stopped:
            self.ten_env.log_warn(
                "Tencent ASR connection closed. Reconnecting...",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._handle_reconnect()

    async def _refresh_connection_params(self) -> None:
        if self.config is None or self.client is None:
            return
        self.request_params = self.config.params.to_request_params()
        self.client.update_params(self.request_params)
        await self.client.on_reconnect()

    async def _handle_reconnect(self) -> None:
        """Schedule one reconnect attempt; further retries come from vendor callbacks."""
        if self.stopped or self.client is None or not self.reconnect_manager:
            return

        await self._refresh_connection_params()
        await self.reconnect_manager.handle_reconnect(
            connection_func=self.start_connection,
            error_handler=self.send_asr_error,
        )

    @override
    async def on_asr_fail(self, response: ResponseData):
        """
        response.result is tencent asr server error.
        """
        self.ten_env.log_error(
            f"vendor_error: on_asr_fail {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        vendor_info = ModuleErrorVendorInfo(
            vendor=self.vendor(),
            code=str(response.code),
            message=response.message,
        )
        await self.send_asr_error(
            ModuleError(
                module="asr",
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=response.model_dump_json(),
                vendor_info=vendor_info,
            ),
        )
        if response.code in (4001, 4002, 4003, 4004, 4005):
            await self.on_disconnected(
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=response.message,
                vendor_info=vendor_info,
            )
            if not self.stopped:
                # Server may also close the socket; skip the duplicate close path.
                self._skip_close_reconnect = True
                self.ten_env.log_warn(
                    "Tencent ASR server error. Reconnecting...",
                    category=LOG_CATEGORY_VENDOR,
                )
                await self._handle_reconnect()

    @override
    async def on_asr_error(
        self, response: ResponseData[str], error: Exception | None = None
    ):
        """
        response.code: 9999 is TencentAsrClient error, 9998 is WebSocketClient error.
        response.message = "error"
        response.voice_id is the voice_id of the request.
        response.result is the str of the Exception instance.
        error is the Exception instance.

        Only 9998 (transport/session loss) reports disconnected and reconnects.
        9999 (e.g. malformed server JSON) keeps the live session — same as main,
        where ws_client auto_reconnect retried 9998 only at the socket layer.
        """
        self.ten_env.log_error(
            f"vendor_error: on_asr_error {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        error_message = response.result or "unknown error"
        vendor_info = ModuleErrorVendorInfo(
            vendor=self.vendor(),
            code=str(response.code),
            message=error_message,
        )
        await self.send_asr_error(
            ModuleError(
                module="asr",
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=error_message,
                vendor_info=vendor_info,
            ),
        )
        if not self._is_reconnectable_asr_error(response.code):
            return

        await self.on_disconnected(
            code=ModuleErrorCode.NON_FATAL_ERROR.value,
            message=error_message,
            vendor_info=vendor_info,
        )
        if not self.stopped:
            self.ten_env.log_warn(
                "Tencent ASR connection error. Reconnecting...",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._handle_reconnect()

    def _get_language(self) -> str:
        assert self.request_params is not None
        model_type = self.request_params.engine_model_type
        language = model_type.lstrip("16k_")

        language_to_iso_639_1 = {
            "zh": "zh-CN",
            "zh_en": "zh-CN",
            "zh-PY": "zh-CN",
            "zh-TW": "zh-TW",
            "zh_edu": "zh-CN",
            "zh_medical": "zh-CN",
            "zh_court": "zh-CN",
            "yue": "zh-HK",
            "en": "en-US",
            "en_game": "en-US",
            "en_edu": "en-US",
            "ko": "ko-KR",
            "ja": "ja-JP",
            "fr": "fr-FR",
            "de": "de-DE",
        }

        return language_to_iso_639_1.get(language, language)

    def _get_asr_result_language(self) -> str:
        if self.config and self.config.params.result_language_default:
            s = (self.config.params.result_language_default or "").strip()
            if s:
                return s
        return self._get_language()

    async def _handle_asr_result(
        self, result: RecoginizeResult, message_id: str | None = None
    ):
        if (
            self.last_finalize_timestamp != 0
            and result.slice_type == RecoginizeResult.SliceType.END
        ):
            timestamp = int(time.time() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_debug(
                f"finalize end at {timestamp}, counter: {latency}"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

        duration_ms = result.end_time - result.start_time
        actual_start_ms = (
            self.audio_timeline.get_audio_duration_before_time(
                result.start_time
            )
            + self.sent_user_audio_duration_ms_before_last_reset
        )

        language = self._get_asr_result_language()

        asr_result = ASRResult(
            id=message_id,
            text=result.voice_text_str,
            final=result.slice_type == RecoginizeResult.SliceType.END,
            start_ms=actual_start_ms,
            duration_ms=duration_ms,
            language=language,
            words=[],
        )
        self.ten_env.log_debug(f"asr_result: {asr_result.model_dump_json()}")

        await self.send_asr_result(asr_result)

    @override
    async def on_asr_sentence_start(
        self, response: ResponseData[RecoginizeResult]
    ):
        """
        response.result is the RecoginizeResult instance.
        response.result.slice_type is SliceType.START.
        """
        if response.result is None:
            return
        self.ten_env.log_debug(
            f"vendor_result: on_asr_sentence_start {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._handle_asr_result(response.result, response.message_id)

    @override
    async def on_asr_sentence_change(
        self, response: ResponseData[RecoginizeResult]
    ):
        """
        response.result is the RecoginizeResult instance.
        response.result.slice_type is SliceType.PROCESSING.
        """
        if response.result is None:
            return
        self.ten_env.log_debug(
            f"vendor_result: on_asr_sentence_change {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._handle_asr_result(response.result, response.message_id)

    @override
    async def on_asr_sentence_end(
        self, response: ResponseData[RecoginizeResult]
    ):
        """
        response.result is the RecoginizeResult instance.
        response.result.slice_type is SliceType.END.
        """
        if response.result is None:
            return
        self.ten_env.log_debug(
            f"vendor_result: on_asr_sentence_end {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._handle_asr_result(response.result, response.message_id)

    @override
    async def on_asr_complete(self, response: ResponseData[RecoginizeResult]):
        """
        response.final is True.
        """
        if response.result is None:
            return
        self.ten_env.log_debug(
            f"vendor_result: on_asr_complete {response.model_dump_json()}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._handle_asr_result(response.result, response.message_id)

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)
