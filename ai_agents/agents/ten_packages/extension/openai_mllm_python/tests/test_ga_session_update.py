"""Outbound `session.update` must be serialised in the GA nested shape."""

import json

import pytest

from realtime.struct import (
    AudioFormats,
    ResponseCreate,
    ResponseCreateParams,
    InputAudioTranscription,
    SemanticVADUpdateParams,
    ServerVADUpdateParams,
    SessionUpdate,
    SessionUpdateParams,
    to_json,
)


def _session(**kwargs) -> dict:
    su = SessionUpdate(session=SessionUpdateParams(**kwargs))
    return json.loads(to_json(su))


def test_envelope_keeps_session_update_type() -> None:
    payload = _session(model="gpt-realtime-2.1")
    assert payload["type"] == "session.update"
    assert payload["event_id"]


def test_session_is_tagged_realtime() -> None:
    assert _session(model="gpt-realtime-2.1")["session"]["type"] == "realtime"


def test_top_level_fields_stay_flat() -> None:
    session = _session(
        model="gpt-realtime-2.1",
        instructions="be brief",
        tools=[],
        tool_choice="none",
    )["session"]

    assert session["model"] == "gpt-realtime-2.1"
    assert session["instructions"] == "be brief"
    assert session["tools"] == []
    assert session["tool_choice"] == "none"


def test_voice_moves_under_audio_output() -> None:
    session = _session(voice="alloy")["session"]

    assert session["audio"]["output"]["voice"] == "alloy"
    assert "voice" not in session


def test_turn_detection_moves_under_audio_input() -> None:
    session = _session(
        turn_detection=ServerVADUpdateParams(
            threshold=0.5, prefix_padding_ms=300, silence_duration_ms=500
        )
    )["session"]

    turn_detection = session["audio"]["input"]["turn_detection"]
    assert turn_detection["type"] == "server_vad"
    assert turn_detection["threshold"] == 0.5
    assert "turn_detection" not in session


def test_semantic_vad_is_preserved() -> None:
    session = _session(
        turn_detection=SemanticVADUpdateParams(eagerness="high")
    )["session"]

    turn_detection = session["audio"]["input"]["turn_detection"]
    assert turn_detection["type"] == "semantic_vad"
    assert turn_detection["eagerness"] == "high"


def test_transcription_is_renamed_and_nested() -> None:
    session = _session(
        input_audio_transcription=InputAudioTranscription(language="ja")
    )["session"]

    assert session["audio"]["input"]["transcription"]["language"] == "ja"
    assert "input_audio_transcription" not in session


def test_modalities_becomes_output_modalities() -> None:
    session = _session(modalities=["text"])["session"]

    assert session["output_modalities"] == ["text"]
    assert "modalities" not in session


def test_max_tokens_is_renamed() -> None:
    session = _session(max_response_output_tokens=2048)["session"]

    assert session["max_output_tokens"] == 2048
    assert "max_response_output_tokens" not in session


def test_unset_fields_are_omitted() -> None:
    """Omitted fields let the service apply its own defaults."""
    session = _session(model="gpt-realtime-2.1")["session"]

    assert session.keys() == {"type", "model"}


def test_audio_format_is_omitted_when_unset() -> None:
    """The extension relies on the GA default of PCM16 24 kHz mono."""
    session = _session(voice="alloy")["session"]

    assert "format" not in session["audio"]["output"]
    assert "input" not in session["audio"]


@pytest.mark.parametrize(
    "fmt,expected",
    [
        (AudioFormats.PCM16, {"type": "audio/pcm", "rate": 24000}),
        (AudioFormats.G711_ULAW, {"type": "audio/pcmu"}),
        (AudioFormats.G711_ALAW, {"type": "audio/pcma"}),
    ],
)
def test_audio_format_serialises_as_object(fmt, expected) -> None:
    """GA rejects a bare string here despite what the reference documents."""
    session = _session(input_audio_format=fmt, output_audio_format=fmt)[
        "session"
    ]

    assert session["audio"]["input"]["format"] == expected
    assert session["audio"]["output"]["format"] == expected


def test_audio_format_is_never_a_bare_string() -> None:
    session = _session(input_audio_format=AudioFormats.PCM16)["session"]

    assert not isinstance(session["audio"]["input"]["format"], str)


def test_reasoning_effort_is_nested() -> None:
    session = _session(reasoning_effort="low")["session"]

    assert session["reasoning"] == {"effort": "low"}
    assert "reasoning_effort" not in session


def test_reasoning_is_absent_when_unset() -> None:
    session = _session(model="gpt-realtime-2.1")["session"]

    assert "reasoning" not in session


def test_full_payload_matches_ga_shape() -> None:
    su = SessionUpdate(
        session=SessionUpdateParams(
            instructions="be nice",
            model="gpt-realtime-2.1",
            tools=[],
            tool_choice="none",
            turn_detection=SemanticVADUpdateParams(eagerness="auto"),
        )
    )
    su.session.voice = "alloy"
    su.session.input_audio_transcription = InputAudioTranscription(
        language="en"
    )
    su.session.reasoning_effort = "low"

    payload = json.loads(to_json(su))
    payload.pop("event_id")

    # Asserted whole rather than key by key: a per-key denylist passes
    # vacuously for any field the fixture leaves unset, and stays silent about
    # fields added to SessionUpdateParams later.
    assert payload == {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": "gpt-realtime-2.1",
            "instructions": "be nice",
            "tools": [],
            "tool_choice": "none",
            "reasoning": {"effort": "low"},
            "audio": {
                "input": {
                    "turn_detection": {
                        "type": "semantic_vad",
                        "eagerness": "auto",
                        "create_response": True,
                        "interrupt_response": True,
                    },
                    "transcription": {
                        "model": "gpt-4o-transcribe",
                        "prompt": "",
                        "language": "en",
                    },
                },
                "output": {"voice": "alloy"},
            },
        },
    }


def test_bare_response_create_still_serialises() -> None:
    """This is what the extension actually sends."""
    payload = json.loads(to_json(ResponseCreate()))

    assert payload["type"] == "response.create"
    assert "response" not in payload


def test_response_create_overrides_are_rejected() -> None:
    """ResponseCreateParams is still the flat beta struct."""
    with pytest.raises(NotImplementedError, match="not migrated"):
        to_json(ResponseCreate(response=ResponseCreateParams()))


def test_unmapped_field_is_rejected() -> None:
    """GA rejects the whole session.update on an unknown key.

    `temperature` is declared on SessionUpdateParams, OpenAIRealtimeConfig and
    every shipped graph, so passing it through under its beta name would take
    instructions, tools, VAD and voice down with it. Failing here surfaces the
    gap instead.
    """
    with pytest.raises(ValueError, match="temperature"):
        _session(model="gpt-realtime-2.1", temperature=0.9)


def test_empty_reasoning_effort_is_treated_as_unset() -> None:
    """The config uses "" to mean "leave it to the model"."""
    session = _session(model="gpt-realtime-2.1", reasoning_effort="")["session"]

    assert "reasoning" not in session


def test_modalities_string_is_rejected() -> None:
    """A bare string would iterate into characters."""
    with pytest.raises(ValueError, match="sequence"):
        _session(modalities="audio")


def test_modalities_order_is_preserved() -> None:
    assert _session(modalities=["audio", "text"])["session"][
        "output_modalities"
    ] == ["audio", "text"]


def test_unknown_audio_format_is_rejected() -> None:
    with pytest.raises(ValueError, match="_GA_AUDIO_FORMATS"):
        _session(input_audio_format="pcm24")


def test_audio_format_result_is_not_shared_state() -> None:
    """Callers must not be able to mutate the module-level format table."""
    first = _session(input_audio_format=AudioFormats.PCM16)["session"]
    first["audio"]["input"]["format"]["rate"] = 48000

    second = _session(input_audio_format=AudioFormats.PCM16)["session"]

    assert second["audio"]["input"]["format"]["rate"] == 24000
