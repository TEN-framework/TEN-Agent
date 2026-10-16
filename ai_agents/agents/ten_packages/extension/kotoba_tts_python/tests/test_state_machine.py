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
from helpers import make_config, run_tester  # noqa: E402


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
