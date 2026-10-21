#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Deterministic checks for the vendor timing hooks.

The hooks build the reference that the live subtitle case compares against
TEN output, so their spacing rules and request bookkeeping are checked here
without a provider connection.
"""

import json
from fractions import Fraction
from types import SimpleNamespace

import pytest

from .timing_hooks.base import ReferenceWord
from .timing_hooks.bytedance import ByteDanceTimingHook
from .timing_hooks.bytedance_duplex import ByteDanceDuplexTimingHook
from .timing_hooks.cartesia import _add_spacing_groups
from .timing_hooks.elevenlabs import ElevenLabsTimingHook
from .timing_hooks.minimax import MiniMaxTimingHook

# The cartesia client's own spacing fixtures (cartesia_tts/tests/test_basic.py)
# plus two-group cases, with the tokens the client emits for the same input.
CARTESIA_SPACING_FIXTURES = [
    ([["is", "your"]], [["is", " ", "your"]]),
    ([[".", "If"]], [[".", " ", "If"]]),
    ([["(", "hello"]], [["(", "hello"]]),
    ([["hello", ","]], [["hello", ","]]),
    ([["你", "好"]], [["你", "好"]]),
    ([["中", "English"]], [["中", "English"]]),
    ([["Hello", "world", "!"]], [["Hello", " ", "world", "!"]]),
    ([["hello"], ["world"]], [["hello"], [" ", "world"]]),
    ([["hello"], [".", "world"]], [["hello"], [" ", ".", " ", "world"]]),
    ([["hello"], [",", "world"]], [["hello"], [" ", ",", " ", "world"]]),
    ([["你"], ["好"]], [["你"], [" ", "好"]]),
]


def _word(text, start_ms=0, end_ms=0):
    return ReferenceWord(text, Fraction(start_ms), Fraction(end_ms))


def _reference_tokens(groups):
    return [
        [word.word for word in group]
        for group in _add_spacing_groups(
            [[_word(text) for text in group] for group in groups]
        )
    ]


@pytest.mark.parametrize(("groups", "expected"), CARTESIA_SPACING_FIXTURES)
def test_cartesia_hook_matches_client_spacing(groups, expected):
    assert _reference_tokens(groups) == expected


def _alignment_payload(request_id, chars, starts, durations):
    return json.dumps(
        {
            "contextId": request_id,
            "alignment": {
                "chars": chars,
                "charStartTimesMs": starts,
                "charDurationsMs": durations,
            },
        }
    )


def test_elevenlabs_reference_preserves_first_word_offsets_per_request():
    hook = ElevenLabsTimingHook()

    for request_id, first_start in (
        ("first", 40),
        ("second", 5),
    ):
        hook.begin_request(request_id)
        hook.observe_receive(
            _alignment_payload(
                request_id,
                ["h", "i"],
                [first_start, first_start + 20],
                [20, 20],
            )
        )
        words = hook.reference(request_id).captions[0]
        assert [word.word for word in words] == ["hi"]
        # Each request keeps its own provider offset; no capture state leaks
        # from the previous request.
        assert words[0].start_ms == first_start
        assert words[0].end_ms == first_start + 40


def test_minimax_reference_keeps_request_relative_word_times():
    hook = MiniMaxTimingHook()
    hook.begin_request("req-minimax")
    hook.observe_send(
        json.dumps(
            {
                "event": "task_start",
                "audio_setting": {
                    "format": "pcm",
                    "sample_rate": 16000,
                    "channels": 1,
                },
            }
        )
    )

    for subtitle in (
        {
            "text": "First ",
            "time_begin": 85,
            "time_end": 320,
            "timestamped_words": [
                {
                    "word": "First",
                    "word_begin": 0,
                    "word_end": 5,
                    "time_begin": 85,
                    "time_end": 200,
                },
                {
                    "word": "First",
                    "word_begin": 0,
                    "word_end": 5,
                    "time_begin": 85,
                    "time_end": 300,
                },
                {
                    "word": "[SPACE]",
                    "word_begin": 5,
                    "word_end": 12,
                    "time_begin": 300,
                    "time_end": 320,
                },
            ],
        },
        {
            "text": "Second",
            "time_begin": 1300,
            "time_end": 1600,
            "timestamped_words": [
                {
                    "word": "Second",
                    "word_begin": 0,
                    "word_end": 6,
                    "time_begin": 1300,
                    "time_end": 1600,
                },
            ],
        },
    ):
        hook.observe_receive(
            json.dumps(
                {
                    "data": {
                        "audio": "00" * 1600,
                        "subtitle": subtitle,
                    },
                }
            )
        )

    reference = hook.reference("req-minimax")
    assert reference.error is None
    assert reference.pcm_bytes == 3200
    first, second = reference.captions
    assert [(word.word, word.start_ms, word.end_ms) for word in first] == [
        ("First", 85, 300),
        (" ", 300, 320),
    ]
    # Word times are request-relative; the segment's time_begin is not added
    # a second time.
    assert [(word.word, word.start_ms, word.end_ms) for word in second] == [
        ("Second", 1300, 1600),
    ]


def _duplex_message(event, payload=None, payload_json=None):
    return SimpleNamespace(event=event, payload=payload, payload_json=payload_json)


def _duplex_hook():
    hook = ByteDanceDuplexTimingHook()
    hook.sample_rate = 16000
    hook.events = {
        "chunk": 352,
        "sentence_start": 350,
        "sentence_end": 351,
    }
    return hook


def test_duplex_reference_follows_sentence_audio_positions():
    hook = _duplex_hook()
    hook.begin_request("req-1")

    hook._capture(_duplex_message(350))
    hook._capture(_duplex_message(352, payload=b"\x00" * 3200))
    hook._capture(
        _duplex_message(
            351,
            payload_json=json.dumps(
                {
                    "words": [
                        {
                            "word": "hi",
                            "startTime": 0.042667,
                            "endTime": 0.062667,
                        },
                        {"word": "there", "startTime": 0.07, "endTime": 0.09},
                    ]
                }
            ),
        )
    )
    hook._capture(_duplex_message(350))
    hook._capture(_duplex_message(352, payload=b"\x00" * 1600))
    hook._capture(
        _duplex_message(
            351,
            payload_json=json.dumps(
                {
                    "words": [
                        {"word": "again", "startTime": 0.11, "endTime": 0.13},
                    ],
                }
            ),
        )
    )

    reference = hook.reference("req-1")
    assert reference.error is None
    assert reference.pcm_bytes == 4800
    first, second = reference.captions
    # Provider times are cumulative for the request, so sentence boundaries do
    # not add another offset.
    assert [word.word for word in first] == ["hi", "there"]
    assert first[0].start_ms == 42
    assert first[1].start_ms == 70
    assert second[0].word == "again"
    assert second[0].start_ms == 110
    assert second[0].end_ms == 130


def test_bytedance_reference_keeps_leading_silence_offset():
    hook = ByteDanceTimingHook()
    hook.sample_rate = 16000
    hook.begin_request("req-1")
    session = SimpleNamespace(original_request_id="req-1", tts_input=SimpleNamespace())

    hook._observe_frontend_msg(
        session,
        json.dumps(
            {
                "frontend": json.dumps(
                    {
                        "words": [
                            {
                                "word": "hello",
                                "start_time": 30,
                                "end_time": 130,
                            },
                            {
                                "word": "world",
                                "start_time": 140,
                                "end_time": 240,
                            },
                        ]
                    }
                )
            }
        ),
    )
    hook._observe_response(
        session,
        (
            SimpleNamespace(frame=b"\x00" * 3200, text_result=object()),
            None,
        ),
    )
    hook._observe_response(
        session, (SimpleNamespace(frame=b"", text_result=None), None)
    )

    reference = hook.reference("req-1")
    assert reference.error is None
    assert reference.pcm_bytes == 3200
    words = reference.captions[0]
    # Provider offsets are kept, and the session's own word space is mirrored.
    assert [word.word for word in words] == ["hello", " world"]
    assert words[0].start_ms == 30
    assert words[0].end_ms == 130
    assert words[1].start_ms == 140
    assert words[1].end_ms == 240
