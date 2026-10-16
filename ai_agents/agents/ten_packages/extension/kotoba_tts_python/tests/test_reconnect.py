#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Connection loss before audio, after partial audio, and while idle."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import make_config, run_tester  # noqa: E402


def test_drop_before_audio_retries_once_on_a_fresh_socket():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, close_response_index=1)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "retry", "再接続。", end=True)
            end = await tester.wait_for_audio_end("retry")
            rec = tester.recording
            assert end.payload["reason"] == 1
            assert rec.audio_bytes("retry") == server.expected_pcm(1)
            assert len(rec.named("tts_audio_start")) == 1
            assert rec.named("error") == []
            statuses = [
                e.payload.get("current")
                for e in rec.named("connection_status_changed")
            ]
            assert statuses.count("connected") == 2
            assert "disconnected" in statuses

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 2
        assert server.recorded.texts == ["再接続。", "再接続。"]
    finally:
        server.stop()


def test_drop_after_partial_audio_ends_with_error_and_recovers():
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=5,
            close_response_index=1,
            close_after_chunks=2,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(
                ten_env, "partial", "途中で切れる。", end=True
            )
            end = await tester.wait_for_audio_end("partial")
            rec = tester.recording
            assert end.payload["reason"] == 3
            emitted = len(rec.audio_bytes("partial"))
            assert emitted == 2 * 800 * 2
            assert end.payload["request_total_audio_duration_ms"] == (
                emitted * 1000 // (16000 * 2)
            )
            errors = rec.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == 1000
            assert errors[0].payload["vendor_info"]["vendor"] == "kotoba"
            assert "途中で切れる" not in errors[0].payload["message"]
            await tester.send_text(ten_env, "again", "回復。", end=True)
            end2 = await tester.wait_for_audio_end("again")
            assert end2.payload["reason"] == 1
            assert rec.audio_bytes("again") == server.expected_pcm(1)

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 2
        assert server.recorded.texts == ["途中で切れる。", "回復。"]
    finally:
        server.stop()


def test_idle_close_between_requests_reconnects_transparently():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=2, idle_close_s=0.3)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "one", "一。", end=True)
            await tester.wait_for_audio_end("one")
            await asyncio.sleep(0.9)
            await tester.send_text(ten_env, "two", "二。", end=True)
            end = await tester.wait_for_audio_end("two")
            rec = tester.recording
            assert end.payload["reason"] == 1
            assert rec.audio_bytes("two") == server.expected_pcm(1)
            assert rec.named("error") == []

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 2
        assert server.recorded.texts == ["一。", "二。"]
    finally:
        server.stop()


def test_response_stall_times_out_without_hanging():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, first_chunk_delay_s=3.0)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "stall", "止まる。", end=True)
            end = await tester.wait_for_audio_end("stall", timeout_s=4.0)
            rec = tester.recording
            assert end.payload["reason"] == 3
            assert end.payload["request_total_audio_duration_ms"] == 0
            errors = rec.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == 1000
            assert (
                errors[0].payload["vendor_info"]["code"] == "response_timeout"
            )

        run_tester(
            script,
            make_config(server.url, params={"request_timeout_seconds": 0.5}),
        )
    finally:
        server.stop()


def test_idle_close_is_reported_before_the_next_text():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=2, idle_close_s=0.3)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "one", "一。", end=True)
            await tester.wait_for_audio_end("one")
            # The service closes the idle socket; the status must flip
            # without any further request from us.
            await tester.wait_for(
                lambda r: any(
                    e.payload.get("current") == "disconnected"
                    and e.payload.get("last") == "connected"
                    for e in r.named("connection_status_changed")
                ),
                timeout_s=2.0,
            )
            await tester.send_text(ten_env, "two", "二。", end=True)
            end = await tester.wait_for_audio_end("two")
            assert end.payload["reason"] == 1
            assert tester.recording.named("error") == []

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 2
    finally:
        server.stop()
