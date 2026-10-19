from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class ReconnectManager:
    """Bounded reconnect helper for one StepFun recognition session."""

    def __init__(self, max_attempts: int = 5, base_delay: float = 0.5):
        self.max_attempts = max(1, max_attempts)
        self.base_delay = max(0.0, base_delay)
        self.attempts = 0
        self._lock = asyncio.Lock()

    def mark_connection_successful(self) -> None:
        self.attempts = 0

    async def handle_reconnect(
        self,
        connection_func: Callable[[], Awaitable[None]],
        should_abort: Callable[[], bool] | None = None,
    ) -> bool:
        async with self._lock:
            for attempt in range(self.max_attempts):
                if should_abort and should_abort():
                    return False
                self.attempts = attempt + 1
                if attempt:
                    await asyncio.sleep(
                        min(8.0, self.base_delay * 2 ** (attempt - 1))
                    )
                    if should_abort and should_abort():
                        return False
                try:
                    await connection_func()
                except Exception:
                    if should_abort and should_abort():
                        return False
                    continue
                self.mark_connection_successful()
                return True
            return False
