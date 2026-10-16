#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Dump files hold exactly the emitted PCM, one file per request."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import dump_path as _dump_file  # noqa: E402
from helpers import make_config, run_tester  # noqa: E402


def test_dump_matches_emitted_audio_per_request():
    dump_dir = tempfile.mkdtemp(prefix="kotoba_dump_")
    server = FakeKotobaServer(Scenario(chunks_per_response=3)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "d1", "一文目。二文目。", end=True)
            await tester.wait_for_audio_end("d1")
            await tester.send_text(ten_env, "d2", "三文目。", end=True)
            await tester.wait_for_audio_end("d2")

        tester = run_tester(
            script, make_config(server.url, dump=True, dump_path=dump_dir)
        )
        files = sorted(os.listdir(dump_dir))
        assert files == sorted(
            os.path.basename(_dump_file(dump_dir, rid)) for rid in ("d1", "d2")
        )
        with open(_dump_file(dump_dir, "d1"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("d1")
        with open(_dump_file(dump_dir, "d2"), "rb") as f:
            assert f.read() == tester.recording.audio_bytes("d2")
        assert tester.recording.audio_bytes("d1") == server.expected_pcm(2)
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_dump_is_finalized_on_flush_and_sanitizes_request_id():
    dump_dir = tempfile.mkdtemp(prefix="kotoba_dump_")
    server = FakeKotobaServer(
        Scenario(chunks_per_response=40, chunk_delay_s=0.05)
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "../evil/id", "長い文。", end=True)
            await tester.wait_for_event("pcm_frame", count=2)
            await tester.send_flush(ten_env)
            await tester.wait_for_event("tts_flush_end")
            await tester.wait_for_audio_end("../evil/id", timeout_s=1.0)

        tester = run_tester(
            script, make_config(server.url, dump=True, dump_path=dump_dir)
        )
        files = os.listdir(dump_dir)
        assert files == [os.path.basename(_dump_file(dump_dir, "../evil/id"))]
        assert "/" not in files[0] and files[0].startswith("kotoba_tts_dump_")
        with open(os.path.join(dump_dir, files[0]), "rb") as f:
            data = f.read()
        assert data == tester.recording.audio_bytes("../evil/id")
        assert 0 < len(data) < len(server.expected_pcm(1))
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_dump_write_failure_does_not_fail_the_request():
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_dump_")
    server = FakeKotobaServer(Scenario(chunks_per_response=3)).start()

    async def failing_write(self, data):
        raise OSError("disk full")

    try:
        with patch.object(ext_mod.PCMWriter, "write", failing_write):

            async def script(tester, ten_env):
                await tester.send_text(
                    ten_env, "nodisk", "書けない。", end=True
                )
                end = await tester.wait_for_audio_end("nodisk")
                assert end.payload["reason"] == 1
                assert tester.recording.audio_bytes(
                    "nodisk"
                ) == server.expected_pcm(1)
                assert end.payload["request_total_audio_duration_ms"] == (
                    len(server.expected_pcm(1)) * 1000 // 32000
                )
                assert tester.recording.named("error") == []

            run_tester(
                script, make_config(server.url, dump=True, dump_path=dump_dir)
            )
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_unusable_dump_path_does_not_strand_the_queue():
    """dump_path names an existing file, so the directory cannot be created.
    The request must still complete, and so must the next one."""
    blocker = tempfile.NamedTemporaryFile(
        prefix="kotoba_not_a_dir_", delete=False
    )
    blocker.close()
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "d1", "一。", end=True)
            end1 = await tester.wait_for_audio_end("d1")
            assert end1.payload["reason"] == 1
            await tester.send_text(ten_env, "d2", "二。", end=True)
            end2 = await tester.wait_for_audio_end("d2")
            assert end2.payload["reason"] == 1
            assert tester.recording.named("error") == []
            assert tester.recording.audio_bytes("d2") == server.expected_pcm(1)

        run_tester(
            script, make_config(server.url, dump=True, dump_path=blocker.name)
        )
    finally:
        server.stop()
        os.unlink(blocker.name)


def test_dump_is_finalized_on_error_with_partial_audio():
    dump_dir = tempfile.mkdtemp(prefix="kotoba_dump_")
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=4, fail_response_index=1, fail_after_chunks=2
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "err", "途中失敗。", end=True)
            end = await tester.wait_for_audio_end("err")
            assert end.payload["reason"] == 3

        tester = run_tester(
            script, make_config(server.url, dump=True, dump_path=dump_dir)
        )
        with open(_dump_file(dump_dir, "err"), "rb") as f:
            data = f.read()
        assert data == tester.recording.audio_bytes("err")
        assert len(data) == 2 * 800 * 2
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_large_dump_with_slow_writer_is_exact_and_isolated():
    """96 KB of audio crosses PCMWriter's 64 KiB auto-flush while the file
    write itself is slowed down; the finalized dump must equal the emitted
    PCM, and a flush under load must not lose the buffered tail."""
    import time as _time
    from unittest.mock import patch
    import ten_ai_base.helper as helper_mod

    dump_dir = tempfile.mkdtemp(prefix="kotoba_dump_big_")
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=60, samples_per_chunk=800, chunk_delay_s=0.01
        )
    ).start()
    original_write = helper_mod.write_pcm_to_file

    def slow_write(data, path):
        _time.sleep(0.15)
        return original_write(data, path)

    try:
        with patch.object(helper_mod, "write_pcm_to_file", slow_write):

            async def script(tester, ten_env):
                await tester.send_text(
                    ten_env, "big", "長い長い文章。", end=True
                )
                await tester.wait_for_audio_end("big", timeout_s=15.0)
                # flush under load: second request interrupted mid-stream
                await tester.send_text(
                    ten_env, "cut", "途中で止める。", end=True
                )
                await tester.wait_for(
                    lambda r: len(r.audio_bytes("cut")) >= 70_000,
                    timeout_s=15.0,
                )
                await tester.send_flush(ten_env)
                await tester.wait_for_event("tts_flush_end")
                await tester.wait_for_audio_end("cut", timeout_s=2.0)
                await tester.send_text(ten_env, "after", "次。", end=True)
                await tester.wait_for_audio_end("after", timeout_s=15.0)

            tester = run_tester(
                script,
                make_config(server.url, dump=True, dump_path=dump_dir),
                timeout_s=60.0,
            )
        for rid in ("big", "cut", "after"):
            with open(_dump_file(dump_dir, rid), "rb") as f:
                data = f.read()
            assert data == tester.recording.audio_bytes(rid), rid
        assert len(tester.recording.audio_bytes("big")) == 60 * 1600
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_colliding_request_ids_get_separate_dump_files():
    """``a/b`` and ``a_b`` sanitize to the same text; each request must
    still get its own file holding exactly its own audio."""
    dump_dir = tempfile.mkdtemp(prefix="kotoba_dump_")
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "a/b", "一つ目。", end=True)
            await tester.wait_for_audio_end("a/b")
            await tester.send_text(ten_env, "a_b", "二つ目。", end=True)
            await tester.wait_for_audio_end("a_b")

        tester = run_tester(
            script, make_config(server.url, dump=True, dump_path=dump_dir)
        )
        first, second = _dump_file(dump_dir, "a/b"), _dump_file(dump_dir, "a_b")
        assert first != second
        assert sorted(os.listdir(dump_dir)) == sorted(
            os.path.basename(f) for f in (first, second)
        )
        with open(first, "rb") as f:
            assert f.read() == tester.recording.audio_bytes("a/b")
        with open(second, "rb") as f:
            assert f.read() == tester.recording.audio_bytes("a_b")
        assert len(tester.recording.audio_bytes("a/b")) == len(
            server.expected_pcm(1)
        )
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)


def test_existing_dump_file_is_replaced_not_appended():
    """A stale file with this request's name (an earlier run, the same id
    reused) must not be appended to: the file holds only this run's audio."""
    dump_dir = tempfile.mkdtemp(prefix="kotoba_dump_")
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:
        stale = _dump_file(dump_dir, "again")
        with open(stale, "wb") as f:
            f.write(b"\x7f" * 4096)

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "again", "もう一度。", end=True)
            await tester.wait_for_audio_end("again")

        tester = run_tester(
            script, make_config(server.url, dump=True, dump_path=dump_dir)
        )
        with open(stale, "rb") as f:
            data = f.read()
        assert data == tester.recording.audio_bytes("again")
        assert b"\x7f" * 16 not in data
    finally:
        server.stop()
        shutil.rmtree(dump_dir, ignore_errors=True)
