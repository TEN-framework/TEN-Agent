#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Core request lifecycle against the fake Kotoba service."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import make_config, run_tester  # noqa: E402

SAMPLE_WIDTH = 2
CHANNELS = 1


def test_single_request_emits_ordered_events_and_exact_pcm():
    server = FakeKotobaServer(Scenario(chunks_per_response=4)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(
                ten_env, "req-1", "こんにちは、世界。", end=True
            )
            end = await tester.wait_for_audio_end("req-1")
            rec = tester.recording
            assert rec.sequence() == [
                "tts_audio_start",
                "pcm_frame",
                "tts_audio_end",
            ], rec.sequence()
            starts = rec.named("tts_audio_start")
            assert len(starts) == 1
            assert starts[0].payload["request_id"] == "req-1"
            assert rec.audio_bytes("req-1") == server.expected_pcm(1)
            assert {rate for _, _, rate in rec.frames} == {16000}
            assert end.payload["reason"] == 1
            expected_ms = (
                len(server.expected_pcm(1))
                * 1000
                // (16000 * SAMPLE_WIDTH * CHANNELS)
            )
            assert end.payload["request_total_audio_duration_ms"] == expected_ms
            assert end.payload["request_event_interval_ms"] >= 0
            assert rec.named("error") == []
            assert len(rec.named("tts_audio_end")) == 1

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["こんにちは、世界。"]
        assert server.recorded.opens[0]["format"] == "pcm16"
        assert server.recorded.opens[0]["sample_rate"] == 16000
        assert server.recorded.opens[0]["language"] == "ja"
        assert server.recorded.opens[0]["speaker_id"] == "male-01"
        assert "key" not in server.recorded.opens[0]
    finally:
        server.stop()


def test_configured_sample_rate_and_voice_reach_the_service():
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "req-24k", "テスト。", end=True)
            end = await tester.wait_for_audio_end("req-24k")
            rec = tester.recording
            assert {rate for _, _, rate in rec.frames} == {24000}
            expected_ms = (
                len(server.expected_pcm(1)) * 1000 // (24000 * SAMPLE_WIDTH)
            )
            assert end.payload["request_total_audio_duration_ms"] == expected_ms

        run_tester(
            script,
            make_config(
                server.url,
                params={"sample_rate": 24000, "speaker_id": "female-01"},
            ),
        )
        assert server.recorded.opens[0]["sample_rate"] == 24000
        assert server.recorded.opens[0]["speaker_id"] == "female-01"
    finally:
        server.stop()


def test_empty_text_ends_fast_without_contacting_the_service():
    server = FakeKotobaServer().start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "empty-1", "   ", end=True)
            end = await tester.wait_for_audio_end("empty-1", timeout_s=0.5)
            rec = tester.recording
            assert rec.frames == []
            assert rec.named("tts_audio_start") == []
            assert rec.named("error") == []
            assert end.payload["request_total_audio_duration_ms"] == 0
            assert end.payload["request_event_interval_ms"] == 0
            assert end.payload["reason"] == 1

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 0
    finally:
        server.stop()


def test_repeated_empty_requests_with_same_id_end_once_without_errors():
    server = FakeKotobaServer().start()
    try:

        async def script(tester, ten_env):
            for text in ("", " ", ""):
                await tester.send_text(ten_env, "999", text, end=True)
            await tester.wait_for_audio_end("999", timeout_s=1.0)
            # Give late inputs time to arrive; they must stay silent.
            import asyncio

            await asyncio.sleep(0.3)
            rec = tester.recording
            assert len(rec.named("tts_audio_end")) == 1
            assert rec.named("error") == []
            # The queue is released: a new request still works.
            await tester.send_text(ten_env, "after-999", "次。", end=True)
            end = await tester.wait_for_audio_end("after-999")
            assert end.payload["request_total_audio_duration_ms"] > 0

        run_tester(script, make_config(server.url))
    finally:
        server.stop()
