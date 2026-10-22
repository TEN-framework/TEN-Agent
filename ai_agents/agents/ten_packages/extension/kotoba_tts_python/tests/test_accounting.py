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


def test_interval_under_controlled_clock_on_error_and_interrupt():
    """Error after partial audio and flush after audio: the interval is
    exactly the reads between audio_start and audio_end (one read)."""
    clock = FakeClock(step_s=0.1)
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=4,
            chunk_delay_s=0.05,
            fail_response_index=1,
            fail_after_chunks=2,
        )
    ).start()
    try:
        with patch.object(
            ext_mod.KotobaTTSExtension, "_clock", staticmethod(clock)
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "err", "失敗。", end=True)
                end = await tester.wait_for_audio_end("err")
                assert end.payload["reason"] == 3
                assert end.payload["request_event_interval_ms"] == 100
                await tester.send_text(ten_env, "int", "中断。", end=True)
                await tester.wait_for(
                    lambda r: len(r.audio_bytes("int")) >= 2 * 1600
                )
                await tester.send_flush(ten_env)
                await tester.wait_for_event("tts_flush_end")
                end = await tester.wait_for_audio_end("int", timeout_s=0.5)
                assert end.payload["reason"] == 2
                assert end.payload["request_event_interval_ms"] == 100

            run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_split_samples_are_aligned_and_never_cross_requests():
    """Each service chunk carries one extra byte. Only whole samples may be
    emitted and counted; the half sample held back at the end of a request
    must not leak into the next one."""
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, extra_chunk_bytes=1)
    ).start()
    try:

        async def script(tester, ten_env):
            rec = tester.recording
            await tester.send_text(ten_env, "odd1", "奇数。", end=True)
            end1 = await tester.wait_for_audio_end("odd1")
            emitted1 = rec.audio_bytes("odd1")
            # 3 chunks * (1600 + 1) bytes = 4803 -> 4802 emitted, 1 held
            assert len(emitted1) == 4802
            assert all(len(d) % 2 == 0 for _, d, _ in rec.frames)
            assert end1.payload["request_total_audio_duration_ms"] == (
                4802 * 1000 // 32000
            )
            await tester.send_text(ten_env, "odd2", "次。", end=True)
            end2 = await tester.wait_for_audio_end("odd2")
            emitted2 = rec.audio_bytes("odd2")
            assert len(emitted2) == 4802
            assert end2.payload["request_total_audio_duration_ms"] == (
                4802 * 1000 // 32000
            )
            # The first request's held byte did not prefix the second.
            assert emitted2[:2] == server.expected_pcm(1)[:2]

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_half_sample_never_crosses_response_boundary():
    """Two sentences in one request, every chunk one byte too long: the
    half sample left at the end of the first sentence's response must be
    dropped, not glued onto the second response's first byte."""
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, extra_chunk_bytes=1)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "two", "一文目。二文目。", end=True)
            end = await tester.wait_for_audio_end("two")
            audio = tester.recording.audio_bytes("two")
            # Per response: 3 * 1601 = 4803 bytes, 4802 emitted, 1 dropped.
            assert len(audio) == 2 * 4802, len(audio)
            # The second response starts with the ramp's first sample, not
            # with the first response's stray byte.
            ramp = server.expected_pcm(1)
            assert audio[4802:4804] == ramp[:2]
            assert end.payload["request_total_audio_duration_ms"] == (
                2 * 4802 * 1000 // 32000
            )

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["一文目。", "二文目。"]
    finally:
        server.stop()
