"""The optional thinking graph shows reasoning without reading it aloud."""

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


ROOT = (
    Path(__file__).resolve().parents[1]
    / "tenapp/ten_packages/extension/main_jev_python"
)
PACKAGE = "main_jev_python_reasoning_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package
agent_package = types.ModuleType(f"{PACKAGE}.agent")
agent_package.__path__ = [str(ROOT / "agent")]
sys.modules[f"{PACKAGE}.agent"] = agent_package

decorators = types.ModuleType(f"{PACKAGE}.agent.decorators")
decorators.agent_event_handler = lambda _event_type: lambda fn: fn
sys.modules[decorators.__name__] = decorators

agent = types.ModuleType(f"{PACKAGE}.agent.agent")
agent.Agent = type("Agent", (), {})
sys.modules[agent.__name__] = agent

events = types.ModuleType(f"{PACKAGE}.agent.events")
for name in (
    "ASRCommitTimeoutEvent",
    "ASRResultEvent",
    "LLMResponseEvent",
    "ModelRouteEvent",
    "ToolRegisterEvent",
    "UserJoinedEvent",
    "UserLeftEvent",
):
    setattr(events, name, type(name, (), {}))
sys.modules[events.__name__] = events

messages = []


async def fake_send_data(_env, _name, _destination, payload):
    messages.append(payload)


helper = types.ModuleType(f"{PACKAGE}.helper")
helper._send_cmd = None
helper._send_data = fake_send_data
helper.parse_sentences = None
sys.modules[helper.__name__] = helper

config = types.ModuleType(f"{PACKAGE}.config")
config.MainControlConfig = type("MainControlConfig", (), {})
sys.modules[config.__name__] = config

runtime = sys.modules.get("ten_runtime") or types.ModuleType("ten_runtime")
runtime.AsyncExtension = type(
    "AsyncExtension", (), {"__init__": lambda self, _name: None}
)
runtime.AsyncTenEnv = type("AsyncTenEnv", (), {})
runtime.Cmd = type("Cmd", (), {})
runtime.Data = type("Data", (), {})
sys.modules["ten_runtime"] = runtime

MainControlExtension = importlib.import_module(
    f"{PACKAGE}.extension"
).MainControlExtension


@pytest.mark.asyncio
async def test_complete_reasoning_is_visible_but_never_sent_to_tts():
    messages.clear()
    extension = MainControlExtension("main_control")
    extension.ten_env = types.SimpleNamespace(log_info=lambda _message: None)
    extension._send_to_tts = AsyncMock()

    await extension._on_llm_response(
        types.SimpleNamespace(
            type="reasoning", delta="first", text="first", is_final=False
        )
    )
    assert messages == []

    await extension._on_llm_response(
        types.SimpleNamespace(
            type="reasoning",
            delta="",
            text="first\nsecond",
            is_final=True,
        )
    )
    await extension._on_llm_response(
        types.SimpleNamespace(
            type="message", delta="", text="Answer", is_final=True
        )
    )

    assert json.loads(messages[0]["text"]) == {
        "type": "reasoning",
        "data": {"text": "first\nsecond"},
    }
    assert messages[0]["is_final"] is True
    assert messages[1]["data_type"] == "transcribe"
    assert messages[1]["text"] == "Answer"
    extension._send_to_tts.assert_awaited_once_with("", True)


@pytest.mark.asyncio
async def test_route_precedes_reasoning_and_answer_without_frontend_changes():
    messages.clear()
    extension = MainControlExtension("main_control")
    extension.ten_env = types.SimpleNamespace(log_info=lambda _message: None)
    extension.config = types.SimpleNamespace(
        model_routing=types.SimpleNamespace(
            deep_dest="llm_deep", min_confidence=0.8
        )
    )
    extension.turn_id = 1
    extension._send_to_tts = AsyncMock()

    await extension._on_model_route(
        types.SimpleNamespace(
            choice="deep",
            confidence=0.91,
            status="selected_deep",
            destination="llm_deep",
            latency_ms=80,
        )
    )
    await extension._on_llm_response(
        types.SimpleNamespace(
            type="reasoning", delta="", text="Think", is_final=True
        )
    )
    await extension._on_llm_response(
        types.SimpleNamespace(
            type="message", delta="", text="Answer", is_final=True
        )
    )

    assert [item["data_type"] for item in messages] == [
        "transcribe",
        "raw",
        "transcribe",
    ]
    assert "Jev route: deep (confidence 0.91)" in messages[0]["text"]
    assert "thinking on" in messages[0]["text"]
    assert json.loads(messages[1]["text"])["type"] == "reasoning"
    assert messages[2]["text"] == "Answer"
    assert len({item["stream_id"] for item in messages}) == 3
    assert [item["text_ts"] for item in messages] == sorted(
        item["text_ts"] for item in messages
    )
    extension._send_to_tts.assert_awaited_once_with("", True)


@pytest.mark.asyncio
async def test_route_fallback_explains_error_and_uses_fast_mode():
    messages.clear()
    extension = MainControlExtension("main_control")
    extension.ten_env = types.SimpleNamespace(log_info=lambda _message: None)
    extension.config = types.SimpleNamespace(
        model_routing=types.SimpleNamespace(
            deep_dest="llm_deep", min_confidence=0.8
        )
    )
    extension.turn_id = 2
    extension._send_to_tts = AsyncMock()

    await extension._on_model_route(
        types.SimpleNamespace(
            choice=None,
            confidence=None,
            status="timeout",
            destination="llm_fast",
            latency_ms=1200,
        )
    )

    assert messages[0]["data_type"] == "transcribe"
    assert "thinking off" in messages[0]["text"]
    assert "timeout fallback" in messages[0]["text"]
    extension._send_to_tts.assert_not_awaited()


def make_asr_event(
    text, *, final, speech_final, session_id="100", start_ms=None
):
    return types.SimpleNamespace(
        text=text,
        final=final,
        start_ms=start_ms,
        metadata={
            "session_id": session_id,
            "asr_info": {"speech_final": speech_final},
        },
    )


def make_asr_extension(mode="speech_final", fallback_ms=1000):
    messages.clear()
    extension = MainControlExtension("main_control")
    extension.ten_env = types.SimpleNamespace(log_info=lambda _message: None)
    extension.config = types.SimpleNamespace(
        turn_detection_mode=mode, asr_final_fallback_ms=fallback_ms
    )
    extension.agent = types.SimpleNamespace(
        queue_llm_input=AsyncMock(), queue_asr_timeout=AsyncMock()
    )

    async def deliver_timeout(session_id, stream_id, generation):
        await extension._on_asr_commit_timeout(
            types.SimpleNamespace(
                session_id=session_id,
                stream_id=stream_id,
                generation=generation,
            )
        )

    extension.agent.queue_asr_timeout.side_effect = deliver_timeout
    extension._interrupt = AsyncMock()
    return extension


@pytest.mark.asyncio
async def test_jev_waits_for_speech_final_and_sends_complete_utterance():
    extension = make_asr_extension()

    await extension._on_asr_result(
        make_asr_event("Hello", final=True, speech_final=False)
    )
    await extension._on_asr_result(
        make_asr_event("world", final=False, speech_final=False)
    )
    extension.agent.queue_llm_input.assert_not_awaited()

    await extension._on_asr_result(
        make_asr_event("world", final=True, speech_final=True)
    )

    extension.agent.queue_llm_input.assert_awaited_once_with("Hello world")
    assert extension.turn_id == 1
    assert [message["text"] for message in messages] == [
        "Hello",
        "Hello world",
        "Hello world",
    ]
    assert [message["is_final"] for message in messages] == [
        False,
        False,
        True,
    ]


@pytest.mark.asyncio
async def test_empty_speech_final_commits_buffered_segments():
    extension = make_asr_extension()
    await extension._on_asr_result(
        make_asr_event("Ready", final=True, speech_final=False)
    )
    await extension._on_asr_result(
        make_asr_event("", final=False, speech_final=True)
    )

    extension.agent.queue_llm_input.assert_awaited_once_with("Ready")
    assert messages[-1]["text"] == "Ready"
    assert messages[-1]["is_final"] is True


@pytest.mark.asyncio
async def test_speech_final_can_commit_current_interim_segment():
    extension = make_asr_extension()
    await extension._on_asr_result(
        make_asr_event("Hello", final=False, speech_final=True)
    )

    extension.agent.queue_llm_input.assert_awaited_once_with("Hello")
    assert messages[-1]["is_final"] is True


@pytest.mark.asyncio
async def test_speech_final_resets_buffer_for_the_next_utterance():
    extension = make_asr_extension()
    await extension._on_asr_result(
        make_asr_event("First", final=True, speech_final=True)
    )
    await extension._on_asr_result(
        make_asr_event("Second", final=True, speech_final=True)
    )

    assert [
        call.args[0] for call in extension.agent.queue_llm_input.await_args_list
    ] == [
        "First",
        "Second",
    ]
    assert extension.turn_id == 2


@pytest.mark.asyncio
async def test_default_mode_keeps_segment_final_behavior():
    extension = make_asr_extension("segment_final")
    await extension._on_asr_result(
        make_asr_event("Hello", final=True, speech_final=False)
    )

    extension.agent.queue_llm_input.assert_awaited_once_with("Hello")
    assert messages[-1]["is_final"] is True


@pytest.mark.asyncio
async def test_missing_speech_final_commits_once_after_last_nonempty_result():
    extension = make_asr_extension(fallback_ms=20)
    committed = asyncio.Event()

    async def record_commit(_text):
        committed.set()

    extension.agent.queue_llm_input.side_effect = record_commit
    await extension._on_asr_result(
        make_asr_event(
            "Okay. Just introduce yourself.",
            final=True,
            speech_final=False,
            start_ms=4430,
        )
    )
    for start_ms in (5000, 5500, 6000):
        await extension._on_asr_result(
            make_asr_event(
                "", final=False, speech_final=False, start_ms=start_ms
            )
        )

    await asyncio.wait_for(committed.wait(), timeout=0.5)
    extension.agent.queue_llm_input.assert_awaited_once_with(
        "Okay. Just introduce yourself."
    )
    assert messages[-1]["is_final"] is True

    # The delayed endpoint and its final duplicate must not make a second turn.
    await extension._on_asr_result(
        make_asr_event("", final=False, speech_final=True, start_ms=7000)
    )
    await extension._on_asr_result(
        make_asr_event(
            "Okay. Just introduce yourself.",
            final=True,
            speech_final=True,
            start_ms=4430,
        )
    )
    assert extension.agent.queue_llm_input.await_count == 1
    assert extension.turn_id == 1

    # Repeating the same words later is a real new turn, not a text duplicate.
    await extension._on_asr_result(
        make_asr_event(
            "Okay. Just introduce yourself.",
            final=True,
            speech_final=True,
            start_ms=20000,
        )
    )
    assert extension.agent.queue_llm_input.await_count == 2


@pytest.mark.asyncio
async def test_stale_deadline_cannot_commit_newer_buffer():
    extension = make_asr_extension()
    await extension._on_asr_result(
        make_asr_event("Hello", final=True, speech_final=False, start_ms=1000)
    )
    old_generation = extension._asr_fallback_generation
    await extension._on_asr_result(
        make_asr_event("world", final=False, speech_final=False, start_ms=1600)
    )
    new_generation = extension._asr_fallback_generation
    assert new_generation > old_generation

    await extension._on_asr_commit_timeout(
        types.SimpleNamespace(
            session_id="100", stream_id=100, generation=old_generation
        )
    )
    extension.agent.queue_llm_input.assert_not_awaited()
    await extension._on_asr_commit_timeout(
        types.SimpleNamespace(
            session_id="100", stream_id=100, generation=new_generation
        )
    )
    extension.agent.queue_llm_input.assert_awaited_once_with("Hello world")


@pytest.mark.asyncio
async def test_session_change_discards_buffer_and_old_timeout():
    extension = make_asr_extension()
    await extension._on_asr_result(
        make_asr_event("Old", final=True, speech_final=False, start_ms=1000)
    )
    old_generation = extension._asr_fallback_generation
    await extension._on_asr_result(
        make_asr_event(
            "New",
            final=True,
            speech_final=False,
            session_id="101",
            start_ms=100,
        )
    )
    await extension._on_asr_commit_timeout(
        types.SimpleNamespace(
            session_id="100", stream_id=100, generation=old_generation
        )
    )
    extension.agent.queue_llm_input.assert_not_awaited()
    await extension._on_asr_result(
        make_asr_event(
            "",
            final=False,
            speech_final=True,
            session_id="101",
            start_ms=200,
        )
    )
    extension.agent.queue_llm_input.assert_awaited_once_with("New")
