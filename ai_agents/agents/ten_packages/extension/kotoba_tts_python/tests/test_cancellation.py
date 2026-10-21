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
    ThreadGate,
    dump_path,
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
                gate["event"] = ThreadGate()
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
                gate["event"] = ThreadGate()
                gate["entered"] = ThreadGate()
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
                gate["event"] = ThreadGate()
                gate["entered"] = ThreadGate()
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
    not drop B's socket or leak A's audio.

    By construction the replacement cannot exist while the old session is
    still being drained: ``connect()`` awaits the drain (or its timeout and
    drop) before opening a new socket, and ``_drain`` / the watcher only
    act on a session that is still ``self._session``. The server-side
    open/close order asserted below is the proof of that ordering."""
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
        kinds = [(k, i) for k, i, _ in server.recorded.events]
        opens = [i for k, i in kinds if k == "open"]
        assert len(opens) == 2, kinds
        first, second = opens
        assert kinds.index(("close", first)) < kinds.index(
            ("open", second)
        ), kinds
    finally:
        server.stop()


def test_flush_takeover_finalizes_the_dump():
    """Same as the hung-terminal test, with dumping enabled: when flush
    takes over, the dump must still hold every emitted frame."""
    import os
    import shutil
    import tempfile
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_takeover_")
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    state = {"calls": 0}
    original = ext_mod.KotobaTTSExtension.send_tts_audio_end

    async def hanging_first_audio_end(self, *args, **kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            await asyncio.sleep(60)
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
                await tester.send_flush(ten_env, "flush-hang")
                await tester.wait_for_event("tts_flush_end")
                await tester.wait_for_audio_end("hang", timeout_s=0.5)

            tester = run_tester(
                script, make_config(server.url, dump=True, dump_path=dump_dir)
            )
        with open(dump_path(dump_dir, "hang"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("hang")
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_stop_during_recorder_finalization_still_finalizes_the_dump():
    """The app stops while the terminal path is inside the (slow) dump
    flush: on_stop must join the finishing worker instead of cancelling
    it, and the file must be complete."""
    import os
    import shutil
    import tempfile
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_stopflush_")
    server = FakeKotobaServer(Scenario(chunks_per_response=3)).start()
    original_flush = ext_mod.PCMWriter.flush

    async def slow_flush(self):
        await asyncio.sleep(0.5)
        await original_flush(self)

    try:
        with patch.object(ext_mod.PCMWriter, "flush", slow_flush):

            async def script(tester, ten_env):
                await tester.send_text(
                    ten_env, "stopdump", "停止中。", end=True
                )
                await tester.wait_for_audio_end("stopdump")
                # Return now: the worker is inside the 0.5 s flush and the
                # runtime stops the extension while it is pending.

            tester = run_tester(
                script,
                make_config(server.url, dump=True, dump_path=dump_dir),
                timeout_s=10.0,
            )
        with open(dump_path(dump_dir, "stopdump"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("stopdump")
        assert len(tester.recording.audio_bytes("stopdump")) == len(
            server.expected_pcm(1)
        )
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def _usage_for(tester, request_id: str) -> list:
    return [
        e
        for e in metrics_with(tester, "recv_audio_duration")
        if e.payload["metadata"].get("request_id") == request_id
    ]


def test_flush_takeover_after_audio_end_still_reports_usage():
    """The worker hangs after audio_end went out, inside the usage send.
    Flush takes over after the bound: no second audio_end, but usage for
    the old request is emitted, and the next request's usage holds only
    its own counters."""
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    state = {"calls": 0}
    original = ext_mod.KotobaTTSExtension.send_usage_metrics

    async def hanging_first_usage(self, *args, **kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            await asyncio.sleep(60)
        return await original(self, *args, **kwargs)

    try:
        with patch.object(ext_mod, "_TERMINAL_JOIN_SECONDS", 0.5), patch.object(
            ext_mod.KotobaTTSExtension,
            "send_usage_metrics",
            hanging_first_usage,
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "U1", "使用量。", end=True)
                await tester.wait_for_audio_end("U1")
                await _wait_until(lambda: state["calls"] >= 1)
                t0 = time.monotonic()
                await tester.send_flush(ten_env, "flush-usage")
                await tester.wait_for_event("tts_flush_end")
                assert 0.4 < time.monotonic() - t0 < 2.0
                await tester.send_text(ten_env, "U2", "次。", end=True)
                await tester.wait_for_audio_end("U2")
                await tester.wait_for(
                    lambda r: len(_usage_for(tester, "U2")) >= 1,
                    timeout_s=2.0,
                )
                ends = [
                    e.payload["request_id"]
                    for e in tester.recording.named("tts_audio_end")
                ]
                assert ends == ["U1", "U2"], ends
                u1 = _usage_for(tester, "U1")
                u2 = _usage_for(tester, "U2")
                assert len(u1) == 1 and len(u2) == 1
                assert u1[0].payload["metrics"]["input_characters"] == len(
                    "使用量。"
                )
                assert u2[0].payload["metrics"]["input_characters"] == len(
                    "次。"
                )
                assert u2[0].payload["metrics"]["recv_audio_duration"] == (
                    len(tester.recording.audio_bytes("U2")) * 1000 / (16000 * 2)
                )

            run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_stop_during_gated_dump_flush_completes_the_file():
    """Shutdown arrives while the dump flush is suspended for longer than
    the join bound: on_stop cancels the worker and finishes the flush
    itself; the file holds every emitted frame."""
    import os
    import shutil
    import tempfile
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_stopgate_")
    server = FakeKotobaServer(Scenario(chunks_per_response=3)).start()
    original_flush = ext_mod.PCMWriter.flush
    state = {"calls": 0}

    async def gated_flush(self):
        state["calls"] += 1
        if state["calls"] == 1:
            # Longer than the (patched) join bound, shorter than the test.
            await asyncio.sleep(1.0)
        await original_flush(self)

    try:
        with patch.object(ext_mod, "_TERMINAL_JOIN_SECONDS", 0.3), patch.object(
            ext_mod.PCMWriter, "flush", gated_flush
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "gate", "停止。", end=True)
                await tester.wait_for_audio_end("gate")
                await _wait_until(lambda: state["calls"] >= 1)
                # Return: the runtime stops the extension inside the flush.

            t0 = time.monotonic()
            tester = run_tester(
                script,
                make_config(server.url, dump=True, dump_path=dump_dir),
                timeout_s=10.0,
            )
            assert time.monotonic() - t0 < 6.0
        with open(dump_path(dump_dir, "gate"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("gate")
        assert len(tester.recording.audio_bytes("gate")) == len(
            server.expected_pcm(1)
        )
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_next_request_during_previous_dump_flush_then_stop():
    """The previous request's dump is still being written when the next
    request starts and the app stops: on_stop must finish the previous
    request's flush (it is no longer the current request) and close the
    current request's dump. Events emitted during on_stop are not
    observable here, so the second file is checked against the frames
    recorded before the stop."""
    import os
    import shutil
    import tempfile
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_overlap_")
    server = FakeKotobaServer(
        Scenario(chunks_per_response=3, chunk_delay_s=0.1)
    ).start()
    original_flush = ext_mod.PCMWriter.flush
    gate = {"event": None, "entered": None}

    async def gated_flush(self):
        event, gate["event"] = gate["event"], None  # gate the first flush
        if event is not None:
            gate["entered"].set()
            await event.wait()
        await original_flush(self)

    try:
        with patch.object(ext_mod.PCMWriter, "flush", gated_flush):

            async def script(tester, ten_env):
                release = ThreadGate()
                gate["event"] = release
                gate["entered"] = ThreadGate()
                await tester.send_text(ten_env, "P", "前。", end=True)
                await tester.wait_for_audio_end("P")
                await asyncio.wait_for(gate["entered"].wait(), 5.0)
                # P is now stuck in its dump flush; start the next request.
                await tester.send_text(ten_env, "Q", "後ろ。", end=True)
                await tester.wait_for(lambda r: len(r.audio_bytes("Q")) > 0)
                release.set()
                # Return: the runtime stops the extension while Q streams
                # and P's flush has just been released.

            tester = run_tester(
                script,
                make_config(server.url, dump=True, dump_path=dump_dir),
                timeout_s=10.0,
            )
        rec = tester.recording
        ends = {e.payload["request_id"]: e for e in rec.named("tts_audio_end")}
        assert ends["P"].payload["reason"] == 1
        with open(dump_path(dump_dir, "P"), "rb") as f:
            assert f.read() == rec.audio_bytes("P")
        assert len(rec.audio_bytes("P")) == len(server.expected_pcm(1))
        with open(dump_path(dump_dir, "Q"), "rb") as f:
            dump_q = f.read()
        recorded_q = rec.audio_bytes("Q")
        assert recorded_q and dump_q.startswith(recorded_q)
        # Frames emitted between the script's return and on_stop are in
        # the file but not in the recording; the file ends on a frame.
        assert len(dump_q) % 1600 == 0, len(dump_q)
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_flush_waits_for_terminal_events_that_land_in_time():
    """Flush arrives while the worker is between its terminal events and
    finish_request (gated here). The events land within the bound, so
    flush waits for them instead of taking over: audio_end keeps its
    REQUEST_END reason, there is exactly one of it, it precedes
    flush_end, and the next request works."""
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    gate = {"release": None, "entered": None}
    original = ext_mod.KotobaTTSExtension.finish_request

    async def gated_finish(self, *args, **kwargs):
        release, gate["release"] = gate["release"], None  # first call only
        if release is not None:
            gate["entered"].set()
            await release.wait()
        return await original(self, *args, **kwargs)

    try:
        with patch.object(
            ext_mod.KotobaTTSExtension, "finish_request", gated_finish
        ):

            async def script(tester, ten_env):
                release = ThreadGate()
                gate["release"] = release
                gate["entered"] = ThreadGate()
                await tester.send_text(ten_env, "wait", "待つ。", end=True)
                end = await tester.wait_for_audio_end("wait")
                await asyncio.wait_for(gate["entered"].wait(), 5.0)
                flush_task = asyncio.ensure_future(
                    tester.send_flush(ten_env, "flush-wait")
                )
                await asyncio.sleep(0.3)
                assert tester.recording.named("tts_flush_end") == []
                t_release = time.monotonic()
                release.set()
                await flush_task
                flush_end = (await tester.wait_for_event("tts_flush_end"))[0]
                assert flush_end.at >= t_release
                assert end.at <= flush_end.at
                ends = [
                    e
                    for e in tester.recording.named("tts_audio_end")
                    if e.payload["request_id"] == "wait"
                ]
                assert len(ends) == 1 and ends[0].payload["reason"] == 1
                assert len(_usage_for(tester, "wait")) == 1
                await tester.send_text(ten_env, "after", "次。", end=True)
                end2 = await tester.wait_for_audio_end("after")
                assert end2.payload["reason"] == 1
                assert tester.recording.audio_bytes(
                    "after"
                ) == server.expected_pcm(1)

            run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_request_released_during_shutdown_never_starts():
    """A's dump flush is gated, B is streaming, C is queued behind B. The
    app stops. While on_stop waits for A, B completes and the base class
    releases C: C must not start (no worker, no dump, no text sent)."""
    import os
    import shutil
    import tempfile
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_stopq_")
    server = FakeKotobaServer(
        Scenario(chunks_per_response=4, chunk_delay_s=0.1)
    ).start()
    original_flush = ext_mod.PCMWriter.flush
    gate = {"entered": None}

    async def gated_flush(self):
        entered, gate["entered"] = gate["entered"], None  # first flush only
        if entered is not None:
            entered.set()
            await asyncio.sleep(1.0)  # longer than B needs to finish
        await original_flush(self)

    try:
        with patch.object(ext_mod.PCMWriter, "flush", gated_flush):

            async def script(tester, ten_env):
                entered = ThreadGate()
                gate["entered"] = entered
                await tester.send_text(ten_env, "A", "前。", end=True)
                await tester.wait_for_audio_end("A")
                await asyncio.wait_for(entered.wait(), 5.0)
                # A is stuck in its dump flush. B streams, C waits behind B.
                await tester.send_text(ten_env, "B", "中。", end=True)
                await tester.send_text(ten_env, "C", "後。", end=True)
                await tester.wait_for(lambda r: len(r.audio_bytes("B")) > 0)
                # Return: the runtime stops the extension while A flushes
                # and B still has chunks to go.

            t0 = time.monotonic()
            tester = run_tester(
                script,
                make_config(server.url, dump=True, dump_path=dump_dir),
                timeout_s=10.0,
            )
            assert time.monotonic() - t0 < 8.0
        files = sorted(os.listdir(dump_dir))
        assert os.path.basename(dump_path(dump_dir, "C")) not in files, files
        assert "後。" not in server.recorded.texts, server.recorded.texts
        with open(dump_path(dump_dir, "A"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("A")
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_flush_during_streaming_does_not_wait_for_dump_io():
    """Dump enabled, the dump write is held: flush during streaming must
    still produce tts_flush_end and accept the next request while the
    write is pending. Shutdown then finishes the file exactly."""
    import os
    import shutil
    import tempfile
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_flushio_")
    server = FakeKotobaServer(
        Scenario(chunks_per_response=40, chunk_delay_s=0.05)
    ).start()
    original_flush = ext_mod.PCMWriter.flush
    gate = {"release": None, "entered": None}

    async def gated_flush(self):
        release, gate["release"] = gate["release"], None  # first flush only
        if release is not None:
            gate["entered"].set()
            await release.wait()
        await original_flush(self)

    try:
        with patch.object(ext_mod.PCMWriter, "flush", gated_flush):

            async def script(tester, ten_env):
                release = ThreadGate()
                gate["release"] = release
                gate["entered"] = ThreadGate()
                await tester.send_text(
                    ten_env, "io", "書き込み待ち。", end=True
                )
                await tester.wait_for_event("pcm_frame", count=2)
                t0 = time.monotonic()
                await tester.send_flush(ten_env, "flush-io")
                await tester.wait_for_event("tts_flush_end", timeout_s=2.0)
                assert time.monotonic() - t0 < FLUSH_BUDGET_S
                end = await tester.wait_for_audio_end("io", timeout_s=0.5)
                assert end.payload["reason"] == 2
                _assert_clean_after_flush(tester, "io")
                # The dump close is parked on the gate, not yet released.
                await asyncio.wait_for(gate["entered"].wait(), 2.0)
                assert not release.is_set()
                # The input gate is open: the next request runs meanwhile.
                await tester.send_text(ten_env, "next", "次。", end=True)
                end2 = await tester.wait_for_audio_end("next", timeout_s=5.0)
                assert end2.payload["reason"] == 1
                release.set()

            tester = run_tester(
                script, make_config(server.url, dump=True, dump_path=dump_dir)
            )
        with open(dump_path(dump_dir, "io"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("io")
        with open(dump_path(dump_dir, "next"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("next")
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_flush_takeover_during_shutdown_does_not_abort_stop():
    """A terminal event hangs. Flush starts waiting for it, then the app
    stops while that wait is still running. Flush times out first and
    cancels the worker that on_stop is joining. on_stop must treat that as
    a completed join, finish its cleanup (dump file exact, socket closed)
    and return normally instead of letting the CancelledError escape."""
    import os
    import shutil
    import tempfile
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_stopjoin_")
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    state = {"calls": 0}
    original = ext_mod.KotobaTTSExtension.send_tts_audio_end

    async def hanging_first_audio_end(self, *args, **kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            await asyncio.sleep(60)  # the worker's own terminal event
        return await original(self, *args, **kwargs)

    try:
        with patch.object(ext_mod, "_TERMINAL_JOIN_SECONDS", 0.6), patch.object(
            ext_mod.KotobaTTSExtension,
            "send_tts_audio_end",
            hanging_first_audio_end,
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "sj", "停止と接続。", end=True)
                await tester.wait_for(
                    lambda r: len(r.frames) >= 2 and state["calls"] >= 1,
                    timeout_s=5.0,
                )
                await tester.send_flush(ten_env, "flush-sj")
                # Return while flush is inside its 0.6 s wait: on_stop
                # starts its own 0.6 s join on the same worker, and flush's
                # timeout cancels that worker first.
                await asyncio.sleep(0.2)

            t0 = time.monotonic()
            tester = run_tester(
                script,
                make_config(server.url, dump=True, dump_path=dump_dir),
                timeout_s=10.0,
            )
            assert time.monotonic() - t0 < 6.0
        with open(dump_path(dump_dir, "sj"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("sj")
        assert len(tester.recording.audio_bytes("sj")) == len(
            server.expected_pcm(1)
        )
        # The transport was closed by on_stop (client.close() ran).
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not any(
            kind == "close" for kind, _conn, _t in server.recorded.events
        ):
            time.sleep(0.02)
        assert any(
            kind == "close" for kind, _conn, _t in server.recorded.events
        ), server.recorded.events
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)
