#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""
Blaze realtime TTS client — matches official docs:
https://app.blaze.vn/api/documentation/realTimeTts

Protocol:
  1. Connect  wss://api.blaze.vn/v1/tts/realtime
  2. Recv     {"type": "successful-connection"}
  3. Send     {"token": "...", "strategy": "request"}
  4. Recv     {"type": "successful-authentication"}
  5. Send     TTS query JSON (query, language, audio_format, ...)
  6. Recv     processing-request → started-byte-stream → binary chunks
              → finished-byte-stream
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Tuple
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosed

from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient
from ten_runtime import AsyncTenEnv

from .config import BlazeTTSConfig, DEFAULT_API_URL


class BlazeTTSHttpClient(AsyncTTS2HttpClient):
    """Realtime TTS over WebSocket (class name kept for extension wiring)."""

    def __init__(self, config: BlazeTTSConfig, ten_env: AsyncTenEnv):
        super().__init__()
        self.config = config
        self.ten_env = ten_env
        self._is_cancelled = False
        self._ws = None
        self._ready = False
        self._lock = asyncio.Lock()
        ten_env.log_info(
            f"BlazeTTS realtime client model="
            f"{config.params.get('model', '2.0-realtime')} "
            f"speaker={config.params.get('speaker_id')}"
        )

    def _ws_url(self) -> str:
        base = str(self.config.params.get("api_url", DEFAULT_API_URL)).rstrip(
            "/"
        )
        if base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://") :]
        # Optional session defaults as query params (docs allow bare URL too)
        q = {
            "speaker_id": self.config.params.get("speaker_id", ""),
            "language": self.config.params.get("language", "vi"),
            "model": self.config.params.get("model", "2.0-realtime"),
            "sample_rate": str(
                int(self.config.params.get("sample_rate", 24000))
            ),
            "audio_format": self.config.params.get("audio_format", "pcm"),
        }
        return f"{base}/v1/tts/realtime?{urlencode(q)}"

    async def cancel(self):
        self.ten_env.log_debug("BlazeTTS: cancel() called.")
        self._is_cancelled = True

    async def _recv_json(self, timeout: float = 30.0) -> dict:
        assert self._ws is not None
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        if isinstance(raw, (bytes, bytearray)):
            raise ValueError(
                f"Expected JSON, received binary ({len(raw)} bytes)"
            )
        return json.loads(raw)

    async def _connect(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._ws = None
            self._ready = False

        url = self._ws_url()
        self.ten_env.log_info(
            f"BlazeTTS connecting {url.split('?')[0]}",
            category=LOG_CATEGORY_VENDOR,
        )
        # Docs example: ping_interval=None
        self._ws = await websockets.connect(
            url,
            max_size=16 * 1024 * 1024,
            ping_interval=None,
            open_timeout=20,
        )

        # 1) successful-connection
        hello = await self._recv_json(timeout=15)
        if hello.get("type") != "successful-connection":
            raise RuntimeError(f"Connection failed: {hello}")

        # 2) auth — strategy MUST be "request" (not "request_base")
        auth = {
            "token": self.config.params.get("api_key", ""),
            "strategy": "request",
        }
        await self._ws.send(json.dumps(auth))

        # 3) successful-authentication (required before queries)
        auth_ok = await self._recv_json(timeout=20)
        if auth_ok.get("type") != "successful-authentication":
            raise RuntimeError(f"Authentication failed: {auth_ok}")

        self._ready = True
        self.ten_env.log_info(
            "BlazeTTS realtime authenticated (strategy=request)",
            category=LOG_CATEGORY_VENDOR,
        )

    async def _ensure_ws(self) -> None:
        if self._ws is not None and self._ready:
            return
        await self._connect()

    def _build_query(self, text: str) -> dict:
        # Match official docs field types exactly
        return {
            "query": text,
            "language": self.config.params.get("language", "vi"),
            "audio_format": self.config.params.get("audio_format", "pcm"),
            "audio_quality": int(self.config.params.get("audio_quality", 64)),
            # docs use string speed
            "audio_speed": str(self.config.params.get("audio_speed", "1")),
            "speaker_id": self.config.params.get("speaker_id"),
            "normalization": self.config.params.get("normalization", "basic"),
            "model": self.config.params.get("model", "2.0-realtime"),
            "sample_rate": int(self.config.params.get("sample_rate", 24000)),
        }

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        self._is_cancelled = False

        if not text or not text.strip():
            yield None, TTS2HttpResponseEventType.END
            return

        async with self._lock:
            try:
                await self._ensure_ws()
                assert self._ws is not None

                payload = self._build_query(text)
                self.ten_env.log_debug(
                    f"BlazeTTS query request_id={request_id} "
                    f"model={payload['model']} chars={len(text)}",
                    category=LOG_CATEGORY_VENDOR,
                )
                await self._ws.send(json.dumps(payload))

                # processing-request
                msg = await self._recv_json(timeout=30)
                mtype = msg.get("type") or msg.get("status")
                if mtype in (
                    "failed-request",
                    "bad-request",
                    "internal-error",
                    "failed-authentication",
                ):
                    detail = (
                        msg.get("details") or msg.get("message") or str(msg)
                    )
                    self.ten_env.log_error(
                        f"vendor_error: {mtype} {detail} "
                        f"request_id={request_id}",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    yield str(detail).encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.ERROR
                    self._ready = False
                    return
                if mtype != "processing-request":
                    # Some paths may skip straight to started-byte-stream
                    if (msg.get("status") or msg.get("type")) != (
                        "started-byte-stream"
                    ):
                        self.ten_env.log_warn(
                            f"BlazeTTS unexpected after query: {msg}",
                            category=LOG_CATEGORY_VENDOR,
                        )

                # started-byte-stream (if not already)
                if (msg.get("status") or msg.get("type")) != (
                    "started-byte-stream"
                ):
                    msg = await self._recv_json(timeout=60)
                    st = msg.get("status") or msg.get("type")
                    if st in (
                        "failed-request",
                        "bad-request",
                        "internal-error",
                    ):
                        detail = (
                            msg.get("details") or msg.get("message") or str(msg)
                        )
                        self.ten_env.log_error(
                            f"vendor_error: {st} {detail} "
                            f"request_id={request_id}",
                            category=LOG_CATEGORY_VENDOR,
                        )
                        yield str(detail).encode(
                            "utf-8"
                        ), TTS2HttpResponseEventType.ERROR
                        self._ready = False
                        return
                    if st != "started-byte-stream":
                        self.ten_env.log_warn(
                            f"BlazeTTS expected started-byte-stream, got {msg}",
                            category=LOG_CATEGORY_VENDOR,
                        )

                # binary chunks until finished-byte-stream
                while True:
                    if self._is_cancelled:
                        yield None, TTS2HttpResponseEventType.FLUSH
                        return

                    raw = await asyncio.wait_for(self._ws.recv(), timeout=90)

                    if isinstance(raw, (bytes, bytearray)):
                        if self._is_cancelled:
                            yield None, TTS2HttpResponseEventType.FLUSH
                            return
                        if len(raw) > 0:
                            yield (
                                bytes(raw),
                                TTS2HttpResponseEventType.RESPONSE,
                            )
                        continue

                    data = json.loads(raw)
                    event = data.get("type") or data.get("status")
                    if event == "finished-byte-stream":
                        yield None, TTS2HttpResponseEventType.END
                        return
                    if event in (
                        "failed-request",
                        "bad-request",
                        "internal-error",
                    ):
                        detail = (
                            data.get("details")
                            or data.get("message")
                            or str(data)
                        )
                        self.ten_env.log_error(
                            f"vendor_error: {event} {detail} "
                            f"request_id={request_id}",
                            category=LOG_CATEGORY_VENDOR,
                        )
                        yield str(detail).encode(
                            "utf-8"
                        ), TTS2HttpResponseEventType.ERROR
                        self._ready = False
                        return
                    # ignore completed-request / speech-* if any
                    if event == "completed-request":
                        yield None, TTS2HttpResponseEventType.END
                        return

            except ConnectionClosed as exc:
                self._ready = False
                self._ws = None
                msg = f"WS closed: {exc}"
                self.ten_env.log_error(
                    f"vendor_error: {msg} request_id={request_id}",
                    category=LOG_CATEGORY_VENDOR,
                )
                yield msg.encode("utf-8"), TTS2HttpResponseEventType.ERROR
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._ready = False
                msg = str(exc)
                self.ten_env.log_error(
                    f"vendor_error: {msg} request_id={request_id}",
                    category=LOG_CATEGORY_VENDOR,
                )
                if "401" in msg or "403" in msg or "Authentication" in msg:
                    yield msg.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
                else:
                    yield msg.encode("utf-8"), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        self.ten_env.log_debug("BlazeTTS: clean() called.")
        self._ready = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._ws = None

    def get_extra_metadata(self) -> dict[str, Any]:
        return {
            "speaker_id": self.config.params.get("speaker_id", ""),
            "model": self.config.params.get("model", ""),
            "language": self.config.params.get("language", ""),
            "transport": "websocket-realtime",
        }
