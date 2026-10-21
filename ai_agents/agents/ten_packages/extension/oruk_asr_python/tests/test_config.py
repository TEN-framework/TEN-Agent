import pytest

from ..config import OrukASRConfig
from ..extension import OrukASRExtension


def test_valid_config_defaults():
    cfg = OrukASRConfig.model_validate(
        {
            "params": {
                "language": "auto",
                "sample_rate": 16000,
                "result_language_default": "en-US",
            }
        }
    )
    cfg.validate_config()
    assert cfg.sample_rate == 16000
    assert cfg.asr_result_language == "en-US"


def test_rejects_non_16k():
    cfg = OrukASRConfig.model_validate({"params": {"sample_rate": 8000}})
    with pytest.raises(ValueError):
        cfg.validate_config()


def test_rejects_other_model():
    cfg = OrukASRConfig.model_validate({"params": {"model": "whisper"}})
    with pytest.raises(ValueError):
        cfg.validate_config()


def test_rejects_fixed_language():
    cfg = OrukASRConfig.model_validate({"params": {"language": "fr"}})
    with pytest.raises(ValueError):
        cfg.validate_config()


def test_vendor_metadata_is_model_only():
    ext = OrukASRExtension("test")
    assert ext.vendor_metadata() == {}
    ext.config = OrukASRConfig.model_validate({})
    assert ext.vendor_metadata() == {"model": "orukeet"}


def test_unknown_result_language_uses_undetermined_tag():
    assert OrukASRConfig.model_validate({}).asr_result_language == "und"
