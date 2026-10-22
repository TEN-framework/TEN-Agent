import pytest

from ..config import CosyTTSConfig


def _valid_config(**overrides) -> CosyTTSConfig:
    values = {
        "api_key": "test-key",
        "model": "cosyvoice-v3-flash",
        "sample_rate": 16000,
        "voice": "longanyang",
        **overrides,
    }
    config = CosyTTSConfig.model_validate({"params": values})
    config.update_params()
    return config


@pytest.mark.parametrize("field", ["api_key", "model", "voice"])
def test_missing_required_field_is_rejected(field: str) -> None:
    config = _valid_config(**{field: " "})

    with pytest.raises(ValueError, match=field):
        config.validate_params()


def test_invalid_sample_rate_is_rejected() -> None:
    config = _valid_config(sample_rate=12345)

    with pytest.raises(ValueError, match="sample_rate"):
        config.validate_params()


def test_config_string_redacts_credentials_and_headers() -> None:
    config = _valid_config(
        headers={"Authorization": "Bearer secret-header"},
        token="secret-token",
    )

    rendered = config.to_str(sensitive_handling=True)

    assert "test-key" not in rendered
    assert "secret-token" not in rendered
    assert "secret-header" not in rendered
