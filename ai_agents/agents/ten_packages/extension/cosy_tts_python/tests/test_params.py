import json

from ..config import CosyTTSConfig


BASE_PARAMS = {
    "api_key": "test-key",
    "model": "cosyvoice-v3-flash",
    "sample_rate": 16000,
    "voice": "longanyang",
}


def _config(
    *,
    enable_words: bool = False,
    **overrides,
) -> CosyTTSConfig:
    values = {**BASE_PARAMS, **overrides}
    config = CosyTTSConfig.model_validate(
        {
            "enable_words": enable_words,
            "params": values,
        }
    )
    config.update_params()
    return config


def test_typed_and_constructor_params_are_extracted() -> None:
    config = _config(
        speech_rate=2.0,
        pitch_rate=0.5,
        volume=70,
        seed=7,
        instruction="speak happily",
        language_hints=["zh"],
        enable_markdown_filter=True,
    )

    assert config.speech_rate == 2.0
    assert config.pitch_rate == 0.5
    assert config.volume == 70
    assert config.seed == 7
    assert config.instruction == "speak happily"
    assert config.language_hints == ["zh"]
    assert config.provider_params() == {
        "enable_markdown_filter": True,
        "word_timestamp_enabled": False,
    }


def test_internal_and_unsupported_params_are_not_forwarded() -> None:
    config = _config(
        pool_size=9,
        format="mp3",
        enable_ssml=True,
        headers={"X-Test": "value"},
        base_url="https://ignored.example",
        workspace="workspace-id",
        workspace_id="workspace-id",
    )

    assert config.format == "pcm"
    assert config.headers == {}
    assert config.provider_params() == {"word_timestamp_enabled": False}


def test_enable_words_forces_provider_switch_in_both_directions() -> None:
    enabled = _config(
        enable_words=True,
        word_timestamp_enabled=False,
    )
    disabled = _config(
        enable_words=False,
        word_timestamp_enabled=True,
    )

    assert enabled.provider_params()["word_timestamp_enabled"] is True
    assert disabled.provider_params()["word_timestamp_enabled"] is False


def test_nested_enable_words_is_not_forwarded() -> None:
    config = CosyTTSConfig.model_validate_json(
        json.dumps(
            {
                "enable_words": True,
                "params": {
                    **BASE_PARAMS,
                    "enable_words": False,
                    "word_timestamp_enabled": False,
                },
            }
        )
    )
    config.update_params()

    assert config.provider_params()["word_timestamp_enabled"] is True
    assert "enable_words" not in config.provider_params()


def test_top_level_url_takes_precedence_over_params() -> None:
    config = CosyTTSConfig.model_validate(
        {
            "url": "wss://top-level.example",
            "params": {
                **BASE_PARAMS,
                "url": "wss://nested.example",
            },
        }
    )
    config.update_params()

    assert config.url == "wss://top-level.example"
    assert "url" not in config.provider_params()
