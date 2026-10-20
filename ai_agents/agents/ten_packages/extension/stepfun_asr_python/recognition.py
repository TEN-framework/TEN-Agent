from __future__ import annotations

import asyncio
import base64
import json
import tempfile
import uuid
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.exceptions import (
    ConnectionClosedError,
    ConnectionClosedOK,
    WebSocketException,
)

from ten_runtime import AsyncTenEnv

from .config import StepFunASRConfig


@dataclass
class TranscriptSegment:
    start: int
    end: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    finalize_id: str | None = None
    finalize_time: float | None = None
    metadata: dict[str, Any] | None = None
    session_id: str | None = None
    timed_out: bool = False
    result: dict[str, Any] | None = None
    published: bool = False
    generation: int = -1


class StepFunASRRecognitionCallback:
    async def on_open(self) -> None:
        pass

    async def on_result(
        self,
        message: dict[str, Any],
        segment: TranscriptSegment,
    ) -> None:
        pass

    async def on_audio_sent(self, total_bytes: int) -> None:
        pass

    async def on_error(
        self,
        message: str,
        error_type: str = "",
        error_code: str = "",
    ) -> None:
        pass

    async def on_close(self) -> None:
        pass


class StepFunASRRecognition:
    """Reconnectable StepFun transport with bounded in-memory PCM journaling."""

    _MAX_AUDIO_BYTES = 10 * 1024 * 1024
    _MAX_COMPLETED_ITEMS = 256

    def __init__(
        self,
        config: StepFunASRConfig,
        ten_env: AsyncTenEnv,
        callback: StepFunASRRecognitionCallback,
    ):
        self.config = config
        self.ten_env = ten_env
        self.callback = callback
        self.websocket: Any = None
        self._receive_task: asyncio.Task[None] | None = None
        self._pump_lock = asyncio.Lock()
        self._session_ready = asyncio.Event()
        self._session_confirmed = False
        self._session_error: str | None = None
        self._started = False
        self._closing = False
        self._generation = 0
        self._session_offset = 0
        self._sent = 0
        self._sent_once = 0
        self._base = 0
        self._audio = tempfile.SpooledTemporaryFile(
            max_size=self._MAX_AUDIO_BYTES
        )
        self._storage_base = 0
        self._tail = 0
        self._pending: deque[TranscriptSegment] = deque()
        self._current = TranscriptSegment(0)
        self._items: dict[str, TranscriptSegment] = {}
        self._item_starts: dict[str, int] = {}
        self._completed_items: deque[str] = deque()
        self._completed_item_set: set[str] = set()
        self._awaiting_ack: deque[TranscriptSegment] = deque()
        self._replay_confirmed: list[tuple[int, int]] = []

    @property
    def bytes_per_second(self) -> int:
        return (
            self.config.sample_rate
            * self.config.channels
            * self.config.bits
            // 8
        )

    async def start(self) -> None:
        async with self._pump_lock:
            await self.close()
            self._closing = False
            self._session_ready.clear()
            self._session_confirmed = False
            self._session_error = None
            self._generation += 1
            self._session_offset = self._base
            self._sent = self._base
            self._items.clear()
            self._item_starts.clear()
            self._completed_items.clear()
            self._completed_item_set.clear()
            self._awaiting_ack.clear()
            self._replay_confirmed.extend(
                (segment.start, segment.end)
                for segment in self._pending
                if segment.published and segment.end is not None
            )
            self._replay_confirmed = [
                span for span in self._replay_confirmed if span[1] > self._base
            ]
            if self.config.server_vad and not any(
                segment.finalize_id is not None for segment in self._pending
            ):
                self._pending.clear()
                self._current = TranscriptSegment(self._base)
            try:
                self.websocket = await websockets.connect(
                    self.config.url,
                    additional_headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                    },
                    open_timeout=self.config.connection_timeout,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=2,
                    max_size=None,
                )
                self._receive_task = asyncio.create_task(self._receive_loop())
                input_config: dict[str, Any] = {
                    "format": {
                        "type": "pcm",
                        "codec": "pcm_s16le",
                        "rate": self.config.sample_rate,
                        "bits": self.config.bits,
                        "channel": self.config.channels,
                    },
                    "transcription": {
                        "model": self.config.model,
                        "language": self.config.language,
                        "full_rerun_on_commit": self.config.full_rerun_on_commit,
                        "enable_itn": self.config.enable_itn,
                        "enable_timestamp_align": (
                            self.config.enable_timestamp_align
                        ),
                    },
                }
                if self.config.server_vad:
                    input_config["turn_detection"] = {
                        "type": "server_vad",
                        "silence_duration_ms": self.config.silence_duration_ms,
                        "threshold": self.config.vad_threshold,
                    }
                await self._send_json(
                    "session.update",
                    session={"audio": {"input": input_config}},
                )
                await asyncio.wait_for(
                    self._session_ready.wait(),
                    self.config.connection_timeout,
                )
                if not self._session_confirmed:
                    raise ConnectionError(
                        self._session_error
                        or "StepFun session closed during handshake"
                    )
                self._started = True
                await self._pump()
                if not self.is_connected():
                    raise ConnectionError(
                        "StepFun session closed during recovery"
                    )
                await self.callback.on_open()
                if not self.is_connected():
                    raise ConnectionError(
                        "StepFun session closed while publishing ready"
                    )
            except BaseException:
                await self.close()
                raise

    async def _receive_loop(self) -> None:
        try:
            async for raw in self.websocket:
                if not isinstance(raw, bytes):
                    await self._handle_message(json.loads(raw))
        except ConnectionClosedOK:
            pass
        except (ConnectionClosedError, WebSocketException) as exc:
            if not self._closing:
                await self.callback.on_error(str(exc), "connection_closed")
        except Exception as exc:
            if not self._closing:
                await self.callback.on_error(str(exc), "invalid_response")
        finally:
            was_started = self._started
            self._started = False
            self._session_ready.set()
            if was_started and not self._closing:
                await self.callback.on_close()

    def _seal_current(self, end: int) -> TranscriptSegment:
        segment = self._current
        segment.end = end
        self._pending.append(segment)
        self._current = TranscriptSegment(end)
        for item, mapped in list(self._items.items()):
            if mapped is segment and self._item_starts.get(item, -1) >= end:
                self._items[item] = self._current
        return segment

    def _segment_for(self, message: dict[str, Any]) -> TranscriptSegment:
        item = str(message.get("item_id") or "")
        words = message.get("words") or []
        start = (
            self._session_offset
            + round(float(words[0]["start"]) * self.bytes_per_second)
            if words
            else self._item_starts.get(item)
        )
        if item and start is not None:
            self._item_starts.setdefault(item, start)
        segment = self._items.get(item)
        if (
            segment is not None
            and segment.result is not None
            and start is not None
            and segment.end is not None
            and start >= segment.end
        ):
            segment = None
        if segment is None:
            candidates = list(self._pending)
            segment = next(
                (
                    candidate
                    for candidate in candidates
                    if start is not None
                    and candidate.end is not None
                    and candidate.start <= start < candidate.end
                ),
                None,
            )
            if segment is None:
                segment = (
                    next(
                        (
                            candidate
                            for candidate in candidates
                            if not candidate.published
                        ),
                        self._current,
                    )
                    if str(message.get("type", "")).endswith(".completed")
                    else self._current
                )
            if item:
                self._items[item] = segment
        return segment

    async def _handle_message(self, message: dict[str, Any]) -> None:
        kind = str(message.get("type") or "")
        item = str(message.get("item_id") or "")
        if kind == "session.updated":
            self._session_confirmed = True
            self._session_ready.set()
        elif kind == "error":
            error = message.get("error") or {}
            self._session_error = str(
                error.get("message") or "StepFun ASR error"
            )
            if not self._started:
                self._session_ready.set()
            await self.callback.on_error(
                self._session_error,
                str(error.get("type") or ""),
                str(error.get("code") or ""),
            )
        elif (
            kind == "input_audio_buffer.speech_stopped"
            and self.config.server_vad
        ):
            if item in self._completed_item_set:
                return
            end_ms = message.get("audio_end_ms", message.get("audio_start_ms"))
            if end_ms is not None:
                end = self._session_offset + int(
                    float(end_ms) * self.bytes_per_second / 1000
                )
                end = min(end, self._sent)
                if end > self._current.start:
                    segment = self._seal_current(end)
                    segment.generation = self._generation
                    if item:
                        self._items[item] = segment
        elif kind == "input_audio_buffer.committed":
            if self._awaiting_ack:
                self._items[item] = self._awaiting_ack.popleft()
        elif kind.endswith((".delta", ".completed")):
            if item in self._completed_item_set:
                return
            if kind.endswith(".delta") and not any(
                message.get(field) for field in ("text", "stash", "words")
            ):
                return
            segment = self._segment_for(message)
            message = dict(message)
            message["audio_offset_ms"] = (
                self._session_offset * 1000 / self.bytes_per_second
            )
            if kind.endswith(".delta"):
                if segment.result is None:
                    await self.callback.on_result(message, segment)
                return
            if segment.published:
                self._remember_completed_item(item)
                return
            if segment.end is None:
                words = message.get("words") or []
                if words and words[-1].get("end") is not None:
                    end = self._session_offset + round(
                        float(words[-1]["end"]) * self.bytes_per_second
                    )
                    end -= end % (self.config.bits // 8 * self.config.channels)
                    if (
                        segment is self._current
                        and segment.start < end <= self._tail
                    ):
                        segment = self._seal_current(end)
                        segment.generation = self._generation
            if segment.end is None:
                await self.callback.on_error(
                    "StepFun final has no committed audio boundary",
                    "invalid_response",
                    "missing_commit_boundary",
                )
                return
            self._remember_completed_item(item)
            segment.result = message
            await self.callback.on_result(
                self._remove_replayed_words(message), segment
            )
            segment.published = True
            while self._pending and self._pending[0].published:
                completed = self._pending.popleft()
                self._retire_segment_mappings(completed)
                self._base = completed.end
                self._release_confirmed_audio()

    def _remove_replayed_words(self, message: dict[str, Any]) -> dict[str, Any]:
        if not self._replay_confirmed or not message.get("transcript"):
            return message
        words = message.get("words") or []
        if not words:
            raise ValueError(
                "Recovered transcript has no word times for overlap reconciliation"
            )
        novel = []
        for word in words:
            start = self._session_offset + round(
                float(word["start"]) * self.bytes_per_second
            )
            end = self._session_offset + round(
                float(word["end"]) * self.bytes_per_second
            )
            if not any(
                left <= start and end <= right
                for left, right in self._replay_confirmed
            ):
                novel.append(word)
        if len(novel) == len(words):
            return message
        separator = "" if self.config.language.startswith("zh") else " "
        return {
            **message,
            "words": novel,
            "transcript": separator.join(str(word["word"]) for word in novel),
        }

    def recovery_complete(self) -> bool:
        if self._generation <= 1:
            return True
        spans = [
            (segment.start, segment.end)
            for segment in self._pending
            if not segment.published
        ]
        spans.append((self._current.start, self._tail))
        for start, end in spans:
            if end is None:
                continue
            self._audio.seek(start - self._storage_base)
            remaining = end - start
            while remaining > 0:
                chunk = self._audio.read(min(remaining, 64 * 1024))
                if not chunk or any(chunk):
                    return False
                remaining -= len(chunk)
        return True

    def _release_confirmed_audio(self) -> None:
        if (
            self._base != self._tail
            and self._base - self._storage_base < self._MAX_AUDIO_BYTES
        ):
            return
        retained = tempfile.SpooledTemporaryFile(max_size=self._MAX_AUDIO_BYTES)
        self._audio.seek(self._base - self._storage_base)
        while chunk := self._audio.read(64 * 1024):
            retained.write(chunk)
        self._audio.close()
        self._audio = retained
        self._storage_base = self._base

    def _remember_completed_item(self, item: str) -> None:
        if not item or item in self._completed_item_set:
            return
        self._completed_items.append(item)
        self._completed_item_set.add(item)
        while len(self._completed_items) > self._MAX_COMPLETED_ITEMS:
            retired = self._completed_items.popleft()
            self._completed_item_set.discard(retired)
            self._items.pop(retired, None)
            self._item_starts.pop(retired, None)

    def _retire_segment_mappings(self, segment: TranscriptSegment) -> None:
        """Drop completed segment transcript bookkeeping after publish."""
        for item, mapped in list(self._items.items()):
            if mapped is segment:
                self._items.pop(item, None)
                # Keep a bounded duplicate window; drop start map with item.
                self._item_starts.pop(item, None)
        segment.result = None

    def mark_finalize_timed_out(self, finalize_id: str) -> None:
        for segment in self._pending:
            if segment.finalize_id == finalize_id:
                segment.timed_out = True

    async def send_audio(self, audio_data: bytes) -> bool:
        """Journal PCM and attempt delivery.

        Returns True once the frame is owned by the recovery journal, even if
        the live WebSocket send fails. Callers must not re-queue journaled
        frames into a second buffer.
        """
        if not audio_data:
            return True
        if len(audio_data) % (self.config.bits // 8 * self.config.channels):
            raise ValueError("StepFun audio must contain complete PCM samples")
        async with self._pump_lock:
            if (
                self._tail - self._base + len(audio_data)
                > self._MAX_AUDIO_BYTES
            ):
                raise BufferError("StepFun audio recovery buffer is full")
            self._audio.seek(self._tail - self._storage_base)
            self._audio.write(audio_data)
            self._tail += len(audio_data)
            await self._pump_or_reconnect()
            return True

    async def commit(
        self,
        finalize_id: str,
        finalize_time: float,
        *,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> None:
        async with self._pump_lock:
            end = self._tail
            if end == self._current.start:
                await self.callback.on_result(
                    {
                        "type": "empty.completed",
                        "transcript": "",
                    },
                    TranscriptSegment(
                        end,
                        end,
                        finalize_id=finalize_id,
                        finalize_time=finalize_time,
                        metadata=(
                            dict(metadata) if metadata is not None else None
                        ),
                        session_id=session_id,
                    ),
                )
                return
            segment = self._seal_current(end)
            segment.finalize_id = finalize_id
            segment.finalize_time = finalize_time
            segment.metadata = (
                dict(metadata) if metadata is not None else None
            )
            segment.session_id = session_id
            await self._pump_or_reconnect()

    async def _pump_or_reconnect(self) -> bool:
        if not self.is_connected():
            return False
        try:
            await self._pump()
            return True
        except ConnectionClosedOK:
            # Completed normal close must not emit an ASR error.
            self._started = False
            await self.callback.on_close()
            return False
        except Exception as exc:
            self._started = False
            await self.callback.on_error(str(exc), "send_failed")
            await self.callback.on_close()
            return False

    async def _pump(self) -> None:
        for segment in list(self._pending):
            if segment.generation == self._generation:
                continue
            if segment.end is None:
                continue
            await self._send_range(segment.end)
            segment.generation = self._generation
            if segment.finalize_id is not None or not self.config.server_vad:
                self._awaiting_ack.append(segment)
                await self._send_json("input_audio_buffer.commit")
        await self._send_range(self._tail)

    async def _send_range(self, end: int) -> None:
        while self._sent < end:
            next_byte = min(end, self._sent + 3200)
            self._audio.seek(self._sent - self._storage_base)
            chunk = self._audio.read(next_byte - self._sent)
            await self._send_json(
                "input_audio_buffer.append",
                audio=base64.b64encode(chunk).decode("ascii"),
            )
            self._sent = next_byte
            if self._sent > self._sent_once:
                self._sent_once = self._sent
                await self.callback.on_audio_sent(self._sent_once)

    async def _send_json(self, kind: str, **fields: Any) -> None:
        if self.websocket is None:
            raise ConnectionError("StepFun WebSocket is not initialized")
        await self.websocket.send(
            json.dumps(
                {
                    "event_id": f"stepfun_{uuid.uuid4().hex}",
                    "type": kind,
                    **fields,
                },
                separators=(",", ":"),
            )
        )

    def is_connected(self) -> bool:
        if not self._started or self.websocket is None:
            return False
        state = getattr(getattr(self.websocket, "state", None), "name", "")
        return bool(getattr(self.websocket, "open", False) or state == "OPEN")

    async def close(self) -> None:
        self._closing = True
        self._started = False
        if (
            self._receive_task
            and self._receive_task is not asyncio.current_task()
        ):
            self._receive_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._receive_task
        self._receive_task = None
        if self.websocket is not None:
            try:
                await self.websocket.close()
            finally:
                self.websocket = None

    async def shutdown(self) -> None:
        await self.close()
        self._audio.close()
