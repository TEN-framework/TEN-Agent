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
from ten.data import Data
from .log import logger
from PIL import Image
from datetime import datetime
from io import BytesIO
from base64 import b64encode


def get_property_bool(data: Data, property_name: str) -> bool:
    """Helper to get boolean property from data with error handling."""
    try:
        return data.get_property_bool(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return False

def get_properties_bool(data: Data, property_names: list[str], callback: Callable[[str, bool], None]) -> None:
    """Helper to get boolean properties from data with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_bool(data, property_name))


def get_property_string(data: Data, property_name: str) -> str:
    """Helper to get string property from data with error handling."""
    try:
        return data.get_property_string(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return ""


def get_properties_string(data: Data, property_names: list[str], callback: Callable[[str, str], None]) -> None:
    """Helper to get string properties from data with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_string(data, property_name))

def get_property_int(data: Data, property_name: str) -> int:
    """Helper to get int property from data with error handling."""
    try:
        return data.get_property_int(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return 0
    
def get_properties_int(data: Data, property_names: list[str], callback: Callable[[str, int], None]) -> None:
    """Helper to get int properties from data with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_int(data, property_name))
    
def get_property_float(data: Data, property_name: str) -> float:
    """Helper to get float property from data with error handling."""
    try:
        return data.get_property_float(property_name)
    except Exception as err:
        logger.warn(f"GetProperty {property_name} failed: {err}")
        return 0.0

def get_properties_float(data: Data, property_names: list[str], callback: Callable[[str, float], None]) -> None:
    """Helper to get float properties from data with error handling."""
    for property_name in property_names:
        callback(property_name, get_property_float(data, property_name))

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