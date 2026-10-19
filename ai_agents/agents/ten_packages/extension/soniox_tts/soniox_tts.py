from __future__ import annotations

import asyncio
import base64
import binascii
import json
import time
from typing import Any, AsyncIterator

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_runtime import AsyncTenEnv

from .config import SonioxTTSConfig

EVENT_TTS_RESPONSE = 1
EVENT_TTS_END = 2
EVENT_TTS_ERROR = 3
EVENT_TTS_TTFB_METRIC = 5
WS_RECV_TIMEOUT = 4.0
KEEPALIVE_INTERVAL = 25.0


class SonioxTTSConnectionException(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"Soniox TTS connection failed ({status_code}): {body}"
        )


class SonioxTTSError(Exception):
    def __init__(
        self,
        error_code: int | None,
        error_type: str,
        message: str,
        request_id: str = "",
    ):
        self.error_code = error_code
        self.error_type = error_type
        self.request_id = request_id
        super().__init__(message)

    @property
    def message(self) -> str:
        return str(self)


class SonioxTTSClient:
    def __init__(self, config: SonioxTTSConfig, ten_env: AsyncTenEnv):
        self.config = config
        self.ten_env = ten_env
        self._ws: Any = None
        self._stream_id: str | None = None
        self._request_started_at: float | None = None
        self._ttfb_sent = False
        self._text_end_sent = False
        self._needs_reconnect = False
        self._send_lock = asyncio.Lock()
        self._keepalive_task: asyncio.Task | None = None

    async def start(self) -> None:
        await self._ensure_connection()

    async def stop(self) -> None:
        self._needs_reconnect = False
        self._stream_id = None
        await self._stop_keepalive()
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def cancel(self) -> None:
        ws = self._ws
        stream_id = self._stream_id
        self._stream_id = None
        self._request_started_at = None
        if ws is not None and stream_id:
            try:
                async with self._send_lock:
                    await ws.send(
                        json.dumps({"stream_id": stream_id, "cancel": True})
                    )
            except Exception:
                pass
        self._needs_reconnect = True
        await self.stop()

    async def start_stream(self, stream_id: str) -> None:
        if self._needs_reconnect:
            await self._reconnect()
        await self._ensure_connection()
        if self._stream_id is not None:
            raise RuntimeError("A Soniox TTS stream is already active")

        payload: dict[str, Any] = {
            "model": self.config.model,
            "language": self.config.language,
            "voice": self.config.voice,
            "audio_format": self.config.audio_format,
            "sample_rate": self.config.sample_rate,
            "stream_id": stream_id,
        }
        if self.config.speed != 1.0:
            payload["speed"] = self.config.speed
        if self.config.reduce_silence:
            payload["reduce_silence"] = True
        if self.config.return_timestamps:
            payload["return_timestamps"] = True
        if self.config.client_reference_id:
            payload["client_reference_id"] = self.config.client_reference_id

        try:
            async with self._send_lock:
                await self._ws.send(json.dumps(payload))
        except Exception:
            self._needs_reconnect = True
            raise

        self._stream_id = stream_id
        self._request_started_at = None
        self._ttfb_sent = False
        self._text_end_sent = False

    async def send_text(self, text: str, text_end: bool) -> None:
        if self._ws is None or self._stream_id is None:
            raise RuntimeError("Soniox TTS stream is not active")
        if self._request_started_at is None:
            self._request_started_at = time.monotonic()
        self._text_end_sent = text_end

        payload = {
            "text": text,
            "text_end": text_end,
            "stream_id": self._stream_id,
        }
        try:
            async with self._send_lock:
                await self._ws.send(json.dumps(payload))
        except Exception:
            self._needs_reconnect = True
            raise

    @property
    def text_end_sent(self) -> bool:
        return self._text_end_sent

    async def iter_events(
        self, stream_id: str
    ) -> AsyncIterator[tuple[bytes | int | SonioxTTSError | None, int]]:
        try:
            while self._ws is not None and self._stream_id == stream_id:
                message = await asyncio.wait_for(
                    self._ws.recv(), timeout=WS_RECV_TIMEOUT
                )
                if isinstance(message, bytes):
                    yield SonioxTTSError(
                        400,
                        "invalid_response",
                        "Soniox returned a binary response",
                        stream_id,
                    ), EVENT_TTS_ERROR
                    return

                try:
                    payload = json.loads(message)
                except (TypeError, json.JSONDecodeError) as exc:
                    yield SonioxTTSError(
                        None,
                        "invalid_response",
                        f"Invalid Soniox response: {exc}",
                        stream_id,
                    ), EVENT_TTS_ERROR
                    return

                message_stream_id = payload.get("stream_id")
                if message_stream_id not in (None, stream_id):
                    continue

                if "error_code" in payload or "error_type" in payload:
                    yield (
                        SonioxTTSError(
                            payload.get("error_code"),
                            str(payload.get("error_type", "vendor_error")),
                            str(
                                payload.get("error_message", "Soniox TTS error")
                            ),
                            str(payload.get("request_id", "")),
                        ),
                        EVENT_TTS_ERROR,
                    )
                    continue

                audio = payload.get("audio")
                if audio:
                    try:
                        audio_bytes = base64.b64decode(audio, validate=True)
                    except (ValueError, binascii.Error) as exc:
                        yield SonioxTTSError(
                            400,
                            "invalid_response",
                            f"Invalid Soniox audio payload: {exc}",
                            stream_id,
                        ), EVENT_TTS_ERROR
                        return

                    if audio_bytes:
                        if not self._ttfb_sent:
                            ttfb_ms = 0
                            if self._request_started_at is not None:
                                ttfb_ms = int(
                                    (
                                        time.monotonic()
                                        - self._request_started_at
                                    )
                                    * 1000
                                )
                            self._ttfb_sent = True
                            yield ttfb_ms, EVENT_TTS_TTFB_METRIC
                        yield audio_bytes, EVENT_TTS_RESPONSE

                if payload.get("terminated") is True:
                    self._stream_id = None
                    yield None, EVENT_TTS_END
                    return
        except asyncio.TimeoutError:
            self._needs_reconnect = True
            self._stream_id = None
            yield SonioxTTSError(
                None,
                "request_timeout",
                "Timed out waiting for Soniox TTS response",
                stream_id,
            ), EVENT_TTS_ERROR
        except ConnectionClosed as exc:
            self._needs_reconnect = True
            self._stream_id = None
            yield SonioxTTSError(
                getattr(exc, "code", None),
                "connection_closed",
                "Soniox TTS WebSocket connection closed",
                stream_id,
            ), EVENT_TTS_ERROR
        except Exception as exc:
            self._needs_reconnect = True
            self._stream_id = None
            self.ten_env.log_error(
                f"Soniox TTS receive failed: {exc}",
                category=LOG_CATEGORY_VENDOR,
            )
            yield SonioxTTSError(
                None,
                "connection_error",
                str(exc),
                stream_id,
            ), EVENT_TTS_ERROR

    async def _ensure_connection(self) -> None:
        if self._ws is None:
            await self._connect()

    async def _connect(self) -> None:
        try:
            self._ws = await websockets.connect(
                self.config.base_url,
                additional_headers={
                    "Authorization": f"Bearer {self.config.api_key}"
                },
            )
            self.ten_env.log_debug(
                "vendor_status: connected to soniox tts",
                category=LOG_CATEGORY_VENDOR,
            )
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        except InvalidStatus as exc:
            status_code = getattr(exc.response, "status_code", 0)
            raise SonioxTTSConnectionException(status_code, str(exc)) from exc
        except Exception as exc:
            message = str(exc)
            if "401" in message or "Unauthorized" in message:
                raise SonioxTTSConnectionException(401, message) from exc
            raise

    async def _reconnect(self) -> None:
        ws = self._ws
        self._ws = None
        self._stream_id = None
        self._needs_reconnect = False
        await self._stop_keepalive()
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        await self._connect()

    async def _stop_keepalive(self) -> None:
        task = self._keepalive_task
        self._keepalive_task = None
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _keepalive_loop(self) -> None:
        try:
            while self._ws is not None:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                if self._ws is None or self._stream_id is not None:
                    continue
                async with self._send_lock:
                    await self._ws.send(json.dumps({"keep_alive": True}))
        except Exception:
            self._needs_reconnect = True
