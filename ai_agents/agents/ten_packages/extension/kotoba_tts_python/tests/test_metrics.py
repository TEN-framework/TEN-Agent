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
