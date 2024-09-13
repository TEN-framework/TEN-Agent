import asyncio


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