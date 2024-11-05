#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import threading


class ChatMemory:
    def __init__(self, max_history_length):
        self.max_history_length = max_history_length
        self.history = []
        self.mutex = threading.Lock()  # TODO: no need lock for asyncio

    def put(self, message):
        with self.mutex:
            self.history.append(message)

            while True:
                history_count = len(self.history)
                if history_count > 0 and history_count > self.max_history_length:
                    self.history.pop(0)
                    continue
                if history_count > 0 and self.history[0]["role"] == "assistant":
                    # we cannot have an assistant message at the start of the chat history
                    # if after removal of the first, we have an assistant message,
                    # we need to remove the assistant message too
                    self.history.pop(0)
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
