#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Appended text, sequential and interleaved requests, late input."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import ThreadGate, make_config, run_tester  # noqa: E402


async def _wait_until(predicate, timeout_s: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.02)


def test_deltas_release_sentences_as_they_complete():
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "r1", "今日は", end=False)
            await tester.send_text(ten_env, "r1", "いい天気ですね。", end=False)
            await tester.send_text(ten_env, "r1", "明日も晴れ", end=False)
            await _wait_until(
                lambda: server.recorded.texts == ["今日はいい天気ですね。"]
            )
            await tester.wait_for_event("pcm_frame")
            # The request stays open: no end event yet.
            await asyncio.sleep(0.2)
            assert tester.recording.named("tts_audio_end") == []
            await tester.send_text(ten_env, "r1", "でしょう。", end=True)
            end = await tester.wait_for_audio_end("r1")
            rec = tester.recording
            assert server.recorded.texts == [
                "今日はいい天気ですね。",
                "明日も晴れでしょう。",
            ]
            assert len(rec.named("tts_audio_start")) == 1
            assert rec.audio_bytes("r1") == server.expected_pcm(2)
            assert end.payload["reason"] == 1
            assert rec.named("error") == []

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 1
    finally:
        server.stop()


def test_sequential_requests_keep_separate_counters():
    server = FakeKotobaServer(Scenario(chunks_per_response=3)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "a", "一文目。", end=True)
            end_a = await tester.wait_for_audio_end("a")
            await tester.send_text(ten_env, "b", "一文目。二文目。", end=True)
            end_b = await tester.wait_for_audio_end("b")
            rec = tester.recording
            assert rec.audio_bytes("a") == server.expected_pcm(1)
            assert rec.audio_bytes("b") == server.expected_pcm(2)
            dur_a = end_a.payload["request_total_audio_duration_ms"]
            dur_b = end_b.payload["request_total_audio_duration_ms"]
            assert dur_b == 2 * dur_a
            starts = [
                e.payload["request_id"] for e in rec.named("tts_audio_start")
            ]
            assert starts == ["a", "b"]
            ends = [e.payload["request_id"] for e in rec.named("tts_audio_end")]
            assert ends == ["a", "b"]
            assert rec.sequence("a") == [
                "tts_audio_start",
                "pcm_frame",
                "tts_audio_end",
            ]
            assert rec.sequence("b") == [
                "tts_audio_start",
                "pcm_frame",
                "tts_audio_end",
            ]

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["一文目。", "一文目。", "二文目。"]
    finally:
        server.stop()


def test_interleaved_request_ids_stay_isolated_and_ordered():
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "x", "Xの前半、", end=False)
            await tester.send_text(ten_env, "y", "Yの前半、", end=False)
            await tester.send_text(ten_env, "x", "Xの後半。", end=True)
            await tester.send_text(ten_env, "y", "Yの後半。", end=True)
            await tester.wait_for_audio_end("x")
            await tester.wait_for_audio_end("y")
            rec = tester.recording
            ends = [e.payload["request_id"] for e in rec.named("tts_audio_end")]
            assert ends == ["x", "y"]
            assert rec.audio_bytes("x") == server.expected_pcm(1)
            assert rec.audio_bytes("y") == server.expected_pcm(1)
            for e in rec.named("tts_audio_end"):
                assert e.payload["reason"] == 1
            assert rec.named("error") == []

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == [
            "Xの前半、Xの後半。",
            "Yの前半、Yの後半。",
        ]
    finally:
        server.stop()


def test_late_text_for_finished_request_is_ignored():
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "done", "終わり。", end=True)
            await tester.wait_for_audio_end("done")
            frames_before = len(tester.recording.frames)
            await tester.send_text(ten_env, "done", "遅れた文。", end=True)
            await asyncio.sleep(0.4)
            rec = tester.recording
            assert len(rec.frames) == frames_before
            assert len(rec.named("tts_audio_end")) == 1
            assert rec.named("error") == []
            await tester.send_text(ten_env, "next", "次の文。", end=True)
            await tester.wait_for_audio_end("next")

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["終わり。", "次の文。"]
    finally:
        server.stop()


def test_unterminated_tail_is_sent_at_text_input_end():
    """Main control ends a turn with an empty final input; a tail without
    a terminator must still be synthesized then."""
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "tail", "今日は", end=False)
            await tester.send_text(ten_env, "tail", "", end=True)
            end = await tester.wait_for_audio_end("tail")
            assert end.payload["reason"] == 1
            assert tester.recording.audio_bytes("tail") == server.expected_pcm(
                1
            )
            await tester.send_text(ten_env, "tail2", "明日は晴れ", end=True)
            await tester.wait_for_audio_end("tail2")

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["今日は", "明日は晴れ"]
    finally:
        server.stop()


def test_completed_id_history_evicts_oldest():
    """With the history shortened to two ids, the first request id is
    forgotten after two more requests and is treated as new again."""
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    server = FakeKotobaServer(Scenario(chunks_per_response=1)).start()
    try:
        with patch.object(ext_mod, "_COMPLETED_HISTORY", 2):

            async def script(tester, ten_env):
                for rid in ("r1", "r2", "r3"):
                    await tester.send_text(ten_env, rid, f"{rid}。", end=True)
                    await tester.wait_for_audio_end(rid)
                # r1 was evicted: its id is accepted as a fresh request.
                await tester.send_text(ten_env, "r1", "再び。", end=True)
                await tester.wait_for(
                    lambda r: sum(
                        1
                        for e in r.named("tts_audio_end")
                        if e.payload["request_id"] == "r1"
                    )
                    == 2,
                    timeout_s=5.0,
                )
                assert tester.recording.named("error") == []

            run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["r1。", "r2。", "r3。", "再び。"]
    finally:
        server.stop()


def _usage(tester, request_id: str) -> list:
    return [
        e
        for e in tester.recording.named("metrics")
        if "recv_audio_duration" in e.payload.get("metrics", {})
        and e.payload["metadata"].get("request_id") == request_id
    ]


def test_late_input_while_usage_settles_does_not_release_the_next_request():
    """A's usage send is held after its counters were read. B waits in the
    base queue, then a late delta for A arrives. That delta must not
    release B early: B may start only after A's terminal sequence is done,
    and B's usage must hold exactly its own text and audio."""
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    server = FakeKotobaServer(
        Scenario(chunks_per_response=20, chunk_delay_s=0.05)
    ).start()
    original = ext_mod.KotobaTTSExtension.send_metrics
    entered, release = ThreadGate(), ThreadGate()
    state = {"held": False}

    async def gated_send_metrics(self, metrics, request_id=""):
        is_usage = "recv_audio_duration" in metrics.metrics
        if is_usage and request_id == "A" and not state["held"]:
            state["held"] = True
            entered.set()
            await release.wait()
        return await original(self, metrics, request_id)

    try:
        with patch.object(
            ext_mod.KotobaTTSExtension, "send_metrics", gated_send_metrics
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "A", "前。", end=True)
                await tester.wait_for_audio_end("A", timeout_s=5.0)
                await asyncio.wait_for(entered.wait(), 5.0)
                # A's usage is in flight. B queues behind A, then a late
                # delta for A arrives.
                await tester.send_text(ten_env, "B", "後ろの文。", end=True)
                await tester.send_text(ten_env, "A", "遅い。", end=True)
                await asyncio.sleep(0.8)
                b_before_release = len(tester.recording.audio_bytes("B"))
                release.set()
                await tester.wait_for_audio_end("B", timeout_s=8.0)
                await tester.wait_for(
                    lambda r: len(_usage(tester, "B")) >= 1, timeout_s=2.0
                )
                assert (
                    b_before_release == 0
                ), "B started while A's usage was still in flight"
                usage_a, usage_b = _usage(tester, "A"), _usage(tester, "B")
                assert len(usage_a) == 1 and len(usage_b) == 1
                assert usage_a[0].payload["metrics"]["input_characters"] == (
                    len("前。")
                )
                b = usage_b[0].payload["metrics"]
                assert b["input_characters"] == len("後ろの文。"), b
                assert b["recv_audio_duration"] == (
                    len(tester.recording.audio_bytes("B")) * 1000 / 32000
                ), b

            run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["前。", "後ろの文。"]
    finally:
        release.set()
        server.stop()


def test_late_input_after_input_end_is_not_spoken_or_counted():
    """A late delta for a request whose text_input_end already arrived,
    while that request is still speaking: it is neither sent to the
    service nor counted in the request's usage."""
    sentences = ["一つ目の文。", "二つ目の文。", "三つ目の文。"]
    server = FakeKotobaServer(
        Scenario(chunks_per_response=4, chunk_delay_s=0.05)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "L", "".join(sentences), end=True)
            await tester.wait_for_event("pcm_frame", count=1)
            await tester.send_text(ten_env, "L", "余分な文。", end=True)
            end = await tester.wait_for_audio_end("L", timeout_s=8.0)
            assert end.payload["reason"] == 1
            await tester.wait_for(
                lambda r: len(_usage(tester, "L")) >= 1, timeout_s=2.0
            )
            usage = _usage(tester, "L")
            assert len(usage) == 1
            assert usage[0].payload["metrics"]["input_characters"] == len(
                "".join(sentences)
            )
            assert tester.recording.audio_bytes("L") == server.expected_pcm(
                len(sentences)
            )
            assert len(tester.recording.named("tts_audio_end")) == 1

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == sentences
    finally:
        server.stop()
