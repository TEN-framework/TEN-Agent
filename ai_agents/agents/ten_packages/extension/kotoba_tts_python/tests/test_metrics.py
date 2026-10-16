#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""TTFB, request and usage metrics are request-scoped and emitted once."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import make_config, run_tester  # noqa: E402


def _metrics(tester, key: str):
    return [
        e
        for e in tester.recording.named("metrics")
        if key in e.payload.get("metrics", {})
    ]


def test_ttfb_once_per_request_and_request_bytes_match_text():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, first_chunk_delay_s=0.2)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "m1", "一文目。二文目。", end=True)
            await tester.wait_for_audio_end("m1")
            await tester.send_text(ten_env, "m2", "三文目。", end=True)
            await tester.wait_for_audio_end("m2")
            # Usage follows audio_end; wait for m2's before reading.
            await tester.wait_for(
                lambda r: any(
                    e.payload["metadata"].get("request_id") == "m2"
                    for e in r.named("metrics")
                    if "recv_audio_duration" in e.payload.get("metrics", {})
                ),
                timeout_s=2.0,
            )

            ttfb = _metrics(tester, "ttfb")
            assert [e.payload["metadata"]["request_id"] for e in ttfb] == [
                "m1",
                "m2",
            ]
            for e in ttfb:
                assert e.payload["vendor"] == "kotoba"
                # First chunk is held 200 ms by the fake service.
                assert 150 <= e.payload["metrics"]["ttfb"] < 3000
                assert e.payload["metadata"]["speaker_id"] == "male-01"

            requests = _metrics(tester, "request_bytes")
            sizes = [e.payload["metrics"]["request_bytes"] for e in requests]
            assert sizes == [
                len("一文目。".encode()),
                len("二文目。".encode()),
                len("三文目。".encode()),
            ]

            usage = _metrics(tester, "recv_audio_duration")
            per_request = [
                e for e in usage if e.payload["metadata"].get("request_id")
            ]
            assert [
                e.payload["metadata"]["request_id"] for e in per_request
            ] == [
                "m1",
                "m2",
            ]
            chunk_ms = 800 * 1000 / 16000
            assert per_request[0].payload["metrics"]["recv_audio_duration"] == (
                2 * 3 * chunk_ms
            )
            assert per_request[1].payload["metrics"]["recv_audio_duration"] == (
                3 * chunk_ms
            )

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_no_ttfb_when_no_audio():
    server = FakeKotobaServer(Scenario(handshake_status=401)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "none", "失敗。", end=True)
            await tester.wait_for_audio_end("none")
            assert _metrics(tester, "ttfb") == []

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_very_fast_response_still_reports_events_once():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=1, chunk_delay_s=0.0)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "fast", "速い。", end=True)
            end = await tester.wait_for_audio_end("fast")
            rec = tester.recording
            assert len(rec.named("tts_audio_start")) == 1
            assert len(rec.named("tts_audio_end")) == 1
            ttfb = _metrics(tester, "ttfb")
            assert len(ttfb) == 1
            assert 0 <= ttfb[0].payload["metrics"]["ttfb"] < 500
            assert end.payload["request_total_audio_duration_ms"] == (
                len(server.expected_pcm(1)) * 1000 // 32000
            )

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_connect_delay_belongs_to_the_request_that_paid_for_it():
    """First request on a new socket is flushed before any audio: its
    handshake must be reported under its own id, not the next request's."""
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, first_chunk_delay_s=1.5)
    ).start()
    try:

        async def script(tester, ten_env):
            import asyncio

            await tester.send_text(ten_env, "first", "最初。", end=True)
            await asyncio.sleep(0.3)  # connected, waiting for first chunk
            await tester.send_flush(ten_env)
            await tester.wait_for_event("tts_flush_end")
            await tester.wait_for_audio_end("first", timeout_s=1.0)
            await tester.send_text(ten_env, "second", "次。", end=True)
            await tester.wait_for_audio_end("second", timeout_s=8.0)
            delays = _metrics(tester, "connect_delay")
            assert [d.payload["metadata"]["request_id"] for d in delays] == [
                "first"
            ], [d.payload for d in delays]

        run_tester(script, make_config(server.url))
    finally:
        server.stop()
