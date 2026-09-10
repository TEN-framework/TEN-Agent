#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""
Blaze realtime STT (WebSocket /v1/stt/realtime, model stt-stream-1.5).

Protocol:
  1. Connect WS, send JSON {token, language, model, ...}
  2. Stream binary PCM s16le mono @ 16kHz
  3. Receive JSON {type: partial|final, text: ...}
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import websockets
from typing_extensions import override
from websockets.exceptions import ConnectionClosed

from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeDiscard,
    AsyncASRBaseExtension,
)
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleType,
)
from ten_ai_base.struct import ASRResult
from ten_runtime import AsyncTenEnv, AudioFrame

from .config import BlazeASRConfig, DEFAULT_SAMPLE_RATE


class BlazeSTTExtension(AsyncASRBaseExtension):
    """Realtime streaming Speech-to-Text via Blaze WebSocket."""

    def __init__(self, name: str):
        super().__init__(name)
        self.config: BlazeASRConfig | None = None
        self.session_id: str | None = None
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._connected = False
        self.audio_dumper: Dumper | None = None
        self._utterance_start_ms: int = 0

    @override
    def vendor(self) -> str:
        return "blaze"

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        config_json, _ = await ten_env.get_property_to_json("")
        try:
            self.config = BlazeASRConfig.model_validate_json(config_json)
            self.config.validate_config()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            if self.config.dump:
                dump_path = Path(self.config.dump_path)
                if dump_path.suffix != ".pcm":
                    dump_path = dump_path / "blaze_stt_in.pcm"
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                self.audio_dumper = Dumper(str(dump_path))
                await self.audio_dumper.start()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            ten_env.log_error(
                f"invalid property: {exc}", category=LOG_CATEGORY_KEY_POINT
            )
            self.config = None
            await self.send_asr_error(
                ModuleError(
                    module=ModuleType.ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(exc),
                ),
            )

    @override
    async def start_connection(self) -> None:
        if self.config is None:
            return
        await self.stop_connection()

        url = self.config.ws_url()
        self.ten_env.log_info(
            f"vendor_status_changed: connecting Blaze STT {url} "
            f"model={self.config.params.model}",
            category=LOG_CATEGORY_VENDOR,
        )
        try:
            self._ws = await websockets.connect(
                url,
                max_size=8 * 1024 * 1024,
                ping_interval=20,
                ping_timeout=20,
            )
            init_msg = {
                "token": self.config.params.api_key,
                "language": self.config.params.language,
                "model": self.config.params.model,
            }
            if self.config.params.topic:
                init_msg["topic"] = self.config.params.topic
            if self.config.params.context:
                init_msg["context"] = self.config.params.context

            await self._ws.send(json.dumps(init_msg))
            self._connected = True
            self._recv_task = asyncio.create_task(self._recv_loop())
            self.ten_env.log_info(
                "vendor_status_changed: Blaze STT realtime ready "
                f"model={self.config.params.model}",
                category=LOG_CATEGORY_VENDOR,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._connected = False
            self._ws = None
            self.ten_env.log_error(
                f"vendor_error: STT connect failed: {exc}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.send_asr_error(
                ModuleError(
                    module=ModuleType.ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(exc),
                ),
                ModuleErrorVendorInfo(
                    vendor="blaze", code="", message=str(exc)
                ),
            )

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle_message(msg)
        except ConnectionClosed:
            self.ten_env.log_info(
                "vendor_status_changed: Blaze STT WS closed",
                category=LOG_CATEGORY_VENDOR,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.ten_env.log_error(
                f"vendor_error: STT recv loop: {exc}",
                category=LOG_CATEGORY_VENDOR,
            )
        finally:
            self._connected = False

    async def _handle_message(self, msg: dict) -> None:
        if self.config is None:
            return
        msg_type = msg.get("type")
        if msg_type == "error":
            text = msg.get("text") or str(msg)
            self.ten_env.log_error(
                f"vendor_error: {text}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.send_asr_error(
                ModuleError(
                    module=ModuleType.ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=text,
                ),
                ModuleErrorVendorInfo(vendor="blaze", code="", message=text),
            )
            return

        if msg_type not in ("partial", "final"):
            return

        text = (msg.get("text") or "").strip()
        is_final = msg_type == "final"
        if not text and not is_final:
            return

        language = msg.get("language") or self.config.params.language
        asr_result = ASRResult(
            text=text,
            final=is_final,
            start_ms=0,
            duration_ms=0,
            language=language,
            words=[],
        )
        self.ten_env.log_debug(
            f"Blaze STT {msg_type}: {text[:120]!r}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self.send_asr_result(asr_result)
        if is_final:
            await self.send_asr_finalize_end()

    @override
    async def stop_connection(self) -> None:
        self._connected = False
        if self._recv_task is not None:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
            self._recv_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._ws = None
        self.ten_env.log_info("Blaze STT connection stopped")

    @override
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    @override
    def input_audio_sample_rate(self) -> int:
        if self.config is None:
            return DEFAULT_SAMPLE_RATE
        return int(self.config.params.sample_rate)

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeDiscard()

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        if not self.is_connected() or self._ws is None:
            return False
        self.session_id = session_id
        try:
            chunk = bytes(frame.get_buf())
            if not chunk:
                return True
            if self.audio_dumper:
                await self.audio_dumper.push_bytes(chunk)
            await self._ws.send(chunk)
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.ten_env.log_error(
                f"vendor_error: send_audio failed: {exc}",
                category=LOG_CATEGORY_VENDOR,
            )
            self._connected = False
            return False

    @override
    async def finalize(self, session_id: str | None) -> None:
        # Server-side endpoint detection emits finals; finalize is a no-op flush
        # signal so the framework lifecycle stays happy.
        self.session_id = session_id or self.session_id
        self.ten_env.log_debug(
            "Blaze STT finalize (endpoint detection is server-side)"
        )
