#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Vendor error classification and secret handling."""
import asyncio
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
            # The request still gets its terminal event.
            end = await tester.wait_for_audio_end("nokey", timeout_s=2.0)
            assert end.payload["reason"] == 3
            assert end.payload["request_total_audio_duration_ms"] == 0
            assert tester.recording.frames == []

        run_tester(script, make_config(server.url, params={"key": ""}))
        assert server.recorded.connections == 0
    finally:
        server.stop()


def test_event_metadata_never_carries_endpoint_secrets():
    server = FakeKotobaServer(Scenario(chunks_per_response=2)).start()
    try:
        # Query names outside any known list: every value must be masked.
        secret_url = (
            server.url
            + "?sign=sig-secret-123&access_token=tok-secret-456"
            + "&X-Amz-Signature=amz-secret-789"
        )

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "meta", "メタデータ。", end=True)
            await tester.wait_for_audio_end("meta")
            for e in tester.recording.events:
                payload = json.dumps(e.payload)
                for secret in (
                    "sig-secret-123",
                    "tok-secret-456",
                    "amz-secret-789",
                ):
                    assert secret not in payload, (e.name, secret)
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


def test_transport_errors_never_quote_endpoint_secrets():
    """Connection refused on a credential-bearing endpoint: the SDK quotes
    the URL it tried; nothing we emit or log may carry the secrets."""
    secret_url = "ws://user:pw-secret-77@127.0.0.1:9/ws?sign=sig-secret-77"

    async def script(tester, ten_env):
        await tester.send_text(ten_env, "refused", "接続拒否。", end=True)
        end = await tester.wait_for_audio_end("refused", timeout_s=10.0)
        assert end.payload["reason"] == 3
        for e in tester.recording.events:
            text = json.dumps(e.payload, ensure_ascii=False)
            assert "pw-secret-77" not in text, e.name
            assert "sig-secret-77" not in text, e.name
        errors = tester.recording.named("error")
        assert len(errors) == 1 and errors[0].payload["code"] == NON_FATAL

    run_tester(
        script, make_config(secret_url, params={"request_timeout_seconds": 2})
    )


def test_malformed_property_error_never_echoes_rejected_input():
    """``params`` given as a bare string (someone pasted the key) fails
    pydantic validation; the rejected value must not appear anywhere."""
    server = FakeKotobaServer().start()
    try:

        async def script(tester, ten_env):
            await tester.wait_for_event("error")
            await tester.send_text(ten_env, "bad", "設定不正。", end=True)
            await tester.wait_for_audio_end("bad", timeout_s=2.0)
            for e in tester.recording.events:
                assert "KEY-MARKER-4242" not in json.dumps(e.payload)
            errors = tester.recording.named("error")
            assert all(e.payload["code"] == FATAL for e in errors)
            assert "params" in errors[0].payload["message"]

        run_tester(script, {"params": "KEY-MARKER-4242"})
        assert server.recorded.connections == 0
    finally:
        server.stop()


def test_transient_rate_limit_on_handshake_is_retried_silently():
    """The gateway answers the first handshake with 429: the retry on a
    fresh socket succeeds and the consumer sees nothing of it."""
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=2,
            handshake_status=429,
            handshake_status_count=1,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "rl1", "混雑。", end=True)
            end = await tester.wait_for_audio_end("rl1")
            assert end.payload["reason"] == 1
            assert tester.recording.named("error") == []
            assert tester.recording.audio_bytes("rl1") == server.expected_pcm(1)

        run_tester(script, make_config(server.url))
        assert server.recorded.connections == 2
    finally:
        server.stop()


def test_persistent_rate_limit_is_non_fatal_and_recoverable():
    """429 on both attempts: one NON_FATAL error naming the limit, one
    audio_end(ERROR), and the next request connects normally."""
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=2,
            handshake_status=429,
            handshake_status_count=2,
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "rl2", "制限中。", end=True)
            end = await tester.wait_for_audio_end("rl2")
            rec = tester.recording
            assert end.payload["reason"] == 3
            assert end.payload["request_total_audio_duration_ms"] == 0
            errors = rec.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == NON_FATAL
            assert errors[0].payload["vendor_info"]["code"] == "rate_limited"
            assert errors[0].payload["id"] == "rl2"
            await tester.send_text(ten_env, "rl3", "復旧。", end=True)
            end2 = await tester.wait_for_audio_end("rl3")
            assert end2.payload["reason"] == 1
            assert rec.audio_bytes("rl3") == server.expected_pcm(1)
            assert len(rec.named("error")) == 1

        run_tester(script, make_config(server.url))
        # Two refused handshakes for rl2, one accepted for rl3.
        assert server.recorded.connections == 3
        assert server.recorded.texts == ["復旧。"]
    finally:
        server.stop()


def test_text_rejected_by_the_service_is_non_fatal_and_not_retried():
    """The service fails the response with a request-level code: one
    NON_FATAL error carrying that code, no retry with the same text, and
    the next request works on the same connection."""
    server = FakeKotobaServer(
        Scenario(
            chunks_per_response=2,
            fail_response_index=1,
            fail_code="invalid_text",
        )
    ).start()
    try:

        async def script(tester, ten_env):
            await tester.send_text(ten_env, "bad", "却下される文。", end=True)
            end = await tester.wait_for_audio_end("bad")
            rec = tester.recording
            assert end.payload["reason"] == 3
            assert end.payload["request_total_audio_duration_ms"] == 0
            errors = rec.named("error")
            assert len(errors) == 1
            assert errors[0].payload["code"] == NON_FATAL
            assert errors[0].payload["vendor_info"]["code"] == "invalid_text"
            assert errors[0].payload["id"] == "bad"
            assert rec.audio_bytes("bad") == b""
            await tester.send_text(ten_env, "good", "次の文。", end=True)
            end2 = await tester.wait_for_audio_end("good")
            assert end2.payload["reason"] == 1
            assert rec.audio_bytes("good") == server.expected_pcm(1)
            assert len(rec.named("error")) == 1

        run_tester(script, make_config(server.url))
        assert server.recorded.texts == ["却下される文。", "次の文。"]
    finally:
        server.stop()


def test_init_failure_reports_each_request_once_across_deltas():
    """With the extension uninitialized, a request arriving as several
    deltas gets exactly one error and one audio_end, not one per delta."""
    server = FakeKotobaServer().start()
    try:

        async def script(tester, ten_env):
            await tester.wait_for_event("error")  # the init error
            await tester.send_text(ten_env, "multi", "一つ、", end=False)
            await tester.send_text(ten_env, "multi", "二つ、", end=False)
            await tester.send_text(ten_env, "multi", "三つ。", end=True)
            await tester.wait_for_audio_end("multi", timeout_s=2.0)
            await asyncio.sleep(0.3)
            errors = [
                e
                for e in tester.recording.named("error")
                if e.payload.get("id") == "multi"
            ]
            ends = [
                e
                for e in tester.recording.named("tts_audio_end")
                if e.payload["request_id"] == "multi"
            ]
            assert len(errors) == 1, len(errors)
            assert len(ends) == 1 and ends[0].payload["reason"] == 3
            # The queue is released: a following request is reported too.
            await tester.send_text(ten_env, "next", "次。", end=True)
            await tester.wait_for_audio_end("next", timeout_s=2.0)

        run_tester(script, make_config(server.url, params={"key": ""}))
        assert server.recorded.connections == 0
    finally:
        server.stop()
