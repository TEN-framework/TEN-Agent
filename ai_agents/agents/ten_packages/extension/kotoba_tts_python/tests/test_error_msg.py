#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Vendor error classification and secret handling."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_kotoba_server import FakeKotobaServer, Scenario  # noqa: E402
from helpers import make_config, run_tester  # noqa: E402

FATAL = -1000
NON_FATAL = 1000


def _assert_no_secret(tester, secret: str) -> None:
    for e in tester.recording.events:
        assert secret not in json.dumps(e.payload, ensure_ascii=False)


def test_rejected_key_is_fatal_and_never_logged():
    server = FakeKotobaServer(
        Scenario(handshake_status=401, reject_mode="http")
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "auth", "認証失敗。", end=True)
            end = await tester.wait_for_audio_end("auth")
            errors = tester.recording.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == FATAL
            assert errors[0].payload["vendor_info"]["code"] == "unauthorized"
            assert errors[0].payload["id"] == "auth"
            assert end.payload["reason"] == 3
            assert tester.recording.frames == []
            _assert_no_secret(tester, "secret-key-123")
            _assert_no_secret(tester, "認証失敗")

        run_tester(
            script, make_config(server.url, params={"key": "secret-key-123"})
        )
        # A fatal error is not retried.
        assert server.recorded.connections == 1
    finally:
        server.stop()


def test_policy_close_1008_is_fatal_like_fal():
    """fal accepts the upgrade and closes with 1008 for a bad key."""
    server = FakeKotobaServer(Scenario(reject_mode="close")).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "auth2", "鍵が違う。", end=True)
            end = await tester.wait_for_audio_end("auth2")
            errors = tester.recording.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == FATAL
            assert errors[0].payload["vendor_info"]["code"] == "unauthorized"
            assert end.payload["reason"] == 3
            _assert_no_secret(tester, "invalid")

        run_tester(script, make_config(server.url, params={"key": "invalid"}))
        assert server.recorded.connections == 1
    finally:
        server.stop()


def test_unsupported_language_is_fatal():
    server = FakeKotobaServer(
        Scenario(open_error="unsupported_language")
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "lang", "言語。", end=True)
            await tester.wait_for_audio_end("lang")
            errors = tester.recording.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == FATAL
            assert (
                errors[0].payload["vendor_info"]["code"]
                == "unsupported_language"
            )

        run_tester(script, make_config(server.url, params={"language": "xx"}))
        assert server.recorded.connections == 1
    finally:
        server.stop()


def test_worker_failure_before_audio_is_retried_silently():
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=2,
            fail_response_index=1,
            fail_code="worker_unavailable",
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "retry", "再試行。", end=True)
            end = await tester.wait_for_audio_end("retry")
            assert end.payload["reason"] == 1
            assert tester.recording.named("error") == []
            assert tester.recording.audio_bytes("retry") == server.expected_pcm(
                1
            )

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["再試行。", "再試行。"]
        assert server.recorded.connections == 2
    finally:
        server.stop()


def test_worker_failure_after_audio_is_non_fatal_and_recoverable():
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=4,
            fail_response_index=1,
            fail_after_chunks=1,
            fail_code="worker_unavailable",
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "fail", "途中失敗。", end=True)
            end = await tester.wait_for_audio_end("fail")
            rec = tester.recording
            assert end.payload["reason"] == 3
            assert end.payload["request_total_audio_duration_ms"] == (
                800 * 2 * 1000 // (16000 * 2)
            )
            errors = rec.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == NON_FATAL
            assert (
                errors[0].payload["vendor_info"]["code"] == "worker_unavailable"
            )
            await tester.send_text(ten_env, "ok", "復旧。", end=True)
            end2 = await tester.wait_for_audio_end("ok")
            assert end2.payload["reason"] == 1
            assert rec.audio_bytes("ok") == server.expected_pcm(1)

        run_tester(script, make_config(server.url))
    finally:
        server.stop()


def test_missing_key_fails_at_init_and_on_request():
    server = FakeKotobaServer().start()
    try:

        async def script(tester, ten_env):
            await tester.wait_for_event("error")
            init_errors = tester.recording.named("error")
            assert init_errors[0].payload["code"] == FATAL
            assert "key" in init_errors[0].payload["message"]
            await tester.send_text(ten_env, "nokey", "鍵なし。", end=True)
            await tester.wait_for(
                lambda r: any(
                    e.payload.get("id") == "nokey" for e in r.named("error")
                )
            )
            assert tester.recording.frames == []

        run_tester(script, make_config(server.url, params={"key": ""}))
        assert server.recorded.connections == 0
    finally:
        server.stop()


def test_event_metadata_never_carries_endpoint_secrets():
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:
        secret_url = server.url + "?sign=sig-secret-123"

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "meta", "メタデータ。", end=True)
            await tester.wait_for_audio_end("meta")
            for e in tester.recording.events:
                assert "sig-secret-123" not in json.dumps(e.payload)
            start = tester.recording.named("tts_audio_start")[0]
            assert (
                "127.0.0.1"
                in start.payload["metadata"]["vendor_metadata"]["url"]
            )

        run_tester(script, make_config(secret_url))
    finally:
        server.stop()


def test_unexpected_negotiated_format_is_fatal():
    server = FakeKotobaServer(
        Scenario(chunks_per_response=2, negotiate_format="pcm_f32")
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "fmt", "形式。", end=True)
            end = await tester.wait_for_audio_end("fmt")
            errors = tester.recording.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == FATAL
            assert (
                errors[0].payload["vendor_info"]["code"] == "unsupported_format"
            )
            assert end.payload["reason"] == 3
            assert tester.recording.frames == []

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 1
        assert server.recorded.texts == []
    finally:
        server.stop()


def test_unexpected_worker_exception_ends_request_and_recovers():
    from unittest.mock import patch
    import kotoba_tts_python.extension as ext_mod

    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    original = ext_mod.KotobaTTSClient.synthesize
    state = {"raised": False}

    def exploding_synthesize(self, text):
        if not state["raised"]:
            state["raised"] = True
            raise RuntimeError("boom")
        return original(self, text)

    try:
        with patch.object(
            ext_mod.KotobaTTSClient, "synthesize", exploding_synthesize
        ):

            async def script(tester, ten_env):
                await tester.send_text(ten_env, "boom", "爆発。", end=True)
                end = await tester.wait_for_audio_end("boom")
                assert end.payload["reason"] == 3
                errors = tester.recording.named("error")
                assert len(errors) == 1
                assert errors[0].payload["code"] == NON_FATAL
                assert (
                    errors[0].payload["vendor_info"]["code"]
                    == "unexpected_error"
                )
                assert "爆発" not in errors[0].payload["message"]
                await tester.send_text(ten_env, "ok", "回復。", end=True)
                end2 = await tester.wait_for_audio_end("ok")
                assert end2.payload["reason"] == 1

            run_tester(script, make_config(server.url))
    finally:
        server.stop()
