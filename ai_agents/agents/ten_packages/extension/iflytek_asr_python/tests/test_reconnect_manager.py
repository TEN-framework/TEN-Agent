import asyncio

import pytest

from iflytek_asr_python.reconnect_manager import (
    ReconnectLimitReached,
    ReconnectLimitReachedError,
    ReconnectManager,
)


def test_legacy_reconnect_limit_exception_name_is_preserved() -> None:
    assert ReconnectLimitReached is ReconnectLimitReachedError


def test_reconnect_manager_uses_capped_exponential_backoff_and_resets() -> None:
    async def run() -> None:
        delays: list[float] = []

        async def sleep(delay: float) -> None:
            delays.append(delay)

        manager = ReconnectManager(
            base_delay=0.5,
            max_delay=1.0,
            max_attempts=3,
            sleep=sleep,
        )

        async def fail() -> None:
            raise ConnectionError("offline")

        with pytest.raises(ConnectionError):
            await manager.attempt(fail)
        with pytest.raises(ConnectionError):
            await manager.attempt(fail)

        connected = False

        async def succeed() -> None:
            nonlocal connected
            connected = True

        await manager.attempt(succeed)

        assert connected is True
        assert delays == [0.5, 1.0, 1.0]
        assert manager.current_attempts == 0

    asyncio.run(run())


def test_reconnect_manager_stops_at_configured_limit() -> None:
    async def run() -> None:
        async def sleep(_delay: float) -> None:
            pass

        manager = ReconnectManager(
            base_delay=0,
            max_delay=0,
            max_attempts=2,
            sleep=sleep,
        )

        async def fail() -> None:
            raise ConnectionError("offline")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await manager.attempt(fail)

        assert manager.can_retry() is False
        with pytest.raises(ReconnectLimitReachedError):
            await manager.attempt(fail)

    asyncio.run(run())
