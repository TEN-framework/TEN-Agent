"""Check case isolation and overlapping messages at the graph's bridge boundary."""

import asyncio
import json

import pytest

from conftest import Message, Result, StatusCode


@pytest.fixture
def bridge(modules, env):
    extension = modules.bridge.AgoraMindBridgeExtension("bridge")
    extension.ten_env = env
    extension.session_id = 7
    extension.config.command_timeout_ms = 10
    env.send_cmd.return_value = (
        Result.create(StatusCode.OK, Message("ok")),
        None,
    )
    return extension


def completed(sequence=1, session_id=7):
    return Message(
        "agora_mind_event",
        {
            "event_json": json.dumps(
                {
                    "type": "workspace.event",
                    "event": {
                        "type": "session_turn_completed",
                        "session_id": session_id,
                        "source": {"type": "top_level"},
                        "input_sequence_range": {
                            "first": sequence,
                            "last": sequence,
                        },
                        "result": [{"type": "text", "text": "Done."}],
                    },
                }
            )
        },
    )


@pytest.mark.asyncio
async def test_overlapping_asr_finals_are_submitted_once(bridge, env):
    entered, release = asyncio.Event(), asyncio.Event()

    async def submit(_cmd):
        entered.set()
        await release.wait()
        return Result.create(StatusCode.OK, Message("ok")), None

    env.send_cmd.side_effect = submit
    final = Message("asr_result", {"text": "Book the flight", "final": True})
    first = asyncio.create_task(bridge.on_data(env, final))
    await entered.wait()
    await bridge.on_data(env, final)
    release.set()
    await first
    env.send_cmd.assert_awaited_once()


@pytest.mark.asyncio
async def test_ambiguous_input_timeout_is_not_retried(bridge, env):
    async def pending(_cmd):
        await asyncio.Event().wait()

    env.send_cmd.side_effect = pending
    final = Message("asr_result", {"text": "Book the flight", "final": True})
    await bridge.on_data(env, final)
    await bridge.on_data(env, final)
    env.send_cmd.assert_awaited_once()
    env.log_error.assert_called_once()


@pytest.mark.asyncio
async def test_delayed_and_overlapping_turn_replays_do_not_repeat_tts(
    bridge, env
):
    entered, release = asyncio.Event(), asyncio.Event()

    async def synthesize(_data):
        entered.set()
        await release.wait()

    env.send_data.side_effect = synthesize
    first = asyncio.create_task(bridge.on_data(env, completed(1)))
    await entered.wait()
    await bridge.on_data(env, completed(1))
    release.set()
    await first
    env.send_data.side_effect = None
    await bridge.on_data(env, completed(2))
    await bridge.on_data(env, completed(1))
    assert env.send_data.await_count == 2
    assert [
        call.args[0].properties["request_id"]
        for call in env.send_data.await_args_list
    ] == ["fdb-tts-7-1", "fdb-tts-7-2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["session_deleted", "session_failed"])
async def test_other_session_failures_do_not_clear_active_case(
    bridge, env, state
):
    await bridge.on_data(
        env,
        Message(
            "agora_mind_event",
            {
                "event_json": json.dumps(
                    {
                        "type": "workspace.event",
                        "event": {"type": state, "session_id": 99},
                    }
                )
            },
        ),
    )
    assert bridge.session_id == 7
    await bridge.on_data(env, completed(session_id=99))
    env.send_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_deletes_session_and_ignores_late_events(bridge, env):
    await bridge.on_stop(env)
    assert bridge.session_id is None
    command = env.send_cmd.await_args.args[0]
    assert command.name == "delete_session"
    assert command.properties == {"session_id": 7}
    await bridge.on_data(env, completed())
    env.send_data.assert_not_awaited()
    await bridge.on_stop(env)
    env.send_cmd.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_timeout_still_clears_case_state(bridge, env):
    async def pending(_cmd):
        await asyncio.Event().wait()

    env.send_cmd.side_effect = pending
    await bridge.on_stop(env)
    assert bridge.session_id is None
    env.log_warn.assert_called_once()


@pytest.mark.asyncio
async def test_new_workspace_clears_previous_session(bridge, env):
    await bridge.on_cmd(env, Message("create_workspace", {"profile": "fdb"}))
    assert bridge.session_id is None
    await bridge.on_data(env, completed())
    env.send_data.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("transition", ["disconnect", "stop"])
async def test_late_session_creation_cannot_restore_invalidated_state(
    bridge, env, transition
):
    entered, release = asyncio.Event(), asyncio.Event()

    async def create(command):
        result = Result.create(StatusCode.OK, command)
        if command.name == "create_session":
            entered.set()
            await release.wait()
            result.set_property_string(
                "response_json",
                json.dumps({"type": "session.created", "session_id": 8}),
            )
        return result, None

    env.send_cmd.side_effect = create
    pending = asyncio.create_task(
        bridge.on_cmd(env, Message("create_session", {}))
    )
    await entered.wait()
    if transition == "stop":
        await bridge.on_stop(env)
    else:
        await bridge.on_data(
            env,
            Message(
                "agora_mind_event",
                {
                    "event_json": json.dumps(
                        {
                            "type": "extension.connection_state",
                            "state": "disconnected",
                        }
                    )
                },
            ),
        )
    release.set()
    await pending
    assert bridge.session_id is None
    result = env.return_result.await_args.args[0]
    assert result.get_status_code() == StatusCode.ERROR
    assert "changed" in result.properties["response_json"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["rejected", "timeout", "missing_result"])
async def test_input_failure_is_reported_once_with_case_metadata(
    bridge, env, failure
):
    bridge.config.example_id = "case-errors"
    response = json.dumps(
        {
            "type": "error",
            "error": {"type": "invalid_arguments", "detail": "rejected"},
        }
    )
    if failure == "timeout":

        async def pending(_cmd):
            await asyncio.Event().wait()

        env.send_cmd.side_effect = pending
    elif failure == "missing_result":
        env.send_cmd.return_value = None, None
    else:
        result = Result.create(StatusCode.ERROR, Message("submit_user_input"))
        result.set_property_string("response_json", response)
        env.send_cmd.return_value = result, None
    final = Message("asr_result", {"text": "Book the flight", "final": True})
    await bridge.on_data(env, final)
    await bridge.on_data(env, final)
    env.send_cmd.assert_awaited_once()
    env.send_data.assert_awaited_once()
    error = env.send_data.await_args.args[0]
    assert error.name == "error"
    assert error.properties["module"] == "agora_mind_bridge"
    assert error.properties["code"] == 1000
    assert error.properties["metadata"]["session_id"] == "7"
    assert error.properties["metadata"]["example_id"] == "case-errors"
    if failure == "rejected":
        assert error.properties["metadata"]["response_json"] == response


@pytest.mark.asyncio
async def test_old_input_failure_is_ignored_after_session_invalidation(
    bridge, env
):
    entered, release = asyncio.Event(), asyncio.Event()

    async def submit(_cmd):
        entered.set()
        await release.wait()
        return None, RuntimeError("old request failed")

    env.send_cmd.side_effect = submit
    pending = asyncio.create_task(
        bridge.on_data(
            env, Message("asr_result", {"text": "Book", "final": True})
        )
    )
    await entered.wait()
    bridge._reset_session(8)
    release.set()
    await pending
    env.send_data.assert_not_awaited()


def timed_final(start_ms=100, duration_ms=20):
    return Message(
        "asr_result",
        {
            "id": "asr-stream-1",
            "text": "Yes",
            "final": True,
            "start_ms": start_ms,
            "duration_ms": duration_ms,
        },
    )


@pytest.mark.asyncio
async def test_asr_final_replay_after_turn_completion_is_not_resubmitted(
    bridge, env
):
    final = timed_final()
    await bridge.on_data(env, final)
    await bridge.on_data(env, completed())
    replay = timed_final()
    replay.properties["id"] = "new-event-id-for-the-same-audio"
    await bridge.on_data(env, replay)
    env.send_cmd.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_first_turn", [False, True])
async def test_same_text_at_a_new_audio_interval_is_a_new_input(
    bridge, env, finish_first_turn
):
    await bridge.on_data(env, timed_final(start_ms=100))
    if finish_first_turn:
        await bridge.on_data(env, completed())
    await bridge.on_data(env, timed_final(start_ms=200))
    assert env.send_cmd.await_count == 2


@pytest.mark.asyncio
async def test_unknown_audio_interval_does_not_merge_repeated_turns(
    bridge, env
):
    final = timed_final(start_ms=0, duration_ms=0)
    await bridge.on_data(env, final)
    await bridge.on_data(env, completed())
    await bridge.on_data(env, final)
    assert env.send_cmd.await_count == 2
