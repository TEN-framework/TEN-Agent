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


def _transcription_config(config: StepFunASRConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.model,
        "language": config.language,
        "full_rerun_on_commit": config.full_rerun_on_commit,
        "enable_itn": config.enable_itn,
        "enable_timestamp_align": config.enable_timestamp_align,
    }
    if config.prompt is not None:
        payload["prompt"] = config.prompt
    return payload


@dataclass
class TranscriptSegment:
    start: int
    end: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # Stable asr_result.id for partial/final pairs on this span.
    result_id: str | None = None
    finalize_id: str | None = None
    finalize_time: float | None = None
    metadata: dict[str, Any] | None = None
    session_id: str | None = None
    timed_out: bool = False
    result: dict[str, Any] | None = None
    published: bool = False
    generation: int = -1
    commit_generation: int = -1
    # Local session-boundary seals must still get a vendor commit under
    # server_vad so consecutive sessions are not one continuous utterance.
    needs_vendor_commit: bool = False

    def can_bind_finalize(self, session_id: str | None) -> bool:
        """Whether an empty/open finalize may claim this sealed span."""
        if self.published or self.finalize_id is not None:
            return False
        if self.session_id is None or session_id is None:
            return True
        return self.session_id == session_id

    def bind_finalize(
        self,
        finalize_id: str,
        finalize_time: float,
        *,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        timed_out: bool = False,
        force_identity: bool = False,
    ) -> None:
        """Attach finalize identity once.

        Pending claims keep existing session/metadata (write-once). Sealing the
        open span for this finalize may force the finalize's identity.
        """
        if self.finalize_id is not None:
            return
        self.finalize_id = finalize_id
        self.finalize_time = finalize_time
        self.timed_out = timed_out
        if force_identity:
            # Empty finalize metadata must not wipe the originating audio context.
            if metadata:
                self.metadata = dict(metadata)
            if session_id is not None:
                self.session_id = session_id
            if self.session_id is not None and self.metadata is not None:
                if "session_id" not in self.metadata:
                    self.metadata["session_id"] = self.session_id
            return
        if self.metadata is None and metadata:
            self.metadata = dict(metadata)
        if self.session_id is None and session_id is not None:
            self.session_id = session_id


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
        self._normal_close = False
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
        self._timed_out_finalizes: deque[str] = deque()
        self._timed_out_finalize_set: set[str] = set()
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

    @property
    def journal_tail(self) -> int:
        """Return the absolute end offset of the recovery journal."""
        return self._tail

    @property
    def normal_close(self) -> bool:
        """Whether the latest connection ended with a normal close."""
        return self._normal_close

    def _mark_normal_close(self) -> None:
        self._normal_close = True

    async def start(self) -> None:
        await self.close()
        self._closing = False
        async with self._pump_lock:
            self._session_ready.clear()
            self._session_confirmed = False
            self._session_error = None
            self._normal_close = False
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
            self._prune_replay_confirmed()

        try:
            websocket = await websockets.connect(
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
            if self._closing:
                with suppress(Exception):
                    await websocket.close()
                return
            self.websocket = websocket
            self._receive_task = asyncio.create_task(self._receive_loop())
            input_config: dict[str, Any] = {
                "format": {
                    "type": "pcm",
                    "codec": "pcm_s16le",
                    "rate": self.config.sample_rate,
                    "bits": self.config.bits,
                    "channel": self.config.channels,
                },
                "transcription": _transcription_config(self.config),
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
            if self._normal_close:
                self._started = False
                await self.close()
                await self.callback.on_close()
                return
            if not self._session_confirmed:
                raise ConnectionError(
                    self._session_error
                    or "StepFun session closed during handshake"
                )
            self._started = True
            try:
                # Keep the network handshake outside this lock. Finalize must
                # be able to claim a timeout while a replacement session opens.
                async with self._pump_lock:
                    await self._pump()
            except ConnectionClosedOK:
                self._mark_normal_close()
                self._started = False
                await self.close()
                await self.callback.on_close()
                return
            if not self.is_connected():
                if self._normal_close:
                    self._started = False
                    await self.close()
                    await self.callback.on_close()
                    return
                raise ConnectionError("StepFun session closed during recovery")
            await self.callback.on_open()
            if not self.is_connected():
                if self._normal_close:
                    self._started = False
                    await self.close()
                    await self.callback.on_close()
                    return
                raise ConnectionError(
                    "StepFun session closed while publishing ready"
                )
        except ConnectionClosedOK:
            self._mark_normal_close()
            self._started = False
            await self.close()
            await self.callback.on_close()
            return
        except BaseException:
            await self.close()
            raise

    async def _receive_loop(self) -> None:
        try:
            async for raw in self.websocket:
                if not isinstance(raw, bytes):
                    await self._handle_message(json.loads(raw))
        except ConnectionClosedOK:
            self._mark_normal_close()
        except (ConnectionClosedError, WebSocketException) as exc:
            if not self._closing:
                await self.callback.on_error(str(exc), "connection_closed")
        except Exception as exc:
            if not self._closing:
                await self.callback.on_error(str(exc), "invalid_response")
        else:
            # websockets closes a normal async iterator without raising.
            self._mark_normal_close()
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
        has_unsealed_suffix = self._tail > end
        self._current = TranscriptSegment(
            end,
            metadata=(
                dict(segment.metadata)
                if has_unsealed_suffix and segment.metadata is not None
                else None
            ),
            session_id=segment.session_id if has_unsealed_suffix else None,
        )
        for item, mapped in list(self._items.items()):
            if mapped is segment and self._item_starts.get(item, -1) >= end:
                self._items[item] = self._current
        return segment

    def _unmapped_replay_segment(self) -> TranscriptSegment | None:
        mapped = tuple(self._items.values())
        for segment in self._pending:
            if (
                segment.generation == self._generation
                and not segment.published
                and segment.result is None
                and not any(
                    mapped_segment is segment for mapped_segment in mapped
                )
            ):
                return segment
        return None

    def _stamp_open_segment(
        self,
        metadata: dict[str, Any] | None,
        session_id: str | None,
    ) -> None:
        """Bind input session metadata to the open audio span."""
        if (
            session_id is not None
            and self._current.session_id is not None
            and session_id != self._current.session_id
            and self._tail > self._current.start
        ):
            # Client session boundary arrived before the vendor sealed the
            # previous turn; keep each span's originating metadata and force a
            # vendor commit even when server_vad owns endpoints.
            sealed = self._seal_current(self._tail)
            sealed.needs_vendor_commit = True
        if self._current.metadata is None and metadata is not None:
            self._current.metadata = dict(metadata)
            self._current.session_id = session_id
        elif self._current.session_id is None and session_id is not None:
            self._current.session_id = session_id

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
        # Confirmed / in-flight replay of an already published span must keep
        # its identity — do not fall through to empty _current.
        if segment is not None and segment.published:
            return segment
        if (
            segment is not None
            and segment.result is not None
            and start is not None
            and segment.end is not None
            and start >= segment.end
        ):
            segment = None
        if segment is None:
            if start is None:
                segment = self._unmapped_replay_segment()
            candidates = list(self._pending)
            if segment is None:
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
            # Deliver the structured error before waking the handshake waiter so
            # start()/close() cannot cancel this report mid-flight, and so the
            # fatal latch is owned by on_error rather than a plain ConnectionError.
            await self.callback.on_error(
                self._session_error,
                str(error.get("type") or ""),
                str(error.get("code") or ""),
            )
            if not self._started:
                self._session_ready.set()
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
                boundary_segment = next(
                    (
                        candidate
                        for candidate in self._pending
                        if candidate.end == end
                        and (
                            not candidate.published
                            or self._is_confirmed_replay_span(candidate)
                        )
                    ),
                    None,
                )
                if boundary_segment is not None:
                    if item:
                        self._items[item] = boundary_segment
                    return
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
                # Replacement finals must still advance journal retirement.
                self._retire_published_prefix()
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
            self._retire_published_prefix()

    def _retire_published_prefix(self) -> None:
        """Drop leading published spans whose replay identities are settled."""
        while self._pending and self._pending[0].published:
            completed = self._pending[0]
            # Keep published confirmed spans in pending until a replacement
            # item is mapped/completed for this recovery generation.
            if not self._segment_mappings_retirable(completed):
                break
            self._pending.popleft()
            self._retire_segment_mappings(completed)
            self._base = completed.end
            self._release_confirmed_audio()
            self._prune_replay_confirmed()

    def _prune_replay_confirmed(self) -> None:
        """Drop confirmed replay ranges that can no longer overlap live audio."""
        self._replay_confirmed = [
            span for span in self._replay_confirmed if span[1] > self._base
        ]

    def _remove_replayed_words(self, message: dict[str, Any]) -> dict[str, Any]:
        if not self._replay_confirmed or not message.get("transcript"):
            return message
        words = message.get("words") or []
        if not words:
            # Word timestamps are optional (alignment defaults off). Without
            # them, keep the vendor transcript rather than failing recovery.
            return message
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

    def _is_confirmed_replay_span(self, segment: TranscriptSegment) -> bool:
        if self._generation <= 1 or segment.end is None:
            return False
        return any(
            left == segment.start and right == segment.end
            for left, right in self._replay_confirmed
        )

    def _segment_mappings_retirable(self, segment: TranscriptSegment) -> bool:
        """True when no incomplete/confirmed-replay identity still needs it."""
        for item, mapped in self._items.items():
            if mapped is segment and item not in self._completed_item_set:
                return False
        if self._is_confirmed_replay_span(segment) and not any(
            mapped is segment and item in self._completed_item_set
            for item, mapped in self._items.items()
        ):
            return False
        return True

    def _retire_segment_mappings(self, segment: TranscriptSegment) -> None:
        """Drop completed segment transcript bookkeeping after publish."""
        for item, mapped in list(self._items.items()):
            if mapped is segment:
                self._items.pop(item, None)
                # Keep a bounded duplicate window; drop start map with item.
                self._item_starts.pop(item, None)
        segment.result = None

    def is_finalize_timed_out(self, finalize_id: str) -> bool:
        return finalize_id in self._timed_out_finalize_set

    def mark_finalize_timed_out(self, finalize_id: str) -> None:
        if finalize_id not in self._timed_out_finalize_set:
            self._timed_out_finalizes.append(finalize_id)
            self._timed_out_finalize_set.add(finalize_id)
            while len(self._timed_out_finalizes) > self._MAX_COMPLETED_ITEMS:
                retired = self._timed_out_finalizes.popleft()
                self._timed_out_finalize_set.discard(retired)
        for segment in self._pending:
            if segment.finalize_id == finalize_id:
                segment.timed_out = True

    async def send_audio(
        self,
        audio_data: bytes,
        *,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> bool:
        """Journal PCM and attempt vendor delivery.

        Returns True only when the frame is delivered to the live vendor send
        path (base-class send_audio contract / TTFW). The frame is always
        owned by the recovery journal after this call returns without raising,
        so flush paths must not re-queue it even when the return is False.
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
            self._stamp_open_segment(metadata, session_id)
            self._audio.seek(self._tail - self._storage_base)
            self._audio.write(audio_data)
            self._tail += len(audio_data)
            # Keep metadata on the open span after the bytes land.
            if self._current.metadata is None and metadata is not None:
                self._current.metadata = dict(metadata)
                self._current.session_id = session_id
            return await self._pump_or_reconnect()

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
            if end > self._current.start:
                if not self._current.can_bind_finalize(session_id):
                    # Open span belongs to another session — leave it alone and
                    # acknowledge this finalize as empty.
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
                            timed_out=finalize_id
                            in self._timed_out_finalize_set,
                        ),
                    )
                    return
                segment = self._seal_current(end)
                segment.bind_finalize(
                    finalize_id,
                    finalize_time,
                    metadata=metadata,
                    session_id=session_id,
                    timed_out=finalize_id in self._timed_out_finalize_set,
                    force_identity=True,
                )
                await self._pump_or_reconnect()
                return
            pending_segment = next(
                (
                    segment
                    for segment in reversed(self._pending)
                    if segment.can_bind_finalize(session_id)
                ),
                None,
            )
            if pending_segment is not None:
                pending_segment.bind_finalize(
                    finalize_id,
                    finalize_time,
                    metadata=metadata,
                    session_id=session_id,
                    timed_out=finalize_id in self._timed_out_finalize_set,
                )
                if self.is_connected():
                    if pending_segment.generation != self._generation:
                        await self._send_range(pending_segment.end)
                        pending_segment.generation = self._generation
                    await self._queue_commit(pending_segment)
                await self._pump_or_reconnect()
                return
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
                        timed_out=finalize_id in self._timed_out_finalize_set,
                    ),
                )
                return
            await self._pump_or_reconnect()

    async def _pump_or_reconnect(self) -> bool:
        if not self.is_connected():
            return False
        try:
            await self._pump()
            return True
        except ConnectionClosedOK:
            # Completed normal close must not emit an ASR error.
            self._mark_normal_close()
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
            if (
                segment.finalize_id is not None
                or not self.config.server_vad
                or segment.needs_vendor_commit
            ):
                await self._queue_commit(segment)
                segment.needs_vendor_commit = False
        await self._send_range(self._tail)

    async def _queue_commit(self, segment: TranscriptSegment) -> None:
        if segment.commit_generation == self._generation:
            return
        segment.commit_generation = self._generation
        self._awaiting_ack.append(segment)
        await self._send_json("input_audio_buffer.commit")

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
