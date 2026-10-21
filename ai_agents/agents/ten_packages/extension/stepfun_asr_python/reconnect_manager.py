from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class ReconnectManager:
    """Reconnect helper for one StepFun recognition session.

    When max_attempts <= 0, retries are unlimited until success or stop/fatal.
    """

    def __init__(self, max_attempts: int = 0, base_delay: float = 0.5):
        self.max_attempts = max_attempts
        self._unlimited = max_attempts <= 0
        self.base_delay = max(0.0, base_delay)
        self.attempts = 0
        self._lock = asyncio.Lock()

    def mark_connection_successful(self) -> None:
        self.attempts = 0

    def record_failed_attempt(self) -> None:
        self.attempts += 1

    def can_retry(self) -> bool:
        if self._unlimited:
            return True
        return self.attempts < max(1, self.max_attempts)

    def next_delay(self) -> float:
        if self.attempts <= 0:
            return 0.0
        return min(8.0, self.base_delay * 2 ** max(0, self.attempts - 1))

    async def handle_reconnect(
        self,
        connection_func: Callable[[], Awaitable[None]],
        should_abort: Callable[[], bool] | None = None,
    ) -> bool:
        """Legacy single-loop helper kept for unit tests of delay math."""
        async with self._lock:
            attempt = 0
            while self.can_retry():
                if should_abort and should_abort():
                    return False
                if attempt:
                    await asyncio.sleep(
                        min(8.0, self.base_delay * 2 ** (attempt - 1))
                    )
                    if should_abort and should_abort():
                        return False
                self.attempts = attempt + 1
                attempt += 1
                try:
                    await connection_func()
                except Exception:
                    if should_abort and should_abort():
                        return False
                    continue
                self.mark_connection_successful()
                return True
            return False
