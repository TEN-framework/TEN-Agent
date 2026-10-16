#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Exact audio-end accounting and metric origins under a controlled clock."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kotoba_tts_python.extension as ext_mod  # noqa: E402
from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import make_config, metrics_with, run_tester  # noqa: E402


class FakeClock:
    """Monotonic clock that advances a fixed step on every read."""

    def __init__(self, step_s: float) -> None:
        self.t = 1000.0
        self.step = step_s
        self.reads = 0

    def __call__(self) -> float:
        self.reads += 1
        self.t += self.step
        return self.t


def test_interval_is_measured_from_audio_start_emission():
    """With a clock that jumps 100 ms per read, the interval equals the
    number of reads between the audio_start read and the audio_end read,
    independent of anything that happened before audio_start."""
    clock = FakeClock(step_s=0.1)
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, handshake_delay_s=0.3)
    ).start()
    try:
        with patch.object(
            ext_mod.KotobaTTSExtension, "_clock", staticmethod(clock)
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "clk", "時計。", end=True)
                end = await tester.wait_for_audio_end("clk")
                interval = end.payload["request_event_interval_ms"]
                # Reads between audio_start and audio_end in _emit_audio /
                # _send_audio_end: exactly one (the end read), so 100 ms.
                assert interval == 100, interval
                ttfb = metrics_with(tester, "ttfb")[0].payload["metrics"][
                    "ttfb"
                ]
                # TTFB: one read at send, one read at first chunk.
                assert ttfb == 100, ttfb
                connect = metrics_with(tester, "connect_delay")
                assert len(connect) == 1
                # Connect delay: one read before start(), one after.
                assert connect[0].payload["metrics"]["connect_delay"] == 100

            run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_duration_counts_only_emitted_bytes_on_every_terminal_path():
    """Success, partial error, and interrupted paths report exactly the
    bytes the tester received."""
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=6,
            chunk_delay_s=0.05,
            fail_response_index=2,
            fail_after_chunks=2,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            rec = tester.recording
            # success
            await tester.send_text(ten_env, "ok", "成功。", end=True)
            end = await tester.wait_for_audio_end("ok")
            assert end.payload["request_total_audio_duration_ms"] == (
                len(rec.audio_bytes("ok")) * 1000 // 32000
            )
            # partial error (response 2 fails after 2 chunks)
            await tester.send_text(ten_env, "err", "失敗。", end=True)
            end = await tester.wait_for_audio_end("err")
            assert end.payload["reason"] == 3
            assert len(rec.audio_bytes("err")) == 2 * 800 * 2
            assert end.payload["request_total_audio_duration_ms"] == (
                len(rec.audio_bytes("err")) * 1000 // 32000
            )
            # interrupted
            await tester.send_text(ten_env, "int", "中断。", end=True)
            await tester.wait_for(
                lambda r: len(r.audio_bytes("int")) >= 2 * 800 * 2
            )
            await tester.send_flush(ten_env)
            await tester.wait_for_event("tts_flush_end")
            end = await tester.wait_for_audio_end("int", timeout_s=0.5)
            assert end.payload["reason"] == 2
            assert end.payload["request_total_audio_duration_ms"] == (
                len(rec.audio_bytes("int")) * 1000 // 32000
            )
            await asyncio.sleep(0.3)
            # no-audio termination
            await tester.send_text(ten_env, "none", "", end=True)
            end = await tester.wait_for_audio_end("none", timeout_s=0.5)
            assert end.payload["request_total_audio_duration_ms"] == 0
            assert end.payload["request_event_interval_ms"] == 0

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_ttfb_excludes_handshake_time():
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=2,
            handshake_delay_s=0.6,
            first_chunk_delay_s=0.2,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "t", "計測。", end=True)
            await tester.wait_for_audio_end("t")
            ttfb = metrics_with(tester, "ttfb")[0].payload["metrics"]["ttfb"]
            assert 150 <= ttfb < 500, ttfb
            connect = metrics_with(tester, "connect_delay")[0]
            assert connect.payload["metrics"]["connect_delay"] >= 550

        run_tester(script, make_config(server.url))
    finally:
        server.stop()
