#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Thin client over the Kotoba Python SDK (``kotoba-sdk``).

One ``AsyncTTSSession`` is kept open across requests. The service closes
idle sockets and connections can drop at any time, so every request goes
through ``connect()``, which reconnects when the socket is gone.
"""
import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable

import websockets
from kotoba._ws_tts import AsyncTTSSession
from kotoba.errors import APIError, AuthError, KotobaError, ProtocolError
from kotoba.errors import TimeoutError as KotobaTimeoutError
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.message import ModuleErrorVendorInfo
from ten_runtime import AsyncTenEnv

from .config import KotobaTTSConfig

# Server error codes that mean the configuration can never work.
_FATAL_CODES = frozenset(
    {
        "unsupported_language",
        "unsupported_format",
        "invalid_sample_rate",
        "invalid_open_message",
        "unauthorized",
    }
)

# How long ``cancel()`` waits for the server's ``response.done`` before the
# socket is dropped instead.
CANCEL_GRACE_SECONDS = 2.0


class KotobaTTSError(Exception):
    """A failed service call, classified for the extension.

    ``fatal`` maps to ``ModuleErrorCode.FATAL_ERROR``. ``retryable`` says a
    fresh connection may succeed when no audio was produced yet.
    """

    def __init__(
        self, message: str, *, code: str, fatal: bool, retryable: bool
    ) -> None:
        super().__init__(message)
        self.code = code
        self.fatal = fatal
        self.retryable = retryable

    def vendor_info(self, vendor: str) -> ModuleErrorVendorInfo:
        return ModuleErrorVendorInfo(
            vendor=vendor, code=self.code, message=str(self)
        )


def classify_error(exc: BaseException) -> KotobaTTSError:
    """Map an SDK or transport exception onto ``KotobaTTSError``."""
    if isinstance(exc, KotobaTTSError):
        return exc
    if isinstance(exc, AuthError):
        return KotobaTTSError(
            "fal rejected the API key",
            code="unauthorized",
            fatal=True,
            retryable=False,
        )
    if isinstance(exc, ProtocolError):
        # The service names the condition in ``message`` on ``error``
        # frames and in ``error.code`` on failed responses; check both.
        text = f"{exc.code or ''} {exc}"
        fatal_code = next((c for c in _FATAL_CODES if c in text), None)
        if fatal_code is None and "sample_rate" in text:
            fatal_code = "invalid_sample_rate"
        code = fatal_code or exc.code or "error"
        return KotobaTTSError(
            str(exc),
            code=code,
            fatal=fatal_code is not None,
            retryable=fatal_code is None,
        )
    if _is_policy_close(exc):
        # fal accepts the upgrade and then closes with 1008 "Unauthorized"
        # for an unknown key, instead of refusing the HTTP handshake.
        return KotobaTTSError(
            "fal rejected the API key",
            code="unauthorized",
            fatal=True,
            retryable=False,
        )
    if isinstance(exc, KotobaTimeoutError):
        return KotobaTTSError(
            str(exc), code="handshake_timeout", fatal=False, retryable=True
        )
    if isinstance(exc, (APIError, KotobaError)):
        return KotobaTTSError(
            str(exc), code="transport_error", fatal=False, retryable=True
        )
    if isinstance(exc, websockets.exceptions.ConnectionClosed):
        close_code = exc.rcvd.code if exc.rcvd is not None else None
        return KotobaTTSError(
            f"connection closed: code={close_code}",
            code="connection_closed",
            fatal=False,
            retryable=True,
        )
    return KotobaTTSError(
        f"{type(exc).__name__}: {exc}",
        code="unexpected_error",
        fatal=False,
        retryable=False,
    )


def _is_policy_close(exc: BaseException) -> bool:
    """True for a WebSocket close with code 1008 (policy violation), which
    the fal gateway uses for authentication failures."""
    if isinstance(exc, websockets.exceptions.ConnectionClosed):
        return exc.rcvd is not None and exc.rcvd.code == 1008
    if isinstance(exc, APIError) and not isinstance(exc, ProtocolError):
        text = str(exc)
        return "code=1008" in text or "unauthorized" in text.lower()
    return False


class KotobaTTSClient:
    def __init__(
        self,
        config: KotobaTTSConfig,
        ten_env: AsyncTenEnv,
        vendor: str,
        *,
        on_connecting: Callable[[], Awaitable[None]] | None = None,
        on_connected: Callable[[], Awaitable[None]] | None = None,
        on_disconnected: Callable[..., Awaitable[None]] | None = None,
        session_factory: Callable[..., AsyncTTSSession] = AsyncTTSSession,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor
        self._on_connecting = on_connecting
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._session_factory = session_factory
        self._clock = clock

        self._session: AsyncTTSSession | None = None
        self._connect_lock = asyncio.Lock()
        # True from the moment text is handed to the socket until the
        # server's response.done has been consumed. Stays True when the
        # consumer stops early, so cancel() knows there is work to undo.
        self._response_active = False
        self._drain_task: asyncio.Task | None = None
        self._closed = False

        # Rate echoed by ``session.created``; equals the configured rate
        # unless the server negotiated differently.
        self.negotiated_sample_rate: int = config.sample_rate
        # Monotonic time of the last text send, the TTFB origin.
        self.last_send_at: float | None = None
        # Handshake duration of the most recent new connection, consumed
        # once by ``take_connect_delay_ms()``.
        self._pending_connect_delay_ms: int | None = None

    # -- connection --------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._session is not None

    def take_connect_delay_ms(self) -> int | None:
        """Return and clear the handshake time of the last new connection."""
        delay, self._pending_connect_delay_ms = (
            self._pending_connect_delay_ms,
            None,
        )
        return delay

    async def connect(self) -> AsyncTTSSession:
        """Return the open session, connecting when needed."""
        if self._response_active:
            # A previous caller abandoned its response; cancel it so the
            # socket carries no stale audio into the next request.
            await self.cancel()
        await self._await_drain()
        async with self._connect_lock:
            if self._closed:
                raise KotobaTTSError(
                    "client is closed",
                    code="client_closed",
                    fatal=False,
                    retryable=False,
                )
            if self._session is not None:
                return self._session
            await self._report_connecting()
            started = self._clock()
            session = self._session_factory(
                self.config.base_url,
                language=self.config.language,
                speaker_id=self.config.speaker_id,
                audio_format="pcm16",
                sample_rate=self.config.sample_rate,
                api_key=self.config.key,
            )
            try:
                await session.start()
            except asyncio.CancelledError:
                await session.close()
                await self._report_disconnected(message="connect cancelled")
                raise
            except Exception as exc:
                err = classify_error(exc)
                self.ten_env.log_warn(
                    f"vendor_status: connect failed code={err.code}",
                    category=LOG_CATEGORY_VENDOR,
                )
                await self._report_disconnected(
                    message="connect failed",
                    vendor_info=err.vendor_info(self.vendor),
                )
                raise err from exc
            self._session = session
            self._response_active = False
            self.negotiated_sample_rate = int(session.sample_rate)
            if session.audio_format not in ("pcm16", "pcm_16"):
                await self._drop_locked(message="unexpected audio format")
                raise KotobaTTSError(
                    f"server negotiated {session.audio_format}, "
                    "expected pcm16",
                    code="unsupported_format",
                    fatal=True,
                    retryable=False,
                )
            delay_ms = int((self._clock() - started) * 1000)
            self._pending_connect_delay_ms = delay_ms
            self.ten_env.log_info(
                f"vendor_status: connected in {delay_ms} ms, "
                f"sample_rate={self.negotiated_sample_rate}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._report_connected()
            return session

    async def drop(self, *, message: str) -> None:
        """Close the socket; the next ``connect()`` opens a new one."""
        async with self._connect_lock:
            await self._drop_locked(message=message)

    async def _drop_locked(self, *, message: str) -> None:
        session, self._session = self._session, None
        self._response_active = False
        if session is None:
            return
        await session.close()
        self.ten_env.log_info(
            f"vendor_status: disconnected ({message})",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._report_disconnected(message=message)

    async def close(self) -> None:
        self._closed = True
        if self._drain_task is not None:
            self._drain_task.cancel()
            try:
                await self._drain_task
            except (asyncio.CancelledError, Exception):
                pass
            self._drain_task = None
        await self.drop(message="closed")

    # -- status callbacks (a reporting failure never breaks the client) ---

    async def _report_connecting(self) -> None:
        if self._on_connecting is None:
            return
        try:
            await self._on_connecting()
        except Exception as exc:
            self.ten_env.log_error(f"on_connecting callback failed: {exc}")

    async def _report_connected(self) -> None:
        if self._on_connected is None:
            return
        try:
            await self._on_connected()
        except Exception as exc:
            self.ten_env.log_error(f"on_connected callback failed: {exc}")

    async def _report_disconnected(
        self,
        *,
        message: str,
        vendor_info: ModuleErrorVendorInfo | None = None,
    ) -> None:
        if self._on_disconnected is None:
            return
        try:
            await self._on_disconnected(
                code=0, message=message, vendor_info=vendor_info
            )
        except Exception as exc:
            self.ten_env.log_error(f"on_disconnected callback failed: {exc}")

    # -- synthesis ---------------------------------------------------------

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Yield PCM16 chunks for ``text`` until the server reports done.

        Raises ``KotobaTTSError``. After an error the socket is dropped, so
        a retry reconnects. ``last_send_at`` is set when the text has been
        handed to the socket.
        """
        session = await self.connect()
        timeout = self.config.request_timeout_seconds

        # Mark the response active before the send: if the send is
        # interrupted the server may still have received the text.
        self._response_active = True
        try:
            await session.synthesize(text)
        except asyncio.CancelledError:
            await self.drop(message="send interrupted")
            raise
        except Exception as exc:
            # A socket the server closed while idle fails here first.
            await self.drop(message="send failed")
            raise classify_error(exc) from exc
        self.last_send_at = self._clock()

        done = False
        finished = False
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        session.__anext__(), timeout=timeout
                    )
                except StopAsyncIteration:
                    break
                if event.type == "audio_chunk":
                    if event.audio:
                        yield event.audio
                elif event.type == "done":
                    done = True
                    status = event.metadata.get("status")
                    self.ten_env.log_debug(
                        f"vendor_status: response done status={status}",
                        category=LOG_CATEGORY_VENDOR,
                    )
            finished = True
        except asyncio.TimeoutError as exc:
            await self.drop(message="response timeout")
            raise KotobaTTSError(
                f"no audio from the service for {timeout:g} s",
                code="response_timeout",
                fatal=False,
                retryable=False,
            ) from exc
        except KotobaError as exc:
            await self.drop(message="service error")
            raise classify_error(exc) from exc
        finally:
            # Left True when the consumer stopped early (cancellation or an
            # abandoned generator): ``cancel()`` then clears the server side.
            if finished:
                self._response_active = False

        if not done:
            await self.drop(message="closed before response.done")
            raise KotobaTTSError(
                "connection closed before the response completed",
                code="connection_closed",
                fatal=False,
                retryable=True,
            )

    async def cancel(self) -> None:
        """Cancel the in-flight response, if any.

        The server answers with ``response.done(cancelled)``; a drain task
        consumes it so the socket can be reused. If the server does not
        answer in time, the socket is dropped.
        """
        session = self._session
        if session is None or not self._response_active:
            return
        self._response_active = False
        try:
            await session.cancel()
        except Exception as exc:
            await self.drop(message=f"cancel failed: {exc}")
            return
        self._drain_task = asyncio.create_task(self._drain(session))

    async def _drain(self, session: AsyncTTSSession) -> None:
        try:
            await asyncio.wait_for(
                self._consume_until_done(session), CANCEL_GRACE_SECONDS
            )
        except (asyncio.TimeoutError, KotobaError) as exc:
            if self._session is session:
                await self.drop(message=f"cancel drain failed: {exc}")

    @staticmethod
    async def _consume_until_done(session: AsyncTTSSession) -> None:
        async for _event in session:
            pass

    async def _await_drain(self) -> None:
        """Wait for a pending cancel drain.

        Caller cancellation propagates: an interrupted drain leaves the
        socket in an unknown state, so it is dropped first.
        """
        task = self._drain_task
        if task is None:
            return
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            task.cancel()
            await self.drop(message="drain interrupted")
            raise
        except Exception:
            pass
        finally:
            if self._drain_task is task:
                self._drain_task = None
