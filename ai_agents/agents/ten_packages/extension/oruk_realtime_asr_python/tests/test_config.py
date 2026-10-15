import json

import pytest

from ..config import OrukRealtimeASRConfig
from ..const import MODEL
from ..extension import OrukRealtimeASRExtension


def test_requires_api_key():
    cfg = OrukRealtimeASRConfig.model_validate({"params": {"key": ""}})
    with pytest.raises(ValueError):
        cfg.validate_config()


def test_rejects_whitespace_key():
    cfg = OrukRealtimeASRConfig.model_validate({"params": {"key": "a b"}})
    with pytest.raises(ValueError):
        cfg.validate_config()


def test_default_url_and_language():
    cfg = OrukRealtimeASRConfig.model_validate({"params": {"key": "secret"}})
    cfg.validate_config()
    assert cfg.url.startswith("wss://")
    assert cfg.language == "auto"
    assert cfg.asr_result_language == "und"


def test_to_json_masks_key():
    cfg = OrukRealtimeASRConfig.model_validate(
        {"params": {"key": "supersecretkey"}}
    )
    rendered = cfg.to_json(sensitive_handling=True)
    data = json.loads(rendered)
    assert data["params"]["key"] != "supersecretkey"
    assert "supersecretkey" not in rendered


def test_vendor_metadata_excludes_when_no_config():
    ext = OrukRealtimeASRExtension("test")
    ext.config = None
    assert ext.vendor_metadata() == {}


def test_vendor_metadata_includes_model_and_key():
    ext = OrukRealtimeASRExtension("test")
    ext.config = OrukRealtimeASRConfig.model_validate(
        {"params": {"key": "secret"}}
    )
    md = ext.vendor_metadata()
    assert md["model"] == MODEL
    assert md["key"] == "secret"
