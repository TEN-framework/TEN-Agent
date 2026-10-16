"""
Fast unit tests for GradiumMLLMConfig -- no TEN runtime needed.

Guards the specific protocol details Gradium confirmed on 2026-08-20,
especially the json_config nesting that was wrong in the initial scaffold
(target_language was sent top-level; Gradium's real protocol nests it
inside json_config).
"""

from gradium_mllm_python.config import GradiumMLLMConfig


def test_setup_message_nests_target_language_in_json_config():
    config = GradiumMLLMConfig(
        api_key="test_key",
        model_name="s2s-translate",
        stt_model_name="stt-translate",
        tts_model_name="default",
        voice_id="some-voice",
        target_language="fr",
        input_format="pcm",
        output_format="pcm",
    )
    setup = config.setup_message()

    assert setup["type"] == "setup"
    assert setup["model_name"] == "s2s-translate"
    assert setup["stt_model_name"] == "stt-translate"
    assert setup["tts_model_name"] == "default"
    assert setup["voice_id"] == "some-voice"
    assert setup["input_format"] == "pcm"
    assert setup["output_format"] == "pcm"

    # target_language must NOT be a top-level field.
    assert "target_language" not in setup
    assert setup["json_config"] == {"target_language": "fr"}


def test_setup_message_defaults_match_gradium_confirmed_values():
    setup = GradiumMLLMConfig(api_key="test_key").setup_message()

    assert setup["model_name"] == "s2s-translate"
    assert setup["stt_model_name"] == "stt-translate"
    assert setup["tts_model_name"] == "default"
    assert setup["json_config"] == {"target_language": "en"}


def test_websocket_url_uses_region_by_default():
    config = GradiumMLLMConfig(region="eu", path="/api/speech/s2s")
    assert config.websocket_url() == "wss://eu.api.gradium.ai/api/speech/s2s"


def test_websocket_url_prefers_explicit_base_url_override():
    config = GradiumMLLMConfig(
        region="us",
        base_url="wss://override.example.com",
        path="/api/speech/s2s",
    )
    assert (
        config.websocket_url() == "wss://override.example.com/api/speech/s2s"
    )


def test_output_sample_rate_defaults_to_48k_for_bare_pcm():
    assert GradiumMLLMConfig(output_format="pcm").output_sample_rate() == 48000


def test_output_sample_rate_honors_explicit_rate_formats():
    assert (
        GradiumMLLMConfig(output_format="pcm_16000").output_sample_rate()
        == 16000
    )
    assert (
        GradiumMLLMConfig(output_format="pcm_24000").output_sample_rate()
        == 24000
    )
