from ..openai_asr_client.schemas import (
    TranscriptionParam,
    _to_plain_dict,
    build_ga_session_update,
)


def test_pcm16_maps_to_audio_pcm_24k():
    payload = build_ga_session_update(
        TranscriptionParam(
            input_audio_format="pcm16",
            input_audio_transcription={
                "model": "whisper-1",
                "language": "en",
            },
        )
    )
    assert payload["type"] == "session.update"
    assert payload["session"]["type"] == "transcription"
    assert payload["session"]["audio"]["input"]["format"] == {
        "type": "audio/pcm",
        "rate": 24000,
    }


def test_optional_fields_omitted_when_unset():
    payload = build_ga_session_update(
        TranscriptionParam(
            input_audio_format="pcm16",
            input_audio_transcription={"model": "whisper-1"},
        )
    )
    audio_input = payload["session"]["audio"]["input"]
    assert "turn_detection" not in audio_input
    assert "noise_reduction" not in audio_input
    assert "include" not in payload["session"]


def test_g711_ulaw_mapping():
    payload = build_ga_session_update(
        TranscriptionParam(
            input_audio_format="g711_ulaw",
            input_audio_transcription={"model": "whisper-1"},
        )
    )
    assert payload["session"]["audio"]["input"]["format"] == {
        "type": "audio/pcmu",
    }


def test_g711_alaw_mapping():
    payload = build_ga_session_update(
        TranscriptionParam(
            input_audio_format="g711_alaw",
            input_audio_transcription={"model": "whisper-1"},
        )
    )
    assert payload["session"]["audio"]["input"]["format"] == {
        "type": "audio/pcma",
    }


def test_null_fields_stripped_from_plain_dict():
    assert _to_plain_dict({"model": "whisper-1", "prompt": None}) == {
        "model": "whisper-1"
    }


def test_turn_detection_and_noise_reduction_included_when_set():
    payload = build_ga_session_update(
        TranscriptionParam(
            input_audio_format="pcm16",
            input_audio_transcription={"model": "whisper-1"},
            turn_detection={"type": "server_vad", "threshold": 0.5},
            input_audio_noise_reduction={"type": "near_field"},
            include=["item.input_audio_transcription.logprobs"],
        )
    )
    audio_input = payload["session"]["audio"]["input"]
    assert audio_input["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.5,
    }
    assert audio_input["noise_reduction"] == {"type": "near_field"}
    assert payload["session"]["include"] == [
        "item.input_audio_transcription.logprobs"
    ]


def test_format_dict_is_not_shared_with_module_constant():
    payload = build_ga_session_update(
        TranscriptionParam(
            input_audio_format="pcm16",
            input_audio_transcription={"model": "whisper-1"},
        )
    )
    fmt = payload["session"]["audio"]["input"]["format"]
    fmt["rate"] = 48000
    payload2 = build_ga_session_update(
        TranscriptionParam(
            input_audio_format="pcm16",
            input_audio_transcription={"model": "whisper-1"},
        )
    )
    assert payload2["session"]["audio"]["input"]["format"]["rate"] == 24000
