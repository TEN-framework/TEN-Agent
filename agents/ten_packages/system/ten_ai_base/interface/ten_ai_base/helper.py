#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
from collections import deque
from datetime import datetime
import functools
from typing import Callable
from ten.async_ten_env import AsyncTenEnv


def get_property_bool(ten_env: AsyncTenEnv, property_name: str) -> bool:
    """Helper to get boolean property from ten_env with error handling."""
    try:
        return ten_env.get_property_bool(property_name)
    except Exception as err:
        ten_env.log_warn(f"GetProperty {property_name} failed: {err}")
        return False

def get_properties_bool(ten_env: AsyncTenEnv, property_names: list[str], callback: Callable[[str, bool], None]) -> None:
    """Helper to get boolean properties from ten_env with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_bool(ten_env, property_name))


def get_property_string(ten_env: AsyncTenEnv, property_name: str) -> str:
    """Helper to get string property from ten_env with error handling."""
    try:
        return ten_env.get_property_string(property_name)
    except Exception as err:
        ten_env.log_warn(f"GetProperty {property_name} failed: {err}")
        return ""


def get_properties_string(ten_env: AsyncTenEnv, property_names: list[str], callback: Callable[[str, str], None]) -> None:
    """Helper to get string properties from ten_env with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_string(ten_env, property_name))

def get_property_int(ten_env: AsyncTenEnv, property_name: str) -> int:
    """Helper to get int property from ten_env with error handling."""
    try:
        return ten_env.get_property_int(property_name)
    except Exception as err:
        ten_env.log_warn(f"GetProperty {property_name} failed: {err}")
        return 0
    
def get_properties_int(ten_env: AsyncTenEnv, property_names: list[str], callback: Callable[[str, int], None]) -> None:
    """Helper to get int properties from ten_env with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_int(ten_env, property_name))
    
def get_property_float(ten_env: AsyncTenEnv, property_name: str) -> float:
    """Helper to get float property from ten_env with error handling."""
    try:
        return ten_env.get_property_float(property_name)
    except Exception as err:
        ten_env.log_warn(f"GetProperty {property_name} failed: {err}")
        return 0.0

def get_properties_float(ten_env: AsyncTenEnv, property_names: list[str], callback: Callable[[str, float], None]) -> None:
    """Helper to get float properties from ten_env with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_float(ten_env, property_name))

class AsyncEventEmitter:
    def __init__(self):
        self.listeners = {}

    def on(self, event_name, listener):
        """Register an event listener."""
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(listener)

    def emit(self, event_name, *args, **kwargs):
        """Fire the event without waiting for listeners to finish."""
        if event_name in self.listeners:
            for listener in self.listeners[event_name]:
                asyncio.create_task(listener(*args, **kwargs))


class AsyncQueue:
    def __init__(self):
        self._queue = deque()  # Use deque for efficient prepend and append
        self._condition = asyncio.Condition()  # Use Condition to manage access

    async def put(self, item, prepend=False):
        """Add an item to the queue (prepend if specified)."""
        async with self._condition:
            if prepend:
                self._queue.appendleft(item)  # Prepend item to the front
            else:
                self._queue.append(item)  # Append item to the back
            self._condition.notify() 

    async def get(self):
        """Remove and return an item from the queue."""
        async with self._condition:
            while not self._queue:
                await self._condition.wait()  # Wait until an item is available
            return self._queue.popleft()  # Pop from the front of the deque

    async def flush(self):
        """Flush all items from the queue."""
        async with self._condition:
            while self._queue:
                self._queue.popleft()  # Clear the queue
            self._condition.notify_all()  # Notify all consumers that the queue is empty

    def __len__(self):
        """Return the current size of the queue."""
        return len(self._queue)

def write_pcm_to_file(buffer: bytearray, file_name: str) -> None:
    """Helper function to write PCM data to a file."""
    with open(file_name, "ab") as f:  # append to file
        f.write(buffer)


def generate_file_name(prefix: str) -> str:
    # Create a timestamp for the file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.pcm"

class PCMWriter:
    def __init__(self, prefix: str, write_pcm: bool, buffer_size: int = 1024 * 64):
        self.write_pcm = write_pcm
        self.buffer = bytearray()
        self.buffer_size = buffer_size
        self.file_name = generate_file_name(prefix) if write_pcm else None
        self.loop = asyncio.get_event_loop()

    async def write(self, data: bytes) -> None:
        """Accumulate data into the buffer and write to file when necessary."""
        if not self.write_pcm:
            return

        self.buffer.extend(data)

        # Write to file if buffer is full
        if len(self.buffer) >= self.buffer_size:
            await self._flush()

    async def flush(self) -> None:
        """Write any remaining data in the buffer to the file."""
        if self.write_pcm and self.buffer:
            await self._flush()

    async def _flush(self) -> None:
        """Helper method to write the buffer to the file."""
        if self.file_name:
            await self.loop.run_in_executor(
                None,
                functools.partial(write_pcm_to_file, self.buffer[:], self.file_name),
            )
        self.buffer.clear()