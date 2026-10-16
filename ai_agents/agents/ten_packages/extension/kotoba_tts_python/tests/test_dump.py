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
from helpers import make_config, run_tester  # noqa: E402


def _dump_file(dump_dir: str, request_id: str) -> str:
    return os.path.join(dump_dir, f"kotoba_tts_dump_{request_id}.pcm")


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
        assert files == ["kotoba_tts_dump_d1.pcm", "kotoba_tts_dump_d2.pcm"]
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
        assert files == ["kotoba_tts_dump_.._evil_id.pcm"]
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
