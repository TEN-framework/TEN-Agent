"""Inbound GA server event names must parse to the expected message types.

GA renamed the response output events. If these regress to the beta spellings
the extension silently stops producing audio and transcripts, because
`parse_server_message` raises and the dispatch in `extension.py` never runs.
"""

import json

import pytest

from realtime.struct import (
    EventType,
    ResponseAudioDelta,
    ResponseAudioDone,
    ResponseAudioTranscriptDelta,
    ResponseAudioTranscriptDone,
    ResponseTextDelta,
    ResponseTextDone,
    parse_server_message,
)

BETA_EVENT_NAMES = {
    "response.audio.delta",
    "response.audio.done",
    "response.audio_transcript.delta",
    "response.audio_transcript.done",
    "response.text.delta",
    "response.text.done",
}


@pytest.mark.parametrize(
    "event_type,expected",
    [
        ("response.output_audio.delta", EventType.RESPONSE_AUDIO_DELTA),
        ("response.output_audio.done", EventType.RESPONSE_AUDIO_DONE),
        (
            "response.output_audio_transcript.delta",
            EventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA,
        ),
        (
            "response.output_audio_transcript.done",
            EventType.RESPONSE_AUDIO_TRANSCRIPT_DONE,
        ),
        ("response.output_text.delta", EventType.RESPONSE_TEXT_DELTA),
        ("response.output_text.done", EventType.RESPONSE_TEXT_DONE),
    ],
)
def test_event_enum_uses_ga_names(event_type: str, expected: EventType) -> None:
    assert expected.value == event_type


def test_no_beta_event_names_remain() -> None:
    values = {member.value for member in EventType}
    assert not (values & BETA_EVENT_NAMES)


def _envelope(event_type: str, **extra) -> str:
    payload = {
        "event_id": "evt_1",
        "type": event_type,
        "response_id": "resp_1",
        "item_id": "item_1",
        "output_index": 0,
        "content_index": 0,
    }
    payload.update(extra)
    return json.dumps(payload)


def test_parses_ga_audio_delta() -> None:
    msg = parse_server_message(
        _envelope("response.output_audio.delta", delta="AAAA")
    )
    assert isinstance(msg, ResponseAudioDelta)
    assert msg.delta == "AAAA"


def test_parses_ga_audio_done() -> None:
    msg = parse_server_message(_envelope("response.output_audio.done"))
    assert isinstance(msg, ResponseAudioDone)


def test_parses_ga_audio_transcript_delta() -> None:
    msg = parse_server_message(
        _envelope("response.output_audio_transcript.delta", delta="hel")
    )
    assert isinstance(msg, ResponseAudioTranscriptDelta)
    assert msg.delta == "hel"


def test_parses_ga_audio_transcript_done() -> None:
    msg = parse_server_message(
        _envelope("response.output_audio_transcript.done", transcript="hello")
    )
    assert isinstance(msg, ResponseAudioTranscriptDone)
    assert msg.transcript == "hello"


def test_parses_ga_text_delta() -> None:
    msg = parse_server_message(
        _envelope("response.output_text.delta", delta="hi")
    )
    assert isinstance(msg, ResponseTextDelta)
    assert msg.delta == "hi"


def test_parses_ga_text_done() -> None:
    msg = parse_server_message(
        _envelope("response.output_text.done", text="hi there")
    )
    assert isinstance(msg, ResponseTextDone)
    assert msg.text == "hi there"


@pytest.mark.parametrize("beta_name", sorted(BETA_EVENT_NAMES))
def test_beta_event_names_are_rejected(beta_name: str) -> None:
    """A beta payload must fail loudly rather than be silently mishandled."""
    with pytest.raises(ValueError):
        parse_server_message(_envelope(beta_name, delta=""))
