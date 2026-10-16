#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Flush / cancellation boundaries."""
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


def test_flush_after_audio_started_interrupts_once_and_stays_silent():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=40, chunk_delay_s=0.05)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "long", "長い文章です。", end=True)
            await tester.wait_for_event("pcm_frame", count=2)
            await tester.send_flush(ten_env, "flush-A")
            flush_end = (await tester.wait_for_event("tts_flush_end"))[0]
            assert flush_end.payload["flush_id"] == "flush-A"
            end = await tester.wait_for_audio_end("long", timeout_s=1.0)
            assert end.payload["reason"] == 2
            rec = tester.recording
            emitted = len(rec.audio_bytes("long"))
            assert 0 < emitted < len(server.expected_pcm(1))
            assert end.payload["request_total_audio_duration_ms"] == (
                emitted * 1000 // (16000 * 2)
            )
            assert end.payload["request_event_interval_ms"] > 0
            frames_at_flush = len(rec.frames)
            await asyncio.sleep(0.6)
            assert len(rec.frames) == frames_at_flush
            assert len(rec.named("tts_audio_end")) == 1
            assert rec.named("error") == []
            # The next request works on the same socket.
            await tester.send_text(ten_env, "after", "次。", end=True)
            end2 = await tester.wait_for_audio_end("after")
            assert end2.payload["reason"] == 1
            assert rec.audio_bytes("after") == server.expected_pcm(1)

        run_tester(script, make_config(server.url))
        assert server.recorded.cancels == 1
        assert server.recorded.responses_cancelled == 1
        assert server.recorded.connections == 1
    finally:
        server.stop()


def test_flush_before_first_audio_reports_zero_and_no_start():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, first_chunk_delay_s=1.5)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "slow", "遅い応答。", end=True)
            await _wait_until(lambda: server.recorded.texts == ["遅い応答。"])
            await tester.send_flush(ten_env, "flush-B")
            await tester.wait_for_event("tts_flush_end")
            end = await tester.wait_for_audio_end("slow", timeout_s=1.0)
            rec = tester.recording
            assert end.payload["reason"] == 2
            assert end.payload["request_total_audio_duration_ms"] == 0
            assert end.payload["request_event_interval_ms"] == 0
            assert rec.named("tts_audio_start") == []
            await asyncio.sleep(0.5)
            assert rec.frames == []
            await tester.send_text(ten_env, "after", "次。", end=True)
            await tester.wait_for_audio_end("after", timeout_s=5.0)
            assert rec.audio_bytes("after") == server.expected_pcm(1)

        run_tester(script, make_config(server.url))
        assert server.recorded.cancels == 1
    finally:
        server.stop()


def test_flush_with_nothing_active_only_acknowledges():
    server = FakeKotobaServer().start()
    try:

        async def script(tester, ten_env):
            await tester.send_flush(ten_env, "flush-C")
            await tester.wait_for_event("tts_flush_end")
            await asyncio.sleep(0.2)
            rec = tester.recording
            assert rec.named("tts_audio_end") == []
            assert rec.named("error") == []

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 0
    finally:
        server.stop()


def test_buffered_text_is_dropped_by_flush():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=30, chunk_delay_s=0.05)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(
                ten_env, "multi", "一文目。二文目。三文目。", end=True
            )
            await tester.wait_for_event("pcm_frame")
            await tester.send_flush(ten_env, "flush-D")
            await tester.wait_for_event("tts_flush_end")
            await tester.wait_for_audio_end("multi", timeout_s=1.0)
            await asyncio.sleep(0.5)

        run_tester(script, make_config(server.url))
        # Only the first sentence ever reached the service.
        assert server.recorded.texts == ["一文目。"]
    finally:
        server.stop()
