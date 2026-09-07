#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from collections.abc import Awaitable, Callable


class ReconnectLimitReachedError(RuntimeError):
    pass


# Legacy compatibility alias for 0.2.x; remove in 0.3.0.
ReconnectLimitReached = ReconnectLimitReachedError


SleepCallable = Callable[[float], Awaitable[None]]
ConnectCallable = Callable[[], Awaitable[None]]


class ReconnectManager:
    def __init__(
        self,
        *,
        base_delay: float,
        max_delay: float,
        max_attempts: int,
        sleep: SleepCallable = asyncio.sleep,
    ) -> None:
        if base_delay < 0:
            raise ValueError("base_delay must not be negative")
        if max_delay < base_delay:
            raise ValueError(
                "max_delay must be greater than or equal to base_delay"
            )
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts
        self.current_attempts = 0
        self._sleep = sleep

    def can_retry(self) -> bool:
        return self.current_attempts < self.max_attempts

    def reset(self) -> None:
        self.current_attempts = 0

    def next_delay(self) -> float:
        if not self.can_retry():
            raise ReconnectLimitReachedError(
                "maximum reconnection attempts reached"
            )
        return min(
            self.base_delay * (2**self.current_attempts),
            self.max_delay,
        )

    async def attempt(self, connect: ConnectCallable) -> None:
        delay = self.next_delay()
        self.current_attempts += 1
        await self._sleep(delay)
        await connect()
        self.reset()
