"""Exercise actual TEN reporting, with only the provider transport mocked."""

import asyncio
import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ten_ai_base.message import ModuleErrorCode
from ten_runtime import Data

from speko_asr_python.client import SpekoRouterError
from speko_asr_python.config import SpekoASRConfig
from speko_asr_python.extension import SpekoASRExtension


def extension_and_events():
    extension = SpekoASRExtension("speko")
    extension.config = SpekoASRConfig(api_key="test-secret-key-long")
    extension.ten_env = MagicMock()
    events = []

    async def send(data):
        raw, _ = data.get_property_to_json("")
        events.append((data.get_name(), json.loads(raw)))

    extension.ten_env.send_data = AsyncMock(side_effect=send)
    extension.client = MagicMock(
        is_ready=True,
        send_audio=AsyncMock(),
        commit=AsyncMock(),
        close=AsyncMock(),
    )
    return extension, events


def audio(metadata=None, size=32000):
    frame = MagicMock()
    frame.get_buf.return_value = bytes(size)
    frame.lock_buf.return_value = bytes(size)
    frame.get_property_to_json.return_value = (
        json.dumps(metadata or {"session_id": "audio-session"}),
        None,
    )
    return frame


def finalize_data(finalize_id, session_id):
    data = Data.create("asr_finalize")
    data.set_property_string("finalize_id", finalize_id)
    data.set_property_from_json(
        "metadata",
        json.dumps({"session_id": session_id, "custom": finalize_id}),
    )
    return data


def payloads(events, name):
    return [payload for kind, payload in events if kind == name]


@pytest.mark.asyncio
async def test_emitted_results_preserve_metadata_and_ids_without_empty_turns():
    ext, events = extension_and_events()
    metadata = {
        "session_id": "audio-session",
        "custom": "keep",
        "asr_info": {"caller": 1},
    }
    await ext._handle_audio_frame(ext.ten_env, audio(metadata))
    original = copy.deepcopy(ext.metadata)
    ext.first_audio_time = asyncio.get_running_loop().time() - 0.1
    for kind, text in (
        ("transcript.delta", "hello"),
        ("transcript.final", "hello"),
        ("transcript.final", ""),
        ("transcript.delta", " "),
    ):
        await ext._on_router_event({"type": kind, "text": text, "speaker": "A"})
    results = payloads(events, "asr_result")
    assert len(results) == 2
    assert results[0]["id"] == results[1]["id"]
    assert results[1]["final"] is True
    assert results[1]["language"] == "en-US"
    assert "session_id" not in results[1]
    assert results[1]["metadata"] == {
        **metadata,
        "asr_info": {
            "caller": 1,
            "vendor": "speko",
            "locked": False,
            "speaker": "A",
        },
    }
    assert ext.metadata == original
    metrics = payloads(events, "metrics")
    assert metrics and metrics[0]["metadata"]["session_id"] == "audio-session"


@pytest.mark.asyncio
async def test_concurrent_finalize_echoes_each_request_and_blocks_later_audio():
    ext, events = extension_and_events()
    await ext._handle_audio_frame(ext.ten_env, audio())
    entered, release = asyncio.Event(), asyncio.Event()

    async def commit():
        entered.set()
        await release.wait()
        await ext._on_router_event({"type": "transcript.final", "text": "done"})

    ext.client.commit.side_effect = commit
    first = asyncio.create_task(
        ext.on_data(ext.ten_env, finalize_data("one", "session-one"))
    )
    await entered.wait()
    second = asyncio.create_task(
        ext.on_data(ext.ten_env, finalize_data("two", "session-two"))
    )
    later_audio = asyncio.create_task(
        ext._handle_audio_frame(ext.ten_env, audio({"session_id": "next"}))
    )
    await asyncio.sleep(0)
    assert ext.client.commit.await_count == 1
    assert not later_audio.done()
    release.set()
    await asyncio.wait_for(asyncio.gather(first, second, later_audio), 1)
    acknowledgements = payloads(events, "asr_finalize_end")
    assert [
        (item["finalize_id"], item["metadata"]["session_id"])
        for item in acknowledgements
    ] == [("one", "session-one"), ("two", "session-two")]
    assert all(
        item["metadata"]["custom"] == item["finalize_id"]
        for item in acknowledgements
    )
    kinds = [kind for kind, _ in events]
    assert kinds.index("asr_result") < kinds.index("asr_finalize_end")
    assert ext.last_finalize_time is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        None,
        SpekoRouterError("request_timeout", "timeout", retryable=True),
        OSError("closed"),
    ],
)
async def test_finalize_acknowledges_disconnection_and_errors(failure):
    ext, events = extension_and_events()
    if failure is None:
        ext.client = None
    else:
        ext.client.commit.side_effect = failure
    await ext.on_data(ext.ten_env, finalize_data("id", "final-session"))
    await ext.stop_connection()
    assert payloads(events, "asr_finalize_end") == [
        {
            "finalize_id": "id",
            "metadata": {"session_id": "final-session", "custom": "id"},
        }
    ]


@pytest.mark.asyncio
async def test_real_status_events_redact_key_and_url():
    ext, events = extension_and_events()
    ext.config.base_url = "https://alice:password@example.com/router?token=private&signature=signed#secret"
    clients = []

    def factory(**kwargs):
        client = MagicMock(is_ready=True, close=AsyncMock())

        async def connect():
            await kwargs["on_event"]({"type": "session.ready"})

        client.connect = AsyncMock(side_effect=connect)
        clients.append((client, kwargs))
        return client

    with patch(
        "speko_asr_python.extension.SpekoASRClient", side_effect=factory
    ):
        await ext.start_connection()
        await ext.start_connection()
        before = list(events)
        await clients[0][1]["on_disconnect"](
            SpekoRouterError("relay_error", "old", retryable=True)
        )
        await clients[0][1]["on_event"](
            {"type": "transcript.final", "text": "stale"}
        )
        assert events == before
        assert ext.client is clients[1][0]
        await ext.on_stop(ext.ten_env)
    statuses = payloads(events, "connection_status_changed")
    assert [item["current"] for item in statuses] == [
        "connecting",
        "connected",
        "connecting",
        "connected",
        "disconnected",
    ]
    serialized = json.dumps(events) + ext.config.to_str()
    for secret in (
        "test-secret-key-long",
        "alice",
        "password",
        "private",
        "signed",
        "#secret",
    ):
        assert secret not in serialized
    vendor = statuses[1]["metadata"]["vendor_metadata"]
    assert vendor["base_url"] == "https://example.com/router"
    assert "key" in vendor and "api_key" not in vendor


@pytest.mark.asyncio
async def test_invalid_configuration_is_latched_before_any_connect_attempt():
    ext, events = extension_and_events()
    ext.client = None
    ext.ten_env.get_property_bool = AsyncMock(return_value=(True, None))
    ext.ten_env.get_property_to_json = AsyncMock(
        return_value=(
            json.dumps(
                {"params": {"api_key": "private-value", "base_url": "invalid"}}
            ),
            None,
        )
    )
    # The real base initializer starts a consumer; stop it through the lifecycle.
    with patch("speko_asr_python.extension.SpekoASRClient") as constructor:
        await ext.on_init(ext.ten_env)
        await ext.on_start(ext.ten_env)
        for _ in range(3):
            await ext.on_audio_frame(ext.ten_env, audio())
            await ext.on_data(ext.ten_env, Data.create("trigger_connect"))
        await ext.on_stop(ext.ten_env)
        constructor.assert_not_called()
    assert len(payloads(events, "error")) == 1
    assert payloads(events, "error")[0]["code"] == int(
        ModuleErrorCode.FATAL_ERROR.value
    )
    assert "private-value" not in json.dumps(events)


@pytest.mark.asyncio
async def test_bounded_reconnect_escalates_and_success_resets_counter():
    ext, events = extension_and_events()
    ext.client = None
    ext.start_connection = AsyncMock()
    real_sleep = asyncio.sleep
    delays = []

    async def sleep(delay):
        delays.append(delay)
        await real_sleep(0)

    with patch("speko_asr_python.extension.asyncio.sleep", side_effect=sleep):
        await ext._reconnect()
    assert delays == [0.5, 1, 2, 4, 4]
    assert ext.start_connection.await_count == 5
    assert ext._reconnect_attempts == 5
    assert payloads(events, "error")[-1]["code"] == int(
        ModuleErrorCode.FATAL_ERROR.value
    )
    await ext._ensure_connection()
    assert ext.start_connection.await_count == 5
    ext._permanent_error = None
    ext.client = MagicMock(is_ready=True)
    ext.on_connected = AsyncMock()
    await ext._on_router_event({"type": "session.ready"})
    assert ext._reconnect_attempts == 0


@pytest.mark.asyncio
async def test_stop_cancels_commit_and_never_reports_after_shutdown():
    ext, events = extension_and_events()
    started = asyncio.Event()

    async def commit():
        started.set()
        await asyncio.Future()

    ext.client.commit.side_effect = commit
    pending = asyncio.create_task(
        ext.on_data(ext.ten_env, finalize_data("stop", "session"))
    )
    await started.wait()
    await asyncio.wait_for(ext.on_stop(ext.ten_env), 1)
    await asyncio.wait_for(pending, 1)
    assert not payloads(events, "asr_finalize_end")
    assert ext.client is None


@pytest.mark.asyncio
@pytest.mark.parametrize("reset_clock", [False, True])
async def test_segment_timeline_two_cycles_and_reconnect(reset_clock):
    ext, events = extension_and_events()
    await ext._handle_audio_frame(ext.ten_env, audio())
    await ext._on_router_event(
        {
            "type": "transcript.final",
            "text": "one",
            "segments": [{"start_ms": 0, "end_ms": 1000, "text": "one"}],
        }
    )
    await ext.on_data(ext.ten_env, finalize_data("one", "audio-session"))
    await ext._handle_audio_frame(ext.ten_env, audio())
    start = 0 if reset_clock else 1000
    await ext._on_router_event(
        {
            "type": "transcript.final",
            "text": "two",
            "segments": [
                {"start_ms": start, "end_ms": start + 1000, "text": "two"}
            ],
        }
    )

    def factory(**kwargs):
        async def connect():
            await kwargs["on_event"]({"type": "session.ready"})

        return MagicMock(
            is_ready=True,
            close=AsyncMock(),
            send_audio=AsyncMock(),
            connect=AsyncMock(side_effect=connect),
        )

    with patch(
        "speko_asr_python.extension.SpekoASRClient", side_effect=factory
    ):
        await ext.start_connection()
        await ext._handle_audio_frame(ext.ten_env, audio())
        await ext._on_router_event(
            {
                "type": "transcript.final",
                "text": "three",
                "segments": [{"start_ms": 0, "end_ms": 1000, "text": "three"}],
            }
        )
    results = payloads(events, "asr_result")
    assert [(item["start_ms"], item["duration_ms"]) for item in results] == [
        (0, 1000),
        (1000, 1000),
        (2000, 1000),
    ]
    assert [item["words"][0]["start_ms"] for item in results] == [0, 1000, 2000]
    await ext.on_stop(ext.ten_env)


@pytest.mark.asyncio
async def test_buffered_frames_keep_session_metadata_and_dump_exact_ingress(
    tmp_path,
):
    ext, events = extension_and_events()
    ext.config.dump = True
    ext.config.dump_path = str(tmp_path / "audio.pcm")
    await ext._start_dumper()
    client = ext.client
    client.is_ready = False
    ext.auto_connect = False
    for session in ("old", "new"):
        frame = audio({"session_id": session})
        await ext.on_audio_frame(ext.ten_env, frame)
        await ext._handle_audio_frame(
            ext.ten_env, ext.audio_frames_queue.get_nowait()
        )
    client.is_ready = True
    ext.on_connected = AsyncMock()
    await ext._on_router_event({"type": "session.ready"})
    for _ in range(2):
        await ext._handle_audio_frame(
            ext.ten_env, ext.audio_frames_queue.get_nowait()
        )
        await ext._on_router_event(
            {"type": "transcript.final", "text": "hello"}
        )
    assert [
        item["metadata"]["session_id"]
        for item in payloads(events, "asr_result")
    ] == ["old", "new"]
    await ext.stop_connection()
    assert ext.audio_dumper is not None
    await ext.on_deinit(ext.ten_env)
    assert (tmp_path / "audio.pcm").read_bytes() == bytes(64000)


@pytest.mark.asyncio
async def test_dropped_audio_and_fractional_frames_have_correct_timeline():
    ext, _ = extension_and_events()
    ext.client.is_ready = False
    ext.config.buffer_duration_ms = 10
    await ext._handle_audio_frame(ext.ten_env, audio(size=640))
    assert ext.buffered_frames_size == 0
    assert ext.audio_timeline.total_dropped_audio_duration == 20
    ext.client.is_ready = True
    ext.config.sample_rate = 44100
    for _ in range(100):
        await ext._handle_audio_frame(ext.ten_env, audio(size=882))
    assert ext.audio_timeline.total_user_audio_duration == 1000
    assert ext.audio_timeline.get_audio_duration_before_time(500) == 520


@pytest.mark.parametrize(
    "params",
    [
        {"base_url": "ftp://example.com"},
        {"base_url": "https://"},
        {"base_url": "https://example.com:bad"},
        {"language": "bad tag"},
        {"ready_timeout_sec": 0},
        {"finalize_timeout_sec": float("inf")},
        {"sample_rate": 1},
        {"channels": 0},
        {"routing": {"mode": "wrong"}},
    ],
)
def test_invalid_config_values(params):
    with pytest.raises(ValueError):
        config = SpekoASRConfig(api_key="key", params=params)
        config.update_params()


@pytest.mark.asyncio
async def test_stop_waits_for_active_send_and_closes_once():
    ext, events = extension_and_events()
    entered, release = asyncio.Event(), asyncio.Event()
    client = ext.client

    async def send(_audio):
        entered.set()
        await release.wait()

    client.send_audio.side_effect = send
    frame = audio()
    sending = asyncio.create_task(ext.send_audio(frame, "session"))
    await entered.wait()
    stopping = asyncio.create_task(ext.on_stop(ext.ten_env))
    await asyncio.sleep(0)
    assert not ext.is_connected()
    client.close.assert_not_awaited()
    release.set()
    await asyncio.wait_for(asyncio.gather(sending, stopping), 1)
    client.close.assert_awaited_once()
    frame.unlock_buf.assert_called_once()
    before = len(events)
    await ext.on_audio_frame(ext.ten_env, audio())
    assert len(events) == before


@pytest.mark.asyncio
async def test_error_and_late_disconnect_have_one_report():
    ext, events = extension_and_events()
    ext.auto_connect = False
    epoch = ext._connection_epoch
    error = SpekoRouterError("route_not_found", "no route")
    await ext._reset_connection(error, epoch)
    await ext._reset_connection(error, epoch)
    await ext.stop_connection()
    errors = payloads(events, "error")
    assert len(errors) == 1
    assert errors[0]["code"] == int(ModuleErrorCode.FATAL_ERROR.value)
    assert errors[0]["vendor_info"] == {
        "vendor": "speko",
        "code": "route_not_found",
        "message": "no route",
    }


@pytest.mark.asyncio
async def test_metrics_have_session_metadata_and_timeline_excludes_silence():
    ext, events = extension_and_events()
    await ext._handle_audio_frame(ext.ten_env, audio())
    ext.audio_timeline.add_silence_audio(500)
    await ext._handle_audio_frame(ext.ten_env, audio())

    async def commit():
        await ext._on_router_event(
            {
                "type": "transcript.final",
                "text": "hello",
                "segments": [
                    {"text": "hello", "start_ms": 1500, "end_ms": 2500}
                ],
            }
        )

    ext.client.commit.side_effect = commit
    await ext.on_data(ext.ten_env, finalize_data("id", "audio-session"))
    await ext._on_router_event(
        {"type": "usage.updated", "usage": {"duration_ms": 2000}}
    )
    await ext._send_audio_actual_send_metrics()
    metric_messages = payloads(events, "metrics")
    metrics = {
        key: value
        for payload in metric_messages
        for key, value in payload["metrics"].items()
    }
    assert {
        "ttfw",
        "ttlw",
        "vendor_metrics",
        "actual_send",
        "actual_send_delta",
    } <= metrics.keys()
    assert all(
        payload["metadata"]["session_id"] == "audio-session"
        for payload in metric_messages
    )
    assert metrics["actual_send"] == 2500
    result = payloads(events, "asr_result")[0]
    assert (result["start_ms"], result["duration_ms"]) == (1000, 1000)


@pytest.mark.asyncio
async def test_shutdown_reports_drained_usage_without_old_callbacks():
    ext, events = extension_and_events()
    ext.metadata = {"session_id": "session"}
    ext.session_id = "session"
    client = ext.client
    client.usage = {"duration_ms": 1000}
    await ext.on_stop(ext.ten_env)
    client.close.assert_awaited_once_with(drain=True)
    metrics = payloads(events, "metrics")
    assert any(
        item["metrics"].get("vendor_metrics")
        == {"usage": {"duration_ms": 1000}}
        for item in metrics
    )


@pytest.mark.asyncio
async def test_stop_finishes_cleanup_cancelled_with_reconnect():
    ext, _ = extension_and_events()
    client = ext.client
    entered = asyncio.Event()

    async def close(*, drain):
        if not drain:
            entered.set()
            await asyncio.Future()

    client.close.side_effect = close
    await ext._reset_connection(
        SpekoRouterError("relay_error", "closed", retryable=True)
    )
    await entered.wait()
    await asyncio.wait_for(ext.on_stop(ext.ten_env), 1)
    assert client.close.await_count == 2
    assert client.close.await_args.kwargs == {"drain": True}
    assert not ext._retired_clients


@pytest.mark.asyncio
async def test_finalize_joins_handshake_and_commits_buffered_audio_before_ack():
    ext, events = extension_and_events()
    ext.client = None
    entered, ready = asyncio.Event(), asyncio.Event()
    order = []

    def factory(**kwargs):
        client = MagicMock(is_ready=False, close=AsyncMock(), usage={})

        async def connect():
            entered.set()
            await ready.wait()
            client.is_ready = True
            await kwargs["on_event"]({"type": "session.ready"})

        async def send(_audio):
            order.append(ext.session_id)

        async def commit():
            order.append("commit")
            await kwargs["on_event"](
                {"type": "transcript.final", "text": "buffered speech"}
            )

        client.connect = connect
        client.send_audio = send
        client.commit = commit
        return client

    consumer = asyncio.create_task(ext._audio_frame_consumer())
    try:
        with patch("speko_asr_python.extension.SpekoASRClient", factory):
            connection = asyncio.create_task(ext._ensure_connection())
            await entered.wait()
            for session in ("first", "second"):
                await ext.on_audio_frame(
                    ext.ten_env, audio({"session_id": session})
                )
            await ext._audio_queue_drained.wait()
            assert ext.buffered_frames.qsize() == 2
            finalize = asyncio.create_task(
                ext.on_data(ext.ten_env, finalize_data("early", "turn"))
            )
            await asyncio.sleep(0)
            later = asyncio.create_task(
                ext.on_audio_frame(ext.ten_env, audio({"session_id": "later"}))
            )
            await asyncio.sleep(0)
            assert not payloads(events, "asr_finalize_end")
            assert not later.done()
            ready.set()
            await asyncio.wait_for(
                asyncio.gather(connection, finalize, later), 1
            )
            await ext._audio_queue_drained.wait()
        assert order == ["first", "second", "commit", "later"]
        assert len(payloads(events, "asr_result")) == 1
        assert payloads(events, "asr_finalize_end")[0]["finalize_id"] == "early"
    finally:
        await ext.on_stop(ext.ten_env)
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)


@pytest.mark.asyncio
async def test_finalize_waits_for_already_queued_audio_on_ready_connection():
    ext, events = extension_and_events()
    order = []

    async def send(_audio):
        await asyncio.sleep(0)
        order.append(ext.session_id)

    async def commit():
        order.append("commit")

    ext.client.send_audio.side_effect = send
    ext.client.commit.side_effect = commit
    consumer = asyncio.create_task(ext._audio_frame_consumer())
    try:
        for session in ("first", "second"):
            await ext.on_audio_frame(
                ext.ten_env, audio({"session_id": session})
            )
        await asyncio.wait_for(
            ext.on_data(ext.ten_env, finalize_data("queued", "turn")), 1
        )
        assert order == ["first", "second", "commit"]
        assert len(payloads(events, "asr_finalize_end")) == 1
    finally:
        await ext.on_stop(ext.ten_env)
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
