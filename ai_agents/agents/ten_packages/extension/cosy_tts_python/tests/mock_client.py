import asyncio
from collections.abc import Callable
from dataclasses import replace
import time
from typing import Any
from unittest.mock import AsyncMock

from ..cosy_tts import (
    MESSAGE_TYPE_CMD_COMPLETE,
    MESSAGE_TYPE_PCM,
    ProviderCompletion,
    QueueItem,
)

EventSpec = tuple[int, Any, float]


class MockClientStream:
    def __init__(
        self,
        event_factory: Callable[[str, str], list[EventSpec]] | None = None,
        completion_event_factory: (
            Callable[[str], list[EventSpec]] | None
        ) = None,
    ) -> None:
        self._event_factory = event_factory or (lambda _text, _request_id: [])
        self._completion_event_factory = completion_event_factory
        self._queue: asyncio.Queue[QueueItem | Exception] = asyncio.Queue()
        self._ready = asyncio.Event()
        self._cancelled = False
        self._active_request_id: str | None = None
        self._first_request_sent_ns: int | None = None
        self._first_audio_received = False

    def configure(self, mock_instance: Any) -> None:
        mock_instance.start = AsyncMock(side_effect=self.start)
        mock_instance.stop = AsyncMock(side_effect=self.stop)
        mock_instance.synthesize_audio = AsyncMock(
            side_effect=self.synthesize_audio
        )
        mock_instance.complete = AsyncMock(side_effect=self.complete)
        mock_instance.cancel = AsyncMock(side_effect=self.cancel)
        mock_instance.get_audio_data = AsyncMock(
            side_effect=self.get_audio_data
        )

    async def start(self) -> int:
        return 0

    async def stop(self) -> None:
        self._cancelled = True

    async def synthesize_audio(self, text: str, request_id: str) -> None:
        self._cancelled = False
        if self._active_request_id != request_id:
            self._active_request_id = request_id
            self._first_request_sent_ns = None
            self._first_audio_received = False
        if self._first_request_sent_ns is None:
            self._first_request_sent_ns = time.perf_counter_ns()
        await self._enqueue_events(
            request_id,
            self._event_factory(text, request_id),
        )
        self._ready.set()

    async def _enqueue_events(
        self,
        request_id: str,
        events: list[EventSpec],
    ) -> None:
        for message_type, payload, delay in events:
            if delay:
                await self._queue.put(
                    QueueItem(
                        done=False,
                        message_type=-1,
                        payload=str(delay).encode(),
                        request_id=request_id,
                        task_id=f"task-{request_id}",
                    )
                )
            if message_type == MESSAGE_TYPE_CMD_COMPLETE and payload is None:
                payload = ProviderCompletion(0, f"task-{request_id}")
            if isinstance(payload, Exception):
                await self._queue.put(payload)
            else:
                await self._queue.put(
                    QueueItem(
                        done=message_type == MESSAGE_TYPE_CMD_COMPLETE,
                        message_type=message_type,
                        payload=payload,
                        request_id=request_id,
                        task_id=f"task-{request_id}",
                    )
                )

    async def complete(self, request_id: str) -> None:
        if self._completion_event_factory is not None:
            await self._enqueue_events(
                request_id,
                self._completion_event_factory(request_id),
            )
            self._ready.set()

    async def cancel(self) -> None:
        self._cancelled = True

    async def get_audio_data(self) -> QueueItem:
        await self._ready.wait()
        while True:
            if self._cancelled:
                await asyncio.Future()
            item = await self._queue.get()
            if isinstance(item, Exception):
                raise item
            if item.message_type == -1:
                await asyncio.sleep(float(bytes(item.payload).decode()))
                continue
            if (
                item.message_type == MESSAGE_TYPE_PCM
                and not self._first_audio_received
            ):
                self._first_audio_received = True
                if self._first_request_sent_ns is not None:
                    item = replace(
                        item,
                        ttfb_ms=int(
                            (
                                time.perf_counter_ns()
                                - self._first_request_sent_ns
                            )
                            / 1_000_000
                        ),
                    )
            return item
