import pytest

from stepfun_asr_python.config import StepFunASRConfig


def valid_config() -> dict:
    return {
        "params": {
            "api_key": "test-key",
            "url": "wss://api.stepfun.com/v1/realtime/asr/stream",
            "model": "stepaudio-2.5-asr-stream",
            "language": "en",
            "sample_rate": 16000,
            "bits": 16,
            "channels": 1,
        }
    }


def test_config_accepts_stepfun_defaults():
    config = StepFunASRConfig.model_validate(valid_config())
    config.validate_config()

    assert config.model == "stepaudio-2.5-asr-stream"
    assert config.sample_rate == 16000
    assert config.channels == 1


def test_config_reconnect_unlimited_by_default():
    config = StepFunASRConfig.model_validate(valid_config())
    assert config.reconnect_max_attempts == 0


def test_config_redacts_api_key():
    config = StepFunASRConfig.model_validate(valid_config())

    assert "test-key" not in config.to_str(sensitive_handling=True)


def test_config_prompt_optional_and_trimmed():
    config = StepFunASRConfig.model_validate(valid_config())
    assert config.prompt is None

    config.update({"prompt": "  术语A  "})
    assert config.prompt == "术语A"

    config.update({"prompt": "   "})
    assert config.prompt is None


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("zh-CN", "zh"),
        ("zh", "zh"),
        ("en-US", "en"),
        ("en", "en"),
        ("ja-JP", "ja"),
        ("KO-kr", "ko"),
        ("zh-Hans-CN", "zh"),
    ],
)
def test_config_maps_language_into_params(configured: str, expected: str):
    config = StepFunASRConfig.model_validate(
        {
            "params": {
                **valid_config()["params"],
                "language": configured,
            }
        }
    )
    assert config.params["language"] == expected
    assert config.language == expected


def test_config_root_language_maps_when_params_language_missing():
    base_params = {
        k: v for k, v in valid_config()["params"].items() if k != "language"
    }
    config = StepFunASRConfig.model_validate(
        {"language": "zh-CN", "params": base_params}
    )
    assert config.params["language"] == "zh"


def test_config_params_language_overrides_root_language():
    config = StepFunASRConfig.model_validate(
        {
            "language": "zh-CN",
            "params": {
                **valid_config()["params"],
                "language": "en-US",
            },
        }
    )
    assert config.params["language"] == "en"


@pytest.mark.parametrize(
    "change",
    [
        {"params": {"api_key": ""}},
        {"params": {"sample_rate": 24000}},
        {"params": {"url": "https://api.stepfun.com/v1/realtime/asr/stream"}},
    ],
)
def test_config_rejects_invalid_values(change):
    raw = valid_config()
    raw["params"].update(change["params"])
    config = StepFunASRConfig.model_validate(raw)

    with pytest.raises(ValueError):
        config.validate_config()
