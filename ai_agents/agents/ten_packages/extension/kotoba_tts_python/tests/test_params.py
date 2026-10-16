#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Configuration mapping tests; no TEN runtime needed."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DEFAULT_BASE_URL, KotobaTTSConfig  # noqa: E402


def _config(params: dict, **top) -> KotobaTTSConfig:
    config = KotobaTTSConfig(params=params, **top)
    config.update_params()
    return config


def test_defaults_apply_when_only_key_given():
    config = _config({"key": "k"})
    config.validate_config()
    assert config.base_url == DEFAULT_BASE_URL
    assert config.language == "ja"
    assert config.speaker_id == "male-01"
    assert config.sample_rate == 16000
    assert config.request_timeout_seconds == 30.0
    assert config.ignored_params() == []


def test_api_key_alias_and_overrides():
    config = _config(
        {
            "api_key": "alias",
            "base_url": "wss://example.test/v2/tts/ws",
            "language": "ja",
            "speaker_id": "female-01",
            "sample_rate": "24000",
            "request_timeout_seconds": 5,
            "segment_soft_limit_chars": 40,
            "voice_settings": {"x": 1},
        }
    )
    config.validate_config()
    assert config.key == "alias"
    assert config.base_url == "wss://example.test/v2/tts/ws"
    assert config.speaker_id == "female-01"
    assert config.sample_rate == 24000
    assert config.request_timeout_seconds == 5.0
    assert config.segment_soft_limit_chars == 40
    assert config.ignored_params() == ["voice_settings"]


def test_key_wins_over_api_key():
    assert _config({"key": "a", "api_key": "b"}).key == "a"


@pytest.mark.parametrize(
    ("params", "message"),
    [
        pytest.param({"key": ""}, "params.key", id="missing-key"),
        pytest.param(
            {"key": "k", "sample_rate": 44100},
            "params.sample_rate",
            id="unsupported-sample-rate",
        ),
        pytest.param(
            {"key": "k", "base_url": "https://fal.run/x"},
            "params.base_url",
            id="http-url",
        ),
        pytest.param(
            {"key": "k", "request_timeout_seconds": 0},
            "request_timeout_seconds",
            id="zero-timeout",
        ),
        pytest.param(
            {"key": "k", "language": "   "},
            "params.language",
            id="blank-language-keeps-default",
            marks=pytest.mark.xfail(
                reason="blank values fall back to the default", strict=True
            ),
        ),
    ],
)
def test_validate_rejects(params, message):
    config = _config(params)
    with pytest.raises(ValueError, match=message):
        config.validate_config()


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"key": "k", "sample_rate": True}, id="bool-as-int"),
        pytest.param({"key": "k", "sample_rate": "16k"}, id="non-numeric"),
        pytest.param(
            {"key": "k", "request_timeout_seconds": float("nan")},
            id="nan-timeout",
        ),
        pytest.param(
            {"key": "k", "request_timeout_seconds": "fast"},
            id="text-timeout",
        ),
    ],
)
def test_update_params_rejects_bad_types(params):
    with pytest.raises(ValueError):
        _config(params)


def test_to_str_masks_key():
    config = _config({"key": "secret-key-value"})
    text = config.to_str(sensitive_handling=True)
    assert "secret-key-value" not in text
    assert "secret-key-value" in config.to_str(sensitive_handling=False)


def test_to_str_redacts_unknown_param_values_and_url_credentials():
    config = _config(
        {
            "key": "k-secret",
            "token": "tok-secret",
            "custom_note": "plain-value",
            "base_url": "wss://user:pw-secret@example.test/ws?sign=sig-secret",
        }
    )
    text = config.to_str(sensitive_handling=True)
    for secret in (
        "k-secret",
        "tok-secret",
        "plain-value",
        "pw-secret",
        "sig-secret",
    ):
        assert secret not in text, secret
    assert "example.test" in text
    assert config.ignored_params() == ["custom_note", "token"]


def test_redacted_base_url_masks_userinfo_and_signed_query():
    config = _config(
        {
            "key": "k",
            "base_url": "wss://user:pw-secret@example.test/ws?sign=sig-secret&x=1",
        }
    )
    url = config.redacted_base_url()
    assert "pw-secret" not in url and "sig-secret" not in url
    assert url.startswith("wss://***@example.test/ws?")
