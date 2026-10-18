#
# Stream parser for extracting <think>...</think> reasoning blocks from
# tokenized content deltas.
#
from __future__ import annotations

from typing import List, Tuple


class ThinkParser:
    OPEN_TAG = "<think>"
    CLOSE_TAG = "</think>"

    def __init__(self):
        self.state = "NORMAL"  # States: 'NORMAL', 'THINK'
        self.think_content = ""
        self.think_delta = ""
        self._pending = ""

    def _partial_suffix_len(self, text: str, tag: str) -> int:
        max_len = min(len(text), len(tag) - 1)
        for size in range(max_len, 0, -1):
            if text.endswith(tag[:size]):
                return size
        return 0

    def process_content(self, new_chars: str) -> List[Tuple[str, str]]:
        events: List[Tuple[str, str]] = []
        if not new_chars:
            return events

        data = self._pending + new_chars
        self._pending = ""
        idx = 0

        while idx < len(data):
            if self.state == "NORMAL":
                open_pos = data.find(self.OPEN_TAG, idx)
                if open_pos < 0:
                    partial = self._partial_suffix_len(
                        data[idx:], self.OPEN_TAG
                    )
                    visible = (
                        data[idx : len(data) - partial]
                        if partial
                        else data[idx:]
                    )
                    if visible:
                        events.append(("message_delta", visible))
                    if partial:
                        self._pending = data[len(data) - partial :]
                    break

                if open_pos > idx:
                    events.append(("message_delta", data[idx:open_pos]))

                self.state = "THINK"
                self.think_delta = ""
                idx = open_pos + len(self.OPEN_TAG)
                continue

            close_pos = data.find(self.CLOSE_TAG, idx)
            if close_pos < 0:
                partial = self._partial_suffix_len(data[idx:], self.CLOSE_TAG)
                think_text = (
                    data[idx : len(data) - partial] if partial else data[idx:]
                )
                if think_text:
                    self.think_content += think_text
                    self.think_delta = think_text
                    events.append(("reasoning_delta", think_text))
                if partial:
                    self._pending = data[len(data) - partial :]
                break

            think_text = data[idx:close_pos]
            if think_text:
                self.think_content += think_text
                self.think_delta = think_text
                events.append(("reasoning_delta", think_text))

            events.append(("reasoning_done", self.think_content))
            self.think_content = ""
            self.think_delta = ""
            self.state = "NORMAL"
            idx = close_pos + len(self.CLOSE_TAG)

        return events

    def process_reasoning_content(
        self, reasoning_content: str
    ) -> List[Tuple[str, str]]:
        events: List[Tuple[str, str]] = []
        if reasoning_content:
            if self.state == "NORMAL":
                self.state = "THINK"
            self.think_content += reasoning_content
            self.think_delta = reasoning_content
            events.append(("reasoning_delta", reasoning_content))
        elif self.state == "THINK":
            events.append(("reasoning_done", self.think_content))
            self.state = "NORMAL"
            self.think_delta = ""
            self.think_content = ""
        return events

    def process(self, new_chars):
        prev_state = self.state
        events = self.process_content(new_chars)
        return prev_state != self.state or any(
            event_type == "reasoning_done" for event_type, _ in events
        )

    def process_by_reasoning_content(self, reasoning_content):
        prev_state = self.state
        events = self.process_reasoning_content(reasoning_content)
        return prev_state != self.state or any(
            event_type == "reasoning_done" for event_type, _ in events
        )

    def finalize(self) -> List[Tuple[str, str]]:
        events: List[Tuple[str, str]] = []
        if self._pending:
            if self.state == "NORMAL":
                events.append(("message_delta", self._pending))
            else:
                self.think_content += self._pending
                self.think_delta = self._pending
                events.append(("reasoning_delta", self._pending))
            self._pending = ""

        if self.state == "THINK":
            events.append(("reasoning_done", self.think_content))
            self.state = "NORMAL"
            self.think_delta = ""
            self.think_content = ""
        return events
