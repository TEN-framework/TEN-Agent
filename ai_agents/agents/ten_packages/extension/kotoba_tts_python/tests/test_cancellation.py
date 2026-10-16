#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Cancellation under blocked transport, terminal races, double flush,
late events from an old session, and shutdown while blocked.

Every test asserts the same invariants: nothing for the old request after
``tts_flush_end``, exactly one ``tts_audio_end`` per request, flush
completes quickly, and the next request works.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import (  # noqa: E402
    events_after,
    make_config,
    metrics_with,
    run_tester,
)

FLUSH_BUDGET_S = 1.0


async def _wait_until(predicate, timeout_s: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.02)


def _assert_clean_after_flush(tester, request_id: str) -> None:
    rec = tester.recording
    flush_end = rec.named("tts_flush_end")[-1]
    ends = [
        e
        for e in rec.named("tts_audio_end")
        if e.payload["request_id"] == request_id
    ]
    assert len(ends) == 1, f"expected one audio_end, got {len(ends)}"
    assert ends[0].at <= flush_end.at, "audio_end landed after flush_end"
    late_frames = [
        f
        for f in events_after(tester, "pcm_frame", flush_end)
        if f.payload.get("request_id") == request_id
    ]
    assert late_frames == [], "frames for the old request after flush_end"
    assert rec.named("error") == []


def test_flush_while_send_is_blocked_discards_the_socket():
    """The service never answers response.create (held send/response).
    Flush must not leave that response on a socket the next request reuses.
    """
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, hold_response_index=1)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "held", "止まった応答。", end=True)
            await _wait_until(
                lambda: server.recorded.texts == ["止まった応答。"]
            )
            t0 = time.monotonic()
            await tester.send_flush(ten_env, "flush-held")
            await tester.wait_for_event("tts_flush_end")
            assert time.monotonic() - t0 < FLUSH_BUDGET_S
            end = await tester.wait_for_audio_end("held", timeout_s=0.5)
            assert end.payload["reason"] == 2
            assert end.payload["request_total_audio_duration_ms"] == 0
            _assert_clean_after_flush(tester, "held")
            # Next request gets clean audio, never the held response's.
            await tester.send_text(ten_env, "next", "次。", end=True)
            end2 = await tester.wait_for_audio_end("next")
            assert end2.payload["reason"] == 1
            assert tester.recording.audio_bytes("next") == server.expected_pcm(
                1
            )

        run_tester(script, make_config(server.url))
        assert server.recorded.cancels == 1
    finally:
        server.stop()


def test_flush_during_slow_handshake_is_bounded():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=2, handshake_delay_s=1.5)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "hs", "握手中。", end=True)
            await _wait_until(lambda: server.recorded.connections >= 1)
            t0 = time.monotonic()
            await tester.send_flush(ten_env, "flush-hs")
            await tester.wait_for_event("tts_flush_end")
            assert time.monotonic() - t0 < FLUSH_BUDGET_S
            end = await tester.wait_for_audio_end("hs", timeout_s=0.5)
            assert end.payload["reason"] == 2
            assert tester.recording.named("tts_audio_start") == []
            _assert_clean_after_flush(tester, "hs")
            await tester.send_text(ten_env, "after", "次。", end=True)
            end2 = await tester.wait_for_audio_end("after", timeout_s=5.0)
            assert tester.recording.audio_bytes("after") == server.expected_pcm(
                1
            )

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_double_flush_with_pending_drain_stays_bounded():
    """Flush A, start B while A's cancel drain is pending, flush B."""
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=40,
            chunk_delay_s=0.05,
            cancel_done_delay_s=1.0,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "A", "最初の長い文。", end=True)
            await tester.wait_for_event("pcm_frame", count=2)
            await tester.send_flush(ten_env, "flush-A")
            await tester.wait_for_event("tts_flush_end")
            await tester.send_text(ten_env, "B", "二番目。", end=True)
            await asyncio.sleep(0.1)  # B is waiting on A's drain
            t0 = time.monotonic()
            await tester.send_flush(ten_env, "flush-B")
            await tester.wait_for_event("tts_flush_end", count=2)
            assert time.monotonic() - t0 < FLUSH_BUDGET_S
            await tester.wait_for_audio_end("B", timeout_s=0.5)
            _assert_clean_after_flush(tester, "A")
            _assert_clean_after_flush(tester, "B")
            await tester.send_text(ten_env, "C", "三番目。", end=True)
            end_c = await tester.wait_for_audio_end("C", timeout_s=8.0)
            assert end_c.payload["reason"] == 1
            assert len(tester.recording.audio_bytes("C")) == len(
                server.expected_pcm(1)
            )

        run_tester(script, make_config(server.url))
        assert server.recorded.texts[:1] == ["最初の長い文。"]
        assert "二番目。" not in server.recorded.texts
    finally:
        server.stop()


def test_stray_audio_after_cancel_never_reaches_the_next_request():
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=40,
            chunk_delay_s=0.05,
            stray_chunks_after_cancel=3,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "old", "古い要求。", end=True)
            await tester.wait_for_event("pcm_frame", count=2)
            await tester.send_flush(ten_env, "flush-old")
            await tester.wait_for_event("tts_flush_end")
            await tester.wait_for_audio_end("old", timeout_s=0.5)
            await tester.send_text(ten_env, "new", "新しい要求。", end=True)
            end = await tester.wait_for_audio_end("new", timeout_s=8.0)
            assert end.payload["reason"] == 1
            # The stray chunks carry a distinct ramp; none may appear.
            assert tester.recording.audio_bytes("new") == server.expected_pcm(1)
            _assert_clean_after_flush(tester, "old")

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_flush_during_terminal_path_keeps_audio_end_before_flush_end():
    """Block the dump flush that _end_request performs after audio_end and
    flush during it: the old request's events must all precede flush_end
    and there must be exactly one audio_end."""
    import tempfile
    import shutil
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_cancel_")
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    gate = {"event": None}

    original_flush = ext_mod.PCMWriter.flush

    async def slow_flush(self):
        if gate["event"] is not None:
            await gate["event"].wait()
        await original_flush(self)

    try:
        with patch.object(ext_mod.PCMWriter, "flush", slow_flush):

            async def script(tester, ten_env):
                gate["event"] = asyncio.Event()
                await tester.send_text(ten_env, "term", "終了中。", end=True)
                end = await tester.wait_for_audio_end("term")
                # Worker is now inside _end_request, blocked on the dump.
                await tester.send_flush(ten_env, "flush-term")
                flush_end = (await tester.wait_for_event("tts_flush_end"))[0]
                assert end.at <= flush_end.at
                gate["event"].set()
                await asyncio.sleep(0.3)
                ends = [
                    e
                    for e in tester.recording.named("tts_audio_end")
                    if e.payload["request_id"] == "term"
                ]
                assert len(ends) == 1
                assert ends[0].payload["reason"] == 1
                await tester.send_text(ten_env, "after", "次。", end=True)
                await tester.wait_for_audio_end("after")

            run_tester(
                script, make_config(server.url, dump=True, dump_path=dump_dir)
            )
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_flush_takes_over_when_terminal_worker_hangs():
    """If the worker's terminal event never goes out, flush waits its bound
    and then emits exactly one INTERRUPTED end itself."""
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    state = {"hang": True, "calls": 0}
    original = ext_mod.KotobaTTSExtension.send_tts_audio_end

    async def hanging_first_audio_end(self, *args, **kwargs):
        state["calls"] += 1
        if state["hang"] and state["calls"] == 1:
            await asyncio.sleep(60)  # never returns before cancellation
        return await original(self, *args, **kwargs)

    try:
        with patch.object(ext_mod, "_TERMINAL_JOIN_SECONDS", 0.5), patch.object(
            ext_mod.KotobaTTSExtension,
            "send_tts_audio_end",
            hanging_first_audio_end,
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "hang", "固まる。", end=True)
                await tester.wait_for(
                    lambda r: len(r.frames) >= 2 and state["calls"] >= 1,
                    timeout_s=5.0,
                )
                t0 = time.monotonic()
                await tester.send_flush(ten_env, "flush-hang")
                await tester.wait_for_event("tts_flush_end")
                elapsed = time.monotonic() - t0
                assert 0.4 < elapsed < 2.0, elapsed
                end = await tester.wait_for_audio_end("hang", timeout_s=0.5)
                assert end.payload["reason"] == 2
                await asyncio.sleep(0.3)
                assert len(tester.recording.named("tts_audio_end")) == 1

            run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_usage_after_flush_belongs_to_the_next_request_only():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=40, chunk_delay_s=0.05)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(
                ten_env, "A", "あいうえお、かきくけこ。", end=True
            )
            await tester.wait_for_event("pcm_frame", count=2)
            await tester.send_flush(ten_env, "flush-A")
            await tester.wait_for_event("tts_flush_end")
            await tester.wait_for_audio_end("A", timeout_s=0.5)
            await tester.send_text(ten_env, "B", "さしすせそ。", end=True)
            await tester.wait_for_audio_end("B", timeout_s=8.0)
            # Usage is emitted right after audio_end; wait for B's.
            await tester.wait_for(
                lambda r: any(
                    e.payload["metadata"].get("request_id") == "B"
                    for e in r.named("metrics")
                    if "recv_audio_duration" in e.payload.get("metrics", {})
                ),
                timeout_s=2.0,
            )
            usage = [
                e
                for e in metrics_with(tester, "recv_audio_duration")
                if e.payload["metadata"].get("request_id")
            ]
            by_id = {e.payload["metadata"]["request_id"]: e for e in usage}
            assert set(by_id) == {"A", "B"}
            assert by_id["A"].payload["metrics"]["input_characters"] == len(
                "あいうえお、かきくけこ。"
            )
            assert by_id["B"].payload["metrics"]["input_characters"] == len(
                "さしすせそ。"
            )
            b_bytes = len(tester.recording.audio_bytes("B"))
            assert by_id["B"].payload["metrics"]["recv_audio_duration"] == (
                b_bytes * 1000 / (16000 * 2)
            )

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_stop_during_blocked_handshake_is_bounded():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=2, handshake_delay_s=5.0)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "stop", "停止。", end=True)
            await _wait_until(lambda: server.recorded.connections >= 1)
            # Returning ends the test: the runtime calls on_stop while the
            # handshake is still pending. run_tester enforces the bound.

        t0 = time.monotonic()
        run_tester(script, make_config(server.url), timeout_s=10.0)
        assert time.monotonic() - t0 < 4.0
    finally:
        server.stop()


def test_disconnect_callback_failure_does_not_break_the_client():
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    server = FakeKotobaServer(
        Scenario(chunks_per_response=2, idle_close_s=0.3)
    ).start()

    original = ext_mod.KotobaTTSExtension.on_disconnected

    async def failing_on_disconnected(self, **kwargs):
        # The base class itself reports "stopped" at shutdown; only the
        # client's own disconnect reports are made to fail here.
        if kwargs.get("message") == "stopped":
            return await original(self, **kwargs)
        raise RuntimeError("status sink down")

    try:
        with patch.object(
            ext_mod.KotobaTTSExtension,
            "on_disconnected",
            failing_on_disconnected,
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "one", "一。", end=True)
                await tester.wait_for_audio_end("one")
                await asyncio.sleep(0.9)  # idle close -> drop -> callback
                await tester.send_text(ten_env, "two", "二。", end=True)
                end = await tester.wait_for_audio_end("two")
                assert end.payload["reason"] == 1
                assert tester.recording.audio_bytes(
                    "two"
                ) == server.expected_pcm(1)
                assert tester.recording.named("error") == []

            run_tester(script, make_config(server.url))
        assert server.recorded.connections == 2
    finally:
        server.stop()


def test_flush_while_the_write_itself_is_suspended():
    """Gate AsyncTTSSession.synthesize (the actual write) and flush while it
    is suspended: the send-cleanup branch must drop the socket, report
    INTERRUPTED once, and the next request must get clean audio."""
    from unittest.mock import patch
    import kotoba._ws_tts as sdk_tts

    server = FakeKotobaServer(Scenario(chunks_per_response=3)).start()
    gate = {"event": None, "entered": None}
    original = sdk_tts.AsyncTTSSession.synthesize

    async def gated_synthesize(self, text, **kwargs):
        event, gate["event"] = gate["event"], None  # gate the first send only
        if event is not None:
            gate["entered"].set()
            await event.wait()
        return await original(self, text, **kwargs)

    try:
        with patch.object(
            sdk_tts.AsyncTTSSession, "synthesize", gated_synthesize
        ):

            async def script(tester, ten_env):
                gate["event"] = asyncio.Event()
                gate["entered"] = asyncio.Event()
                await tester.send_text(ten_env, "w", "書き込み中。", end=True)
                await asyncio.wait_for(gate["entered"].wait(), 5.0)
                t0 = time.monotonic()
                await tester.send_flush(ten_env, "flush-write")
                await tester.wait_for_event("tts_flush_end")
                assert time.monotonic() - t0 < FLUSH_BUDGET_S
                end = await tester.wait_for_audio_end("w", timeout_s=0.5)
                assert end.payload["reason"] == 2
                _assert_clean_after_flush(tester, "w")
                await tester.send_text(ten_env, "n", "次。", end=True)
                end2 = await tester.wait_for_audio_end("n")
                assert end2.payload["reason"] == 1
                assert tester.recording.audio_bytes("n") == server.expected_pcm(
                    1
                )

            run_tester(script, make_config(server.url))
        # The interrupted write dropped its socket; the next request opened a new one.
        assert server.recorded.connections == 2
        assert server.recorded.texts == ["次。"]
    finally:
        server.stop()


def test_stop_while_the_write_is_suspended_is_bounded():
    from unittest.mock import patch
    import kotoba._ws_tts as sdk_tts

    server = FakeKotobaServer(Scenario(chunks_per_response=3)).start()
    gate = {"event": None, "entered": None}
    original = sdk_tts.AsyncTTSSession.synthesize

    async def gated_synthesize(self, text, **kwargs):
        if gate["event"] is not None:
            gate["entered"].set()
            await gate["event"].wait()
        return await original(self, text, **kwargs)

    try:
        with patch.object(
            sdk_tts.AsyncTTSSession, "synthesize", gated_synthesize
        ):

            async def script(tester, ten_env):
                gate["event"] = asyncio.Event()
                gate["entered"] = asyncio.Event()
                await tester.send_text(ten_env, "s", "停止。", end=True)
                await asyncio.wait_for(gate["entered"].wait(), 5.0)
                # Return: the runtime stops the extension mid-write.

            t0 = time.monotonic()
            run_tester(script, make_config(server.url), timeout_s=10.0)
            assert time.monotonic() - t0 < 4.0
    finally:
        server.stop()


def test_late_old_session_cleanup_preserves_the_replacement():
    """A's cancel drain outlives the grace period (server answers late). B
    must get its own connection, and the old session's late cleanup must
    not drop B's socket or leak A's audio."""
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=40,
            chunk_delay_s=0.05,
            cancel_done_delay_s=3.0,
            stray_chunks_after_cancel=2,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "A", "古い。", end=True)
            await tester.wait_for_event("pcm_frame", count=2)
            await tester.send_flush(ten_env, "flush-A")
            await tester.wait_for_event("tts_flush_end")
            await tester.wait_for_audio_end("A", timeout_s=0.5)
            await tester.send_text(ten_env, "B", "新しい。", end=True)
            end_b = await tester.wait_for_audio_end("B", timeout_s=12.0)
            assert end_b.payload["reason"] == 1
            assert tester.recording.audio_bytes("B") == server.expected_pcm(1)
            await asyncio.sleep(1.5)  # old session's late done(cancelled) lands
            await tester.send_text(ten_env, "C", "三。", end=True)
            end_c = await tester.wait_for_audio_end("C", timeout_s=8.0)
            assert end_c.payload["reason"] == 1
            assert tester.recording.audio_bytes("C") == server.expected_pcm(1)
            statuses = [
                e.payload.get("current")
                for e in tester.recording.named("connection_status_changed")
            ]
            assert statuses.count("connected") == 2, statuses

        run_tester(script, make_config(server.url))
        # A's connection was dropped after the grace period; B and C share the replacement.
        assert server.recorded.connections == 2
    finally:
        server.stop()
