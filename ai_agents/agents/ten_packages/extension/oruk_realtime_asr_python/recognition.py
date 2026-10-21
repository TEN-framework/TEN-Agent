#
# Oruk realtime WebSocket client for TEN.
#
# The wire protocol is ported from Oruk's reference integration in
# Oruk-AI/pipecat-oruk (src/pipecat_oruk/realtime.py, MIT licensed) and
# restructured here as a persistent, callback-driven connection that fits TEN's
# ASR extension lifecycle. The Oruk realtime socket commits one turn per
# connection: stream PCM16, receive interim transcript deltas, then "commit" to
# receive the final transcript, phrase-emotion estimates and usage before the
# server closes. The extension reconnects for the next turn.
#
from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlsplit

import aiohttp

from .const import EMOTION_PREFIX, MODEL, TRANSCRIPT_PREFIX

_CHUNK_BYTES = 10_240
_SUBPROTOCOL = "oruk-realtime"
_MAX_TRANSCRIPT_CHARS = 128_000


class OrukRealtimeHandshakeError(RuntimeError):
    def __init__(self, event):
        self.message, self.code, self.fatal = _vendor_error(event)
        super().__init__(self.message)


def _vendor_error(event):
    error = event.get("error")
    code = (
        error.get("code", "realtime_error")
        if isinstance(error, dict)
        else "realtime_error"
    )
    message = error.get("message", code) if isinstance(error, dict) else code
    return (
        str(message),
        str(code),
        code in {"unauthorized", "invalid_api_key", "forbidden", "not_found"},
    )


class OrukRealtimeCallback(Protocol):
    async def on_open(self) -> None: ...
    async def on_interim(self, text: str) -> None: ...
    async def on_final(self, text: str) -> None: ...
    async def on_phrase_emotion(self, event: dict[str, Any]) -> None: ...
    async def on_usage(self, usage: dict[str, Any]) -> None: ...
    async def on_error(
        self, message: str, code: str | None, fatal: bool
    ) -> None: ...
    async def on_close(self, code: int, message: str) -> None: ...


def validate_endpoint(endpoint: str) -> None:
    """Require secure WebSockets, credential-free URLs and model-only query."""
    parsed = urlsplit(endpoint)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        parsed.username
        or parsed.password
        or parsed.fragment
        or not parsed.hostname
    ):
        raise ValueError("endpoint must not contain credentials or a fragment")
    if parsed.scheme != "wss" and not (parsed.scheme == "ws" and local):
        raise ValueError(
            "endpoint requires wss (ws is allowed only on loopback for tests)"
        )
    if any(k != "model" for k, _ in parse_qsl(parsed.query)):
        raise ValueError("endpoint query may contain only model")


class OrukRealtimeConnection:
    """A single Oruk realtime turn over one WebSocket."""

    def __init__(
        self,
        *,
        api_key: str,
        url: str,
        language: str,
        phrase_emotions: bool,
        diarize: bool,
        sample_rate: int,
        callback: OrukRealtimeCallback,
        ten_env: Any,
    ) -> None:
        self._api_key = api_key
        self._url = url
        self._language = language
        self._phrase_emotions = phrase_emotions
        self._diarize = diarize
        self._sample_rate = sample_rate
        self._callback = callback
        self._ten_env = ten_env

        self._session: aiohttp.ClientSession | None = None
        self._socket: aiohttp.ClientWebSocketResponse | None = None
        self._receiver: asyncio.Task[None] | None = None
        self._ready = False
        self._committed = False
        self._request_id: str = ""
        self._closing = False
        self._interim_text = ""
        self._final_received = False
        self._close_code: int | None = None

    def is_connected(self) -> bool:
        return self.is_active() and not self._committed

    def is_active(self) -> bool:
        """The established socket can still deliver a committed turn's result."""
        return (
            self._ready
            and not self._closing
            and self._socket is not None
            and not self._socket.closed
        )

    def _session_options(self) -> dict[str, Any]:
        return {
            "model": MODEL,
            "language": self._language,
            "sample_rate": self._sample_rate,
            "word_timestamps": False,
            "phrase_emotions": self._phrase_emotions,
            "phrase_silence_ms": 600,
            "phrase_max_ms": 8_000,
            "diarize": self._diarize,
        }

    async def start(
        self, *, request_id: str, connect_timeout: float = 10.0
    ) -> None:
        validate_endpoint(self._url)
        if not self._api_key or any(c.isspace() for c in self._api_key):
            raise ValueError(
                "Provide a nonempty Oruk API key without whitespace"
            )

        self._request_id = request_id
        self._interim_text = ""
        self._final_received = False
        self._close_code = None
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None)
        )
        try:
            await asyncio.wait_for(
                self._handshake(request_id), timeout=connect_timeout
            )
        except BaseException:
            await self.close()
            raise

        self._ready = True
        self._receiver = asyncio.create_task(self._receive_loop())
        await self._callback.on_open()

    async def _handshake(self, request_id):
        self._socket = await self._session.ws_connect(
            self._url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "X-Request-ID": request_id,
            },
            protocols=[_SUBPROTOCOL],
            heartbeat=15,
            max_msg_size=1_048_576,
        )
        created = await self._receive_json()
        if created is not None and created.get("type") == "error":
            raise OrukRealtimeHandshakeError(created)
        if created is None or created.get("type") != "session.created":
            raise RuntimeError("missing session.created")
        self._request_id = created.get("request_id", request_id) or request_id
        await self._socket.send_json(
            {
                "type": "session.update",
                "session": self._session_options(),
            }
        )
        updated = await self._receive_json()
        if updated is not None and updated.get("type") == "error":
            raise OrukRealtimeHandshakeError(updated)
        if updated is None or updated.get("type") != "session.updated":
            raise RuntimeError("missing session.updated")

    async def send_pcm(self, pcm: bytes) -> None:
        if not self.is_connected() or self._committed:
            raise ConnectionError("Oruk turn is not accepting audio")
        for offset in range(0, len(pcm), _CHUNK_BYTES):
            await self._socket.send_bytes(pcm[offset : offset + _CHUNK_BYTES])

    async def commit(self) -> None:
        """Signal end of the turn's audio so the server emits the final result."""
        if self._socket is None or self._socket.closed or self._committed:
            return
        self._committed = True
        await self._socket.send_json({"type": "input_audio_buffer.commit"})

    async def _receive_json(self) -> dict[str, Any] | None:
        assert self._socket is not None
        message = await self._socket.receive()
        if message.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
            self._close_code = (
                message.data
                if message.type == aiohttp.WSMsgType.CLOSE
                and isinstance(message.data, int)
                else self._socket.close_code
            )
            return None
        if message.type == aiohttp.WSMsgType.ERROR:
            raise RuntimeError("websocket error")
        if message.type != aiohttp.WSMsgType.TEXT:
            raise RuntimeError("unexpected non-text websocket message")
        event = json.loads(message.data)
        if not isinstance(event, dict) or not isinstance(
            event.get("type"), str
        ):
            raise RuntimeError("invalid event")
        return event

    async def _receive_loop(self) -> None:
        code, message = 1000, "closed"
        try:
            while True:
                event = await self._receive_json()
                if event is None:
                    code = self._close_code or self._socket.close_code or 1006
                    if code not in (1000, 1001):
                        message = f"Oruk WebSocket closed abnormally ({code})"
                        await self._callback.on_error(
                            message, f"websocket_close_{code}", fatal=False
                        )
                    elif self._committed and not self._final_received:
                        message = (
                            "Oruk WebSocket closed before the final result"
                        )
                        await self._callback.on_error(
                            message, "missing_final", fatal=False
                        )
                    break
                await self._dispatch(event)
                if self._closing:
                    break
        except asyncio.CancelledError:
            return
        except Exception:
            code, message = 0, "receive loop error"
            await self._callback.on_error(
                message, "receive_failed", fatal=False
            )
        finally:
            self._ready = False
            if self._socket is not None and not self._socket.closed:
                await self._socket.close()
            if self._session is not None and not self._session.closed:
                await self._session.close()
            if not self._closing:
                await self._callback.on_close(code, message)

    async def _dispatch(self, event: dict[str, Any]) -> None:
        kind = event["type"]
        if kind == "error":
            await self._callback.on_error(*_vendor_error(event))
        elif kind == TRANSCRIPT_PREFIX + "delta":
            delta = event.get("delta")
            if isinstance(delta, str) and delta:
                if len(self._interim_text) + len(delta) > _MAX_TRANSCRIPT_CHARS:
                    raise RuntimeError("interim transcript exceeds limit")
                self._interim_text += delta
                await self._callback.on_interim(self._interim_text)
        elif kind == TRANSCRIPT_PREFIX + "completed":
            transcript = event.get("transcript")
            if isinstance(transcript, str):
                self._final_received = True
                await self._callback.on_final(transcript)
        elif kind in (EMOTION_PREFIX + "completed", EMOTION_PREFIX + "failed"):
            await self._callback.on_phrase_emotion(event)
        elif kind == "session.usage":
            usage = event.get("usage")
            if isinstance(usage, dict):
                await self._callback.on_usage(usage)
        # Other event kinds (speaker boundaries, future signals) are ignored.

    async def close(self) -> None:
        self._ready = False
        self._closing = True
        if (
            self._receiver is not None
            and self._receiver is not asyncio.current_task()
        ):
            self._receiver.cancel()
            try:
                await self._receiver
            except (asyncio.CancelledError, Exception):
                pass
            self._receiver = None
        if self._socket is not None and not self._socket.closed:
            await self._socket.close()
        self._socket = None
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
