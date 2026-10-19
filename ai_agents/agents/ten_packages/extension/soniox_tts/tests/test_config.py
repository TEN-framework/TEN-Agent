import pytest

from soniox_tts.config import SonioxTTSConfig


def test_update_params_and_redact_api_key():
    config = SonioxTTSConfig(
        params={
            "api_key": "soniox-secret-value",
            "model": "tts-rt-v2",
            "language": "de",
            "voice": "Mila",
            "sample_rate": 16000,
        }
    )
    config.update_params()
    config.validate_params()

    assert config.api_key == "soniox-secret-value"
    assert config.language == "de"
    assert config.sample_rate == 16000
    assert "soniox-secret-value" not in config.to_str()
    assert "api_key" not in config.params


@pytest.mark.parametrize("sample_rate", [8000, 16000, 24000, 44100, 48000])
def test_supported_sample_rates(sample_rate):
    config = SonioxTTSConfig(api_key="key", sample_rate=sample_rate)
    config.validate_params()


def test_invalid_audio_format_is_rejected():
    config = SonioxTTSConfig(api_key="key", audio_format="wav")
    with pytest.raises(ValueError, match="audio_format"):
        config.validate_params()


def test_invalid_speed_is_rejected():
    config = SonioxTTSConfig(api_key="key", speed=1.4)
    with pytest.raises(ValueError, match="speed"):
        config.validate_params()
