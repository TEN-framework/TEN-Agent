#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
from collections import deque
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