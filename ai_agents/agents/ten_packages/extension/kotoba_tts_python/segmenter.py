#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Sentence buffering for streamed LLM text.

The Kotoba TTS service synthesizes one complete text per response, while
TEN delivers LLM output as many small deltas. ``SentenceBuffer`` collects
deltas and releases complete sentences, so each sentence becomes one
service request as soon as it is complete.
"""

# Terminators that always end a sentence, wherever they appear.
_HARD_TERMINATORS = "。！？\n"
# Terminators that end a sentence only when followed by a space, a closing
# quote or bracket, or the end of the delta (so ``3.14`` stays whole).
_ASCII_TERMINATORS = ".!?"
# Soft break points used only when the buffer grows past the soft limit.
_SOFT_TERMINATORS = "、，,;；"
# Characters that belong to the sentence they close.
_CLOSERS = '」』”’")）】》'


class SentenceBuffer:
    def __init__(self, soft_limit_chars: int = 120) -> None:
        if soft_limit_chars < 1:
            raise ValueError("soft_limit_chars must be >= 1")
        self._soft_limit = soft_limit_chars
        self._buffer = ""

    @property
    def pending(self) -> str:
        """Text received but not yet released."""
        return self._buffer

    def push(self, text: str) -> list[str]:
        """Append ``text`` and return the sentences that are now complete."""
        if not text:
            return []
        self._buffer += text
        segments: list[str] = []
        while True:
            cut = self._find_boundary(self._buffer)
            if cut is None:
                break
            segments.append(self._buffer[:cut])
            self._buffer = self._buffer[cut:].lstrip()
        segments.extend(self._cut_oversized())
        return [s.strip() for s in segments if _has_speech(s)]

    def flush(self) -> str | None:
        """Release whatever is buffered, or ``None`` when nothing in it
        can be spoken (blank or punctuation only)."""
        rest = self._buffer.strip()
        self._buffer = ""
        return rest if _has_speech(rest) else None

    def clear(self) -> None:
        self._buffer = ""

    def _find_boundary(self, text: str) -> int | None:
        """Index just past the first sentence end, or ``None``."""
        length = len(text)
        for i, ch in enumerate(text):
            if ch in _HARD_TERMINATORS:
                return self._extend_over_closers(text, i + 1)
            if ch in _ASCII_TERMINATORS:
                prev_is_digit = i > 0 and text[i - 1].isdigit()
                if i + 1 >= length:
                    if ch == "." and prev_is_digit:
                        return None
                    return length
                nxt = text[i + 1]
                if nxt.isspace() or nxt in _CLOSERS:
                    return self._extend_over_closers(text, i + 1)
        return None

    @staticmethod
    def _extend_over_closers(text: str, index: int) -> int:
        while index < len(text) and text[index] in _CLOSERS:
            index += 1
        return index

    def _cut_oversized(self) -> list[str]:
        """Bound the buffer: cut at a soft break past the soft limit, and
        unconditionally at twice the soft limit."""
        segments: list[str] = []
        while len(self._buffer) > self._soft_limit:
            window = self._buffer[: self._soft_limit * 2]
            cut = -1
            for j in range(len(window) - 1, -1, -1):
                if window[j] in _SOFT_TERMINATORS:
                    cut = j + 1
                    break
            if cut == -1:
                if len(self._buffer) <= self._soft_limit * 2:
                    break
                space = window.rfind(" ")
                cut = space + 1 if space > 0 else len(window)
            segments.append(self._buffer[:cut])
            self._buffer = self._buffer[cut:].lstrip()
        return segments


def _has_speech(text: str) -> bool:
    """True when ``text`` holds at least one letter or digit."""
    return any(ch.isalnum() for ch in text)
