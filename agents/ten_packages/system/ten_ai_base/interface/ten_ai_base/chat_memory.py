#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import threading
import asyncio

from typing import Dict, List

EVENT_MEMORY_EXPIRED = "memory_expired"
EVENT_MEMORY_APPENDED = "memory_appended"

class ChatMemory:
    def __init__(self, max_history_length):
        self.max_history_length = max_history_length
        self.history = []
        self.mutex = threading.Lock()  # TODO: no need lock for asyncio
        self.listeners: Dict[str, List] = {}

    def put(self, message):
        with self.mutex:
            self.history.append(message)
            self.emit(EVENT_MEMORY_APPENDED, message)

            while True:
                history_count = len(self.history)
                if history_count > 0 and history_count > self.max_history_length:
                    self.emit(EVENT_MEMORY_EXPIRED, self.history.pop(0))
                    continue
                if history_count > 0 and (self.history[0]["role"] == "assistant" or self.history[0]["role"] == "tool"):
                    # we cannot have an assistant message at the start of the chat history
                    # if after removal of the first, we have an assistant message,
                    # we need to remove the assistant message too
                    self.emit(EVENT_MEMORY_EXPIRED, self.history.pop(0))
                    continue
                break

    def get(self):
        with self.mutex:
            return self.history

    def count(self):
        with self.mutex:
            return len(self.history)

    def clear(self):
        with self.mutex:
            self.history = []

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
