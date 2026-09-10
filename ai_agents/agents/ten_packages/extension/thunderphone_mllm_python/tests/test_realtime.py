#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Protocol and configuration tests; no credentials or network needed."""

import json

import pytest

from thunderphone_mllm_python.config import (
    ThunderPhoneRealtimeConfig,
    inline_session_update,
)
from thunderphone_mllm_python.realtime.connection import build_url
from thunderphone_mllm_python.realtime.struct import (
    CallEvent,
    ItemCreated,
    ResponseAudioDelta,
    ResponseAudioTranscriptDone,
    SessionCreated,
    UnknownMessage,
    parse_server_message,
    to_json,
)


class _Param:
    def __init__(self, name, type_, description, required):
        self.name, self.type, self.description, self.required = (
            name,
            type_,
            description,
            required,
        )


class _Tool:
    name = "check_availability"
    description = "Free appointment slots on a date"
    parameters = [_Param("date", "string", "ISO date", True)]


def test_saved_agent_config_builds_call_events_query():
    config = ThunderPhoneRealtimeConfig(
        api_key="sk_live_x", agent_id=12, from_number="+15550001"
    )
    config.validate_for_start()
    assert config.saved_agent
    assert config.query() == {
        "agent_id": "12",
        "from_number": "+15550001",
        "input_audio_format": "pcm16",
        "input_rate": "24000",
        "output_audio_format": "pcm16",
        "output_rate": "24000",
        "call_events": "1",
    }


def test_inline_config_requires_prompt_and_secret_key():
    with pytest.raises(ValueError, match="sk_live_"):
        ThunderPhoneRealtimeConfig(api_key="sk-openai", prompt="x").validate_for_start()
    with pytest.raises(ValueError, match="prompt"):
        ThunderPhoneRealtimeConfig(api_key="sk_live_x").validate_for_start()
    with pytest.raises(ValueError, match="sample_rate"):
        ThunderPhoneRealtimeConfig(
            api_key="sk_live_x", prompt="x", sample_rate=8000
        ).validate_for_start()
    config = ThunderPhoneRealtimeConfig(
        api_key="sk_live_x", prompt="x", product="bolt", language="es", sample_rate=16000
    )
    config.validate_for_start()
    query = config.query()
    assert query["product"] == "bolt" and query["language"] == "es"
    assert query["input_rate"] == query["output_rate"] == "16000"
    assert "agent_id" not in query


def test_build_url_merges_query_into_path():
    assert (
        build_url("wss://api.thunderphone.com/", "/v1/realtime", {"agent_id": "1"})
        == "wss://api.thunderphone.com/v1/realtime?agent_id=1"
    )
    assert (
        build_url("ws://localhost:8002", "/v1/realtime?debug=1", {"a": "b"})
        == "ws://localhost:8002/v1/realtime?debug=1&a=b"
    )


def test_inline_session_update_carries_everything_that_starts_the_call():
    config = ThunderPhoneRealtimeConfig(
        api_key="sk_live_x", prompt="Be brief.", voice="olivia", live_transcripts=True
    )
    update = json.loads(to_json(inline_session_update(config, [_Tool()])))
    session = update["session"]
    assert update["type"] == "session.update"
    assert session["instructions"] == "Be brief."
    assert session["voice"] == "olivia"
    assert session["config"] == {"call_events": True}
    assert session["live_transcripts"] is True
    assert session["tool_choice"] == "auto"
    assert session["tools"] == [
        {
            "type": "function",
            "name": "check_availability",
            "description": "Free appointment slots on a date",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string", "description": "ISO date"}},
                "required": ["date"],
                "additionalProperties": False,
            },
        }
    ]
    # Absent keys are omitted rather than sent as null.
    assert "model" not in session and "turn_detection" not in session

    bare = json.loads(to_json(inline_session_update(config, [])))["session"]
    assert "tools" not in bare and "tool_choice" not in bare


def test_thunderphone_session_created_parses():
    frame = {
        "event_id": "evt_1",
        "type": "session.created",
        "session": {
            "id": "sess_1",
            "object": "realtime.session",
            "model": "thunderphone-realtime",
            "call_id": "987",
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": 24000}}},
            "voice": "olivia",
            "turn_detection": {"type": "server_vad"},
        },
    }
    message = parse_server_message(json.dumps(frame))
    assert isinstance(message, SessionCreated)
    assert message.session.id == "sess_1"
    assert message.session.call_id == "987"
    assert message.session.voice == "olivia"


def test_call_events_and_ga_item_events_parse():
    ended = parse_server_message(
        json.dumps({"event_id": "e", "type": "call.ended", "reason": "agent_hangup"})
    )
    assert isinstance(ended, CallEvent)
    assert ended.type == "call.ended" and ended.reason == "agent_hangup"

    added = parse_server_message(
        json.dumps(
            {
                "event_id": "e",
                "type": "conversation.item.added",
                "previous_item_id": None,
                "item": {"id": "item_1", "type": "message", "role": "user", "content": []},
            }
        )
    )
    assert isinstance(added, ItemCreated)
    assert added.item["id"] == "item_1"

    unknown = parse_server_message(
        json.dumps({"event_id": "e", "type": "output_audio_buffer.started"})
    )
    assert isinstance(unknown, UnknownMessage)
    assert unknown.type == "output_audio_buffer.started"


def test_ga_response_event_names_parse():
    audio = parse_server_message(
        json.dumps(
            {
                "event_id": "e",
                "type": "response.output_audio.delta",
                "response_id": "resp_1",
                "item_id": "item_1",
                "output_index": 0,
                "content_index": 0,
                "delta": "AAAA",
            }
        )
    )
    assert isinstance(audio, ResponseAudioDelta) and audio.delta == "AAAA"
    transcript = parse_server_message(
        json.dumps(
            {
                "event_id": "e",
                "type": "response.output_audio_transcript.done",
                "response_id": "resp_1",
                "item_id": "item_1",
                "output_index": 0,
                "content_index": 0,
                "transcript": "Hello.",
            }
        )
    )
    assert isinstance(transcript, ResponseAudioTranscriptDone)
    assert transcript.transcript == "Hello."
