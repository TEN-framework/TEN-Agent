from ..config import TencentASRConfig
from ..extension import TencentASRExtension


def test_vendor_metadata_from_config():
    ext = TencentASRExtension("test")
    ext.config = TencentASRConfig.model_validate(
        {
            "params": {
                "appid": "1250000000",
                "secretid": "secret-id",
                "secretkey": "secret-key",
                "engine_model_type": "16k_en",
            }
        }
    )
    ext.request_params = ext.config.params.to_request_params()

    metadata = ext.vendor_metadata()

    assert metadata["appid"] == "1250000000"
    assert metadata["key"] == "secret-id"
    assert metadata["model"] == "16k_en"
    assert metadata["url"] == "wss://asr.cloud.tencent.com/asr/v2"
    assert "?" not in metadata["url"]
    assert "region" not in metadata
    assert "mode" not in metadata


def test_vendor_metadata_without_config():
    ext = TencentASRExtension("test")
    ext.config = None
    ext.request_params = None

    assert ext.vendor_metadata() == {}
