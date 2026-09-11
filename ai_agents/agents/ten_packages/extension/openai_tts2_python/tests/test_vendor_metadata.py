from ..config import OpenAITTSConfig
from ..extension import OpenAITTSExtension


def _set_config(ext: OpenAITTSExtension, config: dict) -> None:
    ext.config = OpenAITTSConfig.model_validate(config)
    ext.config.update_params()


def test_vendor_metadata_builds_authorization_from_api_key():
    ext = OpenAITTSExtension("test")
    _set_config(
        ext,
        {
            "url": "https://api.openai.com/v1/audio/speech",
            "params": {
                "api_key": "api-secret",
                "model": "gpt-4o-mini-tts",
                "voice": "coral",
            },
        },
    )

    assert ext.vendor_metadata() == {
        "url": "https://api.openai.com/v1/audio/speech",
        "model": "gpt-4o-mini-tts",
        "api_key": "api-secret",
        "authorization": "",
        "voice": "coral",
    }


def test_vendor_metadata_prefers_authorization_header():
    ext = OpenAITTSExtension("test")
    _set_config(
        ext,
        {
            "headers": {"Authorization": "Bearer header-secret"},
            "params": {"api_key": "api-secret"},
        },
    )

    metadata = ext.vendor_metadata()

    assert "key" not in metadata
    assert metadata["api_key"] == "api-secret"
    assert metadata["authorization"] == "Bearer header-secret"


def test_vendor_metadata_handles_none_api_key():
    ext = OpenAITTSExtension("test")
    _set_config(ext, {"params": {"api_key": None}})

    metadata = ext.vendor_metadata()

    assert "key" not in metadata
    assert metadata["api_key"] == ""
    assert metadata["authorization"] == ""


def test_vendor_metadata_without_config():
    ext = OpenAITTSExtension("test")
    ext.config = None

    assert ext.vendor_metadata() == {}
