#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Waiting on another task without mistaking its cancellation for ours.

``await task`` and ``await asyncio.shield(task)`` raise ``CancelledError``
both when the caller is cancelled and when somebody else cancelled
``task``. Python 3.10 cannot tell the two apart afterwards, so code that
waits on a task it does not own uses these helpers instead: the task's own
outcome is never raised, and only the caller's cancellation propagates.
"""
import asyncio


async def wait_done(task: asyncio.Future, timeout: float | None = None) -> bool:
    """Wait until ``task`` is done, at most ``timeout`` seconds.

    Returns whether it is done. Never cancels ``task``; never raises its
    result, its error or its cancellation. Cancellation of the caller
    propagates as usual.
    """
    done, _ = await asyncio.wait({task}, timeout=timeout)
    if task in done and not task.cancelled():
        # Mark the outcome as retrieved; the task's owner reports failures.
        task.exception()
    return task in done


async def cancel_and_wait(task: asyncio.Future) -> None:
    """Cancel ``task`` and wait until it has finished.

    Only the task's own cancellation is absorbed; a cancellation of the
    caller during the wait propagates.
    """
    task.cancel()
    await wait_done(task)
