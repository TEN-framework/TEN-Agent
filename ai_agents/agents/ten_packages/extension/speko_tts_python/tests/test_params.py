import sys
from pathlib import Path

# Add project root to sys.path to allow running tests from this directory
# The project root is 6 levels up from the parent directory of this file.
project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json
from unittest.mock import MagicMock

import pytest

from ten_packages.extension.speko_tts_python.config import (
    SpekoTTSConfig,
    SPEKO_OUTPUT_SAMPLE_RATE,
)
from ten_packages.extension.speko_tts_python.speko_tts import SpekoTTSClient


def _make_config(params: dict) -> SpekoTTSConfig:
    config = SpekoTTSConfig.model_validate_json(json.dumps({"params": params}))
    config.update_params()
    return config


def test_defaults_and_normalization():
    config = _make_config({"api_key": "k"})
    assert config.params["base_url"] == "https://api.speko.ai"
    assert config.params["model"] == "auto"

    config = _make_config(
        {
            "api_key": "k",
            "base_url": "https://staging.example.com/",
            # These are router-edge constants and must be stripped.
            "response_format": "wav",
            "sample_rate": 16000,
        }
    )
    assert config.params["base_url"] == "https://staging.example.com"
    assert "response_format" not in config.params
    assert "sample_rate" not in config.params


def test_output_sample_rate_is_fixed():
    assert SPEKO_OUTPUT_SAMPLE_RATE == 24000


def test_validate_requires_api_key():
    config = _make_config({})
    with pytest.raises(ValueError):
        config.validate()


def test_validate_rejects_unknown_objective():
    config = _make_config({"api_key": "k", "objective": "cheapest"})
    with pytest.raises(ValueError):
        config.validate()


def test_payload_and_headers():
    config = _make_config(
        {
            "api_key": "fake_test_key",
            "model": "auto",
            "voice": "voice-123",
            "language": "es-PR",
            "speed": 1.2,
            "objective": "latency",
            "deny": "someprovider",
        }
    )
    client = SpekoTTSClient(config=config, ten_env=MagicMock())

    # Routing preferences travel as headers; empties are omitted.
    assert client.headers["Authorization"] == "Bearer fake_test_key"
    assert client.headers["X-Speko-Objective"] == "latency"
    assert client.headers["X-Speko-Deny"] == "someprovider"
    assert "X-Speko-Allow" not in client.headers
    assert "X-Speko-Max-Price" not in client.headers

    payload = client._build_payload("hola")
    assert payload["input"] == "hola"
    assert payload["response_format"] == "pcm"
    assert payload["model"] == "auto"
    assert payload["voice"] == "voice-123"
    assert payload["language"] == "es-PR"
    assert payload["speed"] == 1.2
    # Secrets and client-side knobs never reach the wire.
    for forbidden in ("api_key", "base_url", "objective", "deny"):
        assert forbidden not in payload

    assert client.endpoint == "https://api.speko.ai/v1/audio/speech/stream"
