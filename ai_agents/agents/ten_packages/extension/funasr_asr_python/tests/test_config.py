#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#

import pytest
from funasr_asr_python.config import FunASRConfig


def test_config_default_values():
    """Test default configuration values"""
    config = FunASRConfig()
    assert config.dump is False
    assert config.dump_path == "/tmp"
    assert config.finalize_mode == "disconnect"
    assert config.silence_duration_ms == 1000
    assert config.params == {}


def test_config_from_json():
    """Test configuration from JSON"""
    json_str = """{
        "dump": true,
        "dump_path": "/var/log",
        "finalize_mode": "silence",
        "params": {
            "model": "iic/SenseVoiceSmall",
            "device": "cpu",
            "language": "auto"
        }
    }"""
    config = FunASRConfig.model_validate_json(json_str)
    assert config.dump is True
    assert config.dump_path == "/var/log"
    assert config.finalize_mode == "silence"
    assert config.params["model"] == "iic/SenseVoiceSmall"
    assert config.params["device"] == "cpu"


def test_normalized_language():
    """Language codes map to normalized BCP-47-ish tags."""
    config = FunASRConfig(params={"language": "zh"})
    assert config.normalized_language == "zh-CN"
    config2 = FunASRConfig(params={"language": "auto"})
    assert config2.normalized_language == "auto"
