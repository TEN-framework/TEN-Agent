import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse, urlunparse

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import InvalidStatus

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]
DisconnectHandler = Callable[["SpekoRouterError | None"], Awaitable[None]]


class SpekoRouterError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        request_id: str = "",
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.request_id = request_id
        self.hint = hint

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> "SpekoRouterError":
        error = event.get("error", {})
        return cls(
            str(error.get("code", "relay_error")),
            str(error.get("message", "Speko Router error")),
            retryable=bool(error.get("retryable", False)),
            request_id=str(error.get("request_id", "")),
            hint=str(error.get("hint", "")),
        )


def websocket_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    scheme = {"https": "wss", "http": "ws"}.get(parsed.scheme, parsed.scheme)
    base_path = parsed.path.rstrip("/")
    return urlunparse((scheme, parsed.netloc, f"{base_path}{path}", "", "", ""))


class SpekoASRClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        configure: dict[str, Any],
        ready_timeout_sec: float,
        finalize_timeout_sec: float,
        on_event: EventHandler,
        on_disconnect: DisconnectHandler,
    ) -> None:
        self.api_key = api_key
        self.url = websocket_url(base_url, "/v1/stt/stream")
        self.configure = configure
        self.ready_timeout_sec = ready_timeout_sec
        self.finalize_timeout_sec = finalize_timeout_sec
        self.on_event = on_event
        self.on_disconnect = on_disconnect

        self.request_id = ""
        self.route: dict[str, Any] = {}
        self.usage: dict[str, Any] = {}
        self._ws: ClientConnection | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._finalize_waiter: asyncio.Future[None] | None = None
        self._audio_generation = 0
        self._final_generation = -1
        self._ready = False
        self._closing = False

    @property
    def is_ready(self) -> bool:
        return self._ready and self._ws is not None

    async def connect(self) -> None:
        if self.is_ready:
            return

        self._closing = False
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": uuid.uuid4().hex,
        }
        try:
            self._ws = await websockets.connect(
                self.url,
                additional_headers=headers,
                open_timeout=self.ready_timeout_sec,
                close_timeout=2.0,
            )
            configure_frame = json.dumps(self.configure, separators=(",", ":"))
            await self._ws.send(configure_frame)
            raw = await asyncio.wait_for(
                self._ws.recv(), timeout=self.ready_timeout_sec
            )
            event = self._decode_text_event(raw)
            if event.get("type") == "error":
                raise SpekoRouterError.from_event(event)
            if event.get("type") != "session.ready":
                raise SpekoRouterError(
                    "relay_error",
                    "Expected session.ready from Speko Router",
                    retryable=True,
                )
            self.request_id = str(event.get("request_id", ""))
            self.route = dict(event.get("route", {}))
            self._audio_generation = 0
            self._final_generation = -1
            self._ready = True
            await self.on_event(event)
            self._listener_task = asyncio.create_task(self._listen())
        except InvalidStatus as error:
            await self._close_socket()
            try:
                event = json.loads(error.response.body)
            except (ValueError, TypeError):
                event = {}
            if isinstance(event, dict) and isinstance(event.get("error"), dict):
                raise SpekoRouterError.from_event(event) from error
            status = error.response.status_code
            code = {
                400: "invalid_request",
                401: "authentication_failed",
                403: "authentication_failed",
                402: "insufficient_credit",
                404: "route_not_found",
                429: "rate_limited",
            }.get(status, "relay_error")
            raise SpekoRouterError(
                code,
                f"Speko Router WebSocket upgrade failed ({status})",
                retryable=status >= 500 or status == 429,
            ) from error
        except (Exception, asyncio.CancelledError):
            await self._close_socket()
            raise

    async def send_audio(self, audio: bytes) -> None:
        if not self.is_ready or self._ws is None:
            raise SpekoRouterError(
                "relay_error", "Speko ASR session is not ready", retryable=True
            )
        if audio:
            self._audio_generation += 1
        await self._ws.send(audio)

    async def commit(self) -> None:
        if not self.is_ready or self._ws is None:
            raise SpekoRouterError(
                "relay_error", "Speko ASR session is not ready", retryable=True
            )
        if self._final_generation == self._audio_generation:
            return
        waiter = self._finalize_waiter
        owner = waiter is None or waiter.done()
        if owner:
            waiter = asyncio.get_running_loop().create_future()
            self._finalize_waiter = waiter
        try:
            if owner:
                await self._ws.send('{"type":"input.commit"}')
            await asyncio.wait_for(
                asyncio.shield(waiter), timeout=self.finalize_timeout_sec
            )
        except asyncio.TimeoutError as error:
            raise SpekoRouterError(
                "request_timeout",
                "Timed out waiting for a final Speko transcript",
                retryable=True,
            ) from error
        finally:
            if owner:
                if not waiter.done():
                    waiter.cancel()
                if self._finalize_waiter is waiter:
                    self._finalize_waiter = None

    async def close(self, *, drain: bool = True) -> None:
        self._closing = True
        if self._ws is not None and self._ready:
            try:
                await self._ws.send('{"type":"session.close"}')
            except Exception:
                pass
        task = self._listener_task
        try:
            if (
                drain
                and task is not None
                and task is not asyncio.current_task()
            ):
                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        finally:
            await self._close_socket()

    async def _listen(self) -> None:
        error: SpekoRouterError | None = None
        try:
            assert self._ws is not None
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    raise SpekoRouterError(
                        "relay_error",
                        "Unexpected binary frame on Speko ASR session",
                        retryable=True,
                    )
                event = self._decode_text_event(raw)
                event_type = event.get("type")
                if event_type == "error":
                    error = SpekoRouterError.from_event(event)
                    break
                if event_type == "usage.updated":
                    self.usage = dict(event.get("usage", {}))
                elif event_type == "session.closed":
                    self.usage = dict(event.get("usage", {}))
                    await self.on_event(event)
                    break

                audio_generation = self._audio_generation
                await self.on_event(event)
                if event_type == "transcript.final":
                    self._final_generation = audio_generation
                    waiter = self._finalize_waiter
                    if waiter is not None and not waiter.done():
                        waiter.set_result(None)
        except SpekoRouterError as caught:
            error = caught
        except Exception as caught:  # pragma: no cover - transport-specific
            error = SpekoRouterError("relay_error", str(caught), retryable=True)
        finally:
            self._ready = False
            waiter = self._finalize_waiter
            if waiter is not None and not waiter.done():
                waiter.set_exception(
                    error
                    or SpekoRouterError(
                        "relay_error",
                        "Speko ASR session closed before final transcript",
                        retryable=True,
                    )
                )
            if not self._closing or error is not None:
                await self.on_disconnect(error)

    async def _close_socket(self) -> None:
        self._ready = False
        task = self._listener_task
        self._listener_task = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        websocket, self._ws = self._ws, None
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass

    @staticmethod
    def _decode_text_event(raw: str | bytes) -> dict[str, Any]:
        if not isinstance(raw, str):
            raise SpekoRouterError(
                "relay_error",
                "Expected a JSON text frame from Speko Router",
                retryable=True,
            )
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SpekoRouterError(
                "relay_error",
                "Speko Router returned invalid JSON",
                retryable=True,
            ) from error
        if not isinstance(event, dict):
            raise SpekoRouterError(
                "relay_error",
                "Speko Router event must be a JSON object",
                retryable=True,
            )
        return event
