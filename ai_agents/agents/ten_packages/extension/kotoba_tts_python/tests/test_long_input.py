#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Long input: one long text, many streamed deltas, and flush under a deep
sentence backlog. The segmenter and the per-request segment queue are this
extension's own logic, so they are exercised at length here."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import events_after, make_config, run_tester  # noqa: E402


def _sentences(n: int) -> list[str]:
    return [
        f"これは長い入力の{i}番目の文で、文字数を増やすために同じ言い回しを"
        f"少し長めに続けていますが、百二十文字の上限には届きません。"
        for i in range(1, n + 1)
    ]


def test_long_single_input_is_segmented_and_spoken_in_order():
    sentences = _sentences(40)
    text = "".join(sentences)
    assert len(text) > 2000
    server = FakeKotobaServer(
        Scenario(chunks_per_response=1, chunk_delay_s=0.005)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "long", text, end=True)
            end = await tester.wait_for_audio_end("long", timeout_s=15.0)
            assert end.payload["reason"] == 1
            assert tester.recording.audio_bytes("long") == server.expected_pcm(
                len(sentences)
            )
            assert len(tester.recording.named("tts_audio_start")) == 1
            assert tester.recording.named("error") == []

        run_tester(script, make_config(server.url), timeout_s=30.0)
        # One service request per sentence, in order, nothing lost.
        assert server.recorded.texts == sentences
        assert server.recorded.connections == 1
    finally:
        server.stop()


def test_streamed_deltas_under_backlog_keep_sentence_order():
    """Sixty deltas, two per sentence, sent without waiting: the worker
    must speak the thirty sentences in order while the queue is deep."""
    sentences = _sentences(30)
    server = FakeKotobaServer(
        Scenario(chunks_per_response=1, chunk_delay_s=0.02)
    ).start()
    try:

        async def script(tester, ten_env):
            for i, sentence in enumerate(sentences):
                cut = len(sentence) // 2
                last = i == len(sentences) - 1
                await tester.send_text(
                    ten_env, "stream", sentence[:cut], end=False
                )
                await tester.send_text(
                    ten_env, "stream", sentence[cut:], end=last
                )
            end = await tester.wait_for_audio_end("stream", timeout_s=15.0)
            assert end.payload["reason"] == 1
            assert tester.recording.audio_bytes(
                "stream"
            ) == server.expected_pcm(len(sentences))

        run_tester(script, make_config(server.url), timeout_s=30.0)
        assert server.recorded.texts == sentences
    finally:
        server.stop()


def test_flush_under_backlog_cancels_once_and_recovers():
    """Thirty sentences queued, flush while the first is streaming: one
    INTERRUPTED end, the backlog is dropped (at most the sentence in flight
    and the one already sent reach the service), and the next request
    works on the same connection."""
    sentences = _sentences(30)
    server = FakeKotobaServer(
        Scenario(chunks_per_response=4, chunk_delay_s=0.05)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(
                ten_env, "backlog", "".join(sentences), end=True
            )
            await tester.wait_for_event("pcm_frame", count=2)
            t0 = time.monotonic()
            await tester.send_flush(ten_env, "flush-backlog")
            flush_end = (await tester.wait_for_event("tts_flush_end"))[0]
            assert time.monotonic() - t0 < 1.0
            end = await tester.wait_for_audio_end("backlog", timeout_s=0.5)
            assert end.payload["reason"] == 2
            assert end.at <= flush_end.at
            late = [
                f
                for f in events_after(tester, "pcm_frame", flush_end)
                if f.payload.get("request_id") == "backlog"
            ]
            assert late == []
            sent_before_flush = len(server.recorded.texts)
            assert sent_before_flush <= 2, sent_before_flush
            await tester.send_text(ten_env, "after", "復旧。", end=True)
            end2 = await tester.wait_for_audio_end("after")
            assert end2.payload["reason"] == 1
            assert tester.recording.audio_bytes("after") == server.expected_pcm(
                1
            )
            # Nothing from the dropped backlog was sent after the flush.
            assert server.recorded.texts[sent_before_flush:] == ["復旧。"]

        run_tester(script, make_config(server.url))
        assert server.recorded.cancels == 1
    finally:
        server.stop()
