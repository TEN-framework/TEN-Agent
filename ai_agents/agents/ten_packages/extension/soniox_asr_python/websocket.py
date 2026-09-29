import asyncio
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Any

import websockets
from websockets.exceptions import ConnectionClosed


@dataclass
class QueueItem:
    """Queue item that can carry a callback to be executed before sending."""

    message: str | bytes
    before_send_callback: Callable


@dataclass
class SonioxTranscriptToken:
    text: str
    start_ms: int
    end_ms: int
    is_final: Optional[bool] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None
    translation_status: Optional[str] = None
    language: Optional[str] = None


@dataclass
class SonioxTranslationToken:
    text: str
    translation_status: str
    language: str
    source_language: str
    is_final: Optional[bool] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None


@dataclass
class SonioxFinToken:
    text: str
    is_final: bool


@dataclass
class SonioxEndToken:
    text: str
    is_final: bool


SonioxToken = (
    SonioxTranscriptToken
    | SonioxTranslationToken
    | SonioxFinToken
    | SonioxEndToken
)


class SonioxWebsocketEvents(Enum):
    EXCEPTION = "exception"
    OPEN = "open"
    CLOSE = "close"
    ERROR = "error"
    FINISHED = "finished"
    TRANSCRIPT = "transcript"


class SonioxWebsocketClient:
    class State(Enum):
        INIT = "init"
        CONNECTING = "connecting"
        CONNECTED = "connected"
        STOPPING = "stopping"
        STOPPED = "stopped"

    def __init__(
        self,
        url: str,
        start_request: str,
        enable_keepalive: bool = False,
        keepalive_interval: float = 15.0,
    ):
        self.url = url
        self.start_request = start_request
        self.state = self.State.INIT
        self._send_queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._event_callbacks = {}

        # Keepalive parameters
        self.enable_keepalive = enable_keepalive
        self.keepalive_interval = keepalive_interval
        self._last_audio_time = 0.0
        self._keepalive_task = None

        self._total_sent_audio_bytes = 0
        self._connection_attempt_start_time = 0

    async def connect(self):
        """Run one websocket session. Reconnection is handled by the extension."""
        self._reset_client_state()
        if self.state in (self.State.STOPPING, self.State.STOPPED):
            return

        try:
            self._reset_session_state()
            self.state = self.State.CONNECTING
            self._connection_attempt_start_time = int(time.time() * 1000)
            async with websockets.connect(self.url) as ws:
                if self.state == self.State.STOPPING:
                    return
                await ws.send(self.start_request)
                self.state = self.State.CONNECTED
                await self._call(
                    SonioxWebsocketEvents.OPEN,
                    self._connection_attempt_start_time,
                )
                if self.enable_keepalive:
                    self._start_keepalive_task(ws)
                await self._work(ws)
            if self.state != self.State.STOPPING:
                await self._call(SonioxWebsocketEvents.CLOSE, 0, "closed")
        except Exception as e:
            # Only 1000 (normal closure) is a silent disconnect.
            # 1001 (going away) is ConnectionClosedOK in websockets but is a
            # transient service departure — still emit EXCEPTION.
            if self.state != self.State.STOPPING and not self.is_normal_close(
                e
            ):
                await self._call(SonioxWebsocketEvents.EXCEPTION, e)
            close_code, close_message = self._extract_close_info(e)
            if self.state != self.State.STOPPING:
                await self._call(
                    SonioxWebsocketEvents.CLOSE, close_code, close_message
                )
        finally:
            if self.state == self.State.STOPPING:
                self._stop_event.set()

    def _reset_client_state(self):
        self.state = self.State.INIT

    def _reset_session_state(self):
        self._stop_event.clear()
        if self.enable_keepalive:
            self._last_audio_time = 0.0
            self._stop_keepalive_task()

    @staticmethod
    def is_normal_close(exc: Exception) -> bool:
        """True only for intentional normal closure (code 1000 / 0).

        websockets maps both 1000 and 1001 onto ConnectionClosedOK; 1001
        (going away) must not be treated as an error-free close.
        """
        return isinstance(exc, ConnectionClosed) and getattr(
            exc, "code", None
        ) in (0, 1000)

    @staticmethod
    def _extract_close_info(e: Exception | None) -> tuple[int, str]:
        if isinstance(e, ConnectionClosed):
            return e.code, e.reason or "closed"
        return 0, "closed"

    def _start_keepalive_task(self, ws):
        """Start the keepalive background task"""
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
        self._keepalive_task = asyncio.create_task(self._keepalive_loop(ws))

    def _stop_keepalive_task(self):
        """Stop the keepalive background task"""
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            self._keepalive_task = None

    # pylint: disable=unused-argument
    async def _keepalive_loop(self, ws):
        """Background task that sends keepalive messages when no audio data for keepalive_interval seconds"""
        try:
            while self.state == self.State.CONNECTED:
                current_time = time.time()
                time_since_last_audio = current_time - self._last_audio_time

                if time_since_last_audio >= self.keepalive_interval:
                    # Send keepalive message
                    keepalive_message = json.dumps({"type": "keepalive"})
                    await self._send_queue.put(keepalive_message)
                    # Reset the timer after sending keepalive
                    self._last_audio_time = current_time

                # Wait for a short interval before checking again
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            pass
        except Exception as e:
            # Log any unexpected errors in keepalive loop
            await self._call(SonioxWebsocketEvents.EXCEPTION, e)

    async def _work(self, ws):
        while self.state != self.State.STOPPED:
            recv_task = asyncio.create_task(ws.recv())
            send_task = asyncio.create_task(self._send_queue.get())
            done, pending = await asyncio.wait(
                [recv_task, send_task], return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                if task is recv_task:
                    await self._handle_recv(ws, task.result())
                elif task is send_task:
                    await self._handle_send(ws, task.result())

    # pylint: disable=unused-argument
    async def _handle_recv(self, ws, message: str):
        data = json.loads(message)
        match data:
            case {
                "error_code": error_code,
                "error_message": error_message,
                **rest,
            }:
                await self._call(
                    SonioxWebsocketEvents.ERROR,
                    error_code,
                    error_message,
                    rest.get("request_id"),
                    rest.get("error_type"),
                )
            case {
                "finished": True,
                "final_audio_proc_ms": final_audio_proc_ms,
                "total_audio_proc_ms": total_audio_proc_ms,
            }:
                await self._call(
                    SonioxWebsocketEvents.FINISHED,
                    final_audio_proc_ms,
                    total_audio_proc_ms,
                )
                self._stop_event.set()
            case {
                "tokens": tokens,
                "final_audio_proc_ms": final_audio_proc_ms,
                "total_audio_proc_ms": total_audio_proc_ms,
            }:
                await self._call(
                    SonioxWebsocketEvents.TRANSCRIPT,
                    self._parse_tokens(tokens),
                    final_audio_proc_ms,
                    total_audio_proc_ms,
                )

    def _parse_tokens(self, tokens: list[dict]) -> list[SonioxToken]:
        return [self._parse_token(token) for token in tokens]

    def _parse_token(self, token: dict) -> SonioxToken:
        match token:
            case {"text": "<fin>", "is_final": True}:
                return SonioxFinToken("<fin>", True)
            case {"text": "<end>", "is_final": True}:
                return SonioxEndToken("<end>", True)
            case {
                "text": text,
                "translation_status": translation_status,
                "language": language,
                "source_language": source_language,
                **optionals,
            }:
                return SonioxTranslationToken(
                    text,
                    translation_status,
                    language,
                    source_language,
                    **optionals,
                )
            case {
                "text": text,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "is_final": is_final,
                **optionals,
            }:
                return SonioxTranscriptToken(
                    text, start_ms, end_ms, is_final, **optionals
                )
        assert False, f"Invalid token: {token}"

    async def _handle_send(self, ws, item: str | bytes | QueueItem):
        if isinstance(item, QueueItem):
            await item.before_send_callback(self._total_sent_audio_bytes)
            await ws.send(item.message)
        elif isinstance(item, bytes):
            self._total_sent_audio_bytes += len(item)
            await ws.send(item)
        else:  # str
            await ws.send(item)

    async def finalize(
        self,
        trailing_silence_ms: int | None = None,
        before_send_callback: Optional[Callable] = None,
    ):
        q: dict[str, Any] = {
            "type": "finalize",
        }
        if trailing_silence_ms is not None:
            q["trailing_silence_ms"] = trailing_silence_ms

        message = json.dumps(q)

        # Only use QueueItem if callback provided
        if before_send_callback:
            await self._send_queue.put(QueueItem(message, before_send_callback))
        else:
            await self._send_queue.put(message)

    async def stop(self, wait: bool = True):
        self.state = self.State.STOPPING
        if self.enable_keepalive:
            self._stop_keepalive_task()
        await self._send_queue.put("")
        if wait:
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
            except asyncio.TimeoutError as e:
                await self._call(SonioxWebsocketEvents.EXCEPTION, e)
            finally:
                self.state = self.State.STOPPED

    async def send_audio(self, audio: bytes):
        if self.enable_keepalive:
            self._last_audio_time = time.time()
        await self._send_queue.put(audio)

    def on(self, event: SonioxWebsocketEvents, callback: Callable):
        """
        Register a callback for a specific event.
        The callback should be a coroutine function that takes the same arguments as the event.
        EXCEPTION:
            - Exception: the exception object
        OPEN:
            - connection_start_timestamp: int (milliseconds)
        CLOSE:
            - vendor_code: int (vendor close code, 0 if unavailable)
            - vendor_message: str (vendor close reason)
        ERROR:
            - error_code: int
            - error_message: str
            - request_id: str | None (Soniox request id for vendor log correlation)
            - error_type: str | None (Soniox machine-readable error type)
        FINISHED:
            - final_audio_proc_ms: int
            - total_audio_proc_ms: int
        TRANSCRIPT:
            - tokens: list[SonioxToken]
            - final_audio_proc_ms: int
            - total_audio_proc_ms: int
        """
        self._event_callbacks[event] = callback

    async def _call(self, event: SonioxWebsocketEvents, *args, **kwargs):
        if event in self._event_callbacks:
            await self._event_callbacks[event](*args, **kwargs)
