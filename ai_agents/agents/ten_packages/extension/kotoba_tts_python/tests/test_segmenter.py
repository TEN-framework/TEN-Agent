#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Pure unit tests for ``SentenceBuffer``; no TEN runtime needed."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from segmenter import SentenceBuffer  # noqa: E402


@pytest.mark.parametrize(
    ("deltas", "released", "pending"),
    [
        pytest.param(
            ["こんにちは。", "元気ですか？"],
            ["こんにちは。", "元気ですか？"],
            "",
            id="japanese-one-sentence-per-delta",
        ),
        pytest.param(
            ["今日は", "いい天気", "ですね。明日も"],
            ["今日はいい天気ですね。"],
            "明日も",
            id="japanese-split-mid-delta",
        ),
        pytest.param(
            ["Hello there.", " How are you?"],
            ["Hello there.", "How are you?"],
            "",
            id="ascii-terminator-at-delta-end",
        ),
        pytest.param(
            ["Pi is 3.", "14 exactly. Done"],
            ["Pi is 3.14 exactly."],
            "Done",
            id="decimal-point-not-a-boundary",
        ),
        pytest.param(
            ["He said 「はい。」 then left."],
            ["He said 「はい。」", "then left."],
            "",
            id="closing-quote-stays-with-sentence",
        ),
        pytest.param(
            ["Line one\nLine two"],
            ["Line one"],
            "Line two",
            id="newline-is-a-boundary",
        ),
        pytest.param(
            ["   ", "。"],
            [],
            "",
            id="blank-sentence-dropped",
        ),
    ],
)
def test_push_releases_complete_sentences(deltas, released, pending):
    buf = SentenceBuffer(soft_limit_chars=120)
    got: list[str] = []
    for delta in deltas:
        got.extend(buf.push(delta))
    assert got == released
    assert buf.pending == pending


def test_flush_returns_remainder_once():
    buf = SentenceBuffer()
    assert buf.push("未完の文") == []
    assert buf.flush() == "未完の文"
    assert buf.flush() is None
    assert buf.pending == ""


def test_soft_limit_cuts_at_comma():
    buf = SentenceBuffer(soft_limit_chars=10)
    out = buf.push("一二三四五、六七八九十一二三四五六七八九十")
    assert out == ["一二三四五、"]
    assert buf.pending == "六七八九十一二三四五六七八九十"


def test_hard_limit_bounds_buffer_without_break_points():
    buf = SentenceBuffer(soft_limit_chars=5)
    out = buf.push("a" * 23)
    assert out == ["a" * 10, "a" * 10]
    assert buf.pending == "aaa"


def test_hard_limit_prefers_space():
    buf = SentenceBuffer(soft_limit_chars=5)
    out = buf.push("word another third")
    assert out == ["word", "another"]
    assert buf.pending == "third"


def test_punctuation_only_is_never_released():
    buf = SentenceBuffer()
    assert buf.push("。。。") == []
    assert buf.push("...!?") == []
    assert buf.flush() is None


def test_rejects_invalid_soft_limit():
    with pytest.raises(ValueError):
        SentenceBuffer(soft_limit_chars=0)
