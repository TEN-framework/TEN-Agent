import sys
from pathlib import Path

# Add project root to sys.path to allow running tests from this directory
# The project root is 6 levels up from the parent directory of this file.
project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

#
# Copyright © 2024 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
from unittest.mock import patch, MagicMock, AsyncMock


# ================ test config defaults ================
def test_update_params_defaults():
    """update_params() sets the Smallest defaults and forces output_format=pcm."""
    from smallest_tts_python.config import SmallestTTSConfig

    config = SmallestTTSConfig(params={"api_key": "test_key"})
    config.update_params()

    assert config.params["model"] == "lightning_v3.1"
    # Always raw PCM16 `pcm` regardless of what the caller passed.
    assert config.params["output_format"] == "pcm"
    # A default voice_id is injected — voice_id is required for Lightning.
    assert config.params["voice_id"] == "magnus"
    # A default sample_rate is injected as well.
    assert config.params["sample_rate"] == 24000
    # Default endpoint is the Smallest Lightning SSE streaming endpoint.
    assert config.url == "https://api.smallest.ai/waves/v1/tts/live"
    print("✅ Defaults test passed.")


def test_output_format_is_forced_to_pcm():
    """Even if the caller asks for wav/mp3, we override to pcm."""
    from smallest_tts_python.config import SmallestTTSConfig

    config = SmallestTTSConfig(params={"api_key": "k", "output_format": "wav"})
    config.update_params()
    assert config.params["output_format"] == "pcm"
    print("✅ output_format override test passed.")


# ================ test endpoint URL resolution ================
@patch("smallest_tts_python.smallest_tts.AsyncClient")
@patch("smallest_tts_python.smallest_tts.Timeout")
@patch("smallest_tts_python.smallest_tts.Limits")
def test_url_and_base_url_configuration(
    MockLimits, MockTimeout, MockAsyncClient
):
    """The endpoint URL is resolved from `url` (top-level) or `base_url` (params)."""
    from smallest_tts_python.smallest_tts import SmallestTTSClient
    from smallest_tts_python.config import SmallestTTSConfig
    from ten_runtime import AsyncTenEnv

    MockTimeout.return_value = MagicMock()
    MockLimits.return_value = MagicMock()
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    MockAsyncClient.return_value = mock_client

    mock_ten_env = MagicMock(spec=AsyncTenEnv)
    for attr in ("log_info", "log_debug", "log_error", "log_warn"):
        setattr(mock_ten_env, attr, MagicMock())

    common_params = {"api_key": "test_key", "model": "lightning_v3.1"}

    # Case 1: explicit top-level url wins.
    cfg = SmallestTTSConfig(
        url="https://custom-server.com/v1/tts", params=dict(common_params)
    )
    cfg.update_params()
    client = SmallestTTSClient(cfg, mock_ten_env)
    assert client.config.url == "https://custom-server.com/v1/tts"

    # Case 2: base_url (trailing slash) -> {base_url}/waves/v1/tts/live.
    cfg = SmallestTTSConfig(
        params={**common_params, "base_url": "https://api.custom.com/"}
    )
    cfg.update_params()
    assert cfg.url == "https://api.custom.com/waves/v1/tts/live"

    # Case 3: base_url (no trailing slash).
    cfg = SmallestTTSConfig(
        params={**common_params, "base_url": "https://api.custom.com"}
    )
    cfg.update_params()
    assert cfg.url == "https://api.custom.com/waves/v1/tts/live"

    # Case 4: default Smallest endpoint.
    cfg = SmallestTTSConfig(params=dict(common_params))
    cfg.update_params()
    assert cfg.url == "https://api.smallest.ai/waves/v1/tts/live"

    # Case 5: url in params is extracted and removed.
    cfg = SmallestTTSConfig(
        params={**common_params, "url": "https://params-url.com/tts"}
    )
    cfg.update_params()
    assert cfg.url == "https://params-url.com/tts"
    assert "url" not in cfg.params
    print("✅ URL/base_url configuration test passed.")


# ================ test headers ================
@patch("smallest_tts_python.smallest_tts.AsyncClient")
@patch("smallest_tts_python.smallest_tts.Timeout")
@patch("smallest_tts_python.smallest_tts.Limits")
def test_headers_configuration(MockLimits, MockTimeout, MockAsyncClient):
    """Default Authorization/Content-Type headers, with user override/merge."""
    from smallest_tts_python.smallest_tts import SmallestTTSClient
    from smallest_tts_python.config import SmallestTTSConfig
    from ten_runtime import AsyncTenEnv

    MockTimeout.return_value = MagicMock()
    MockLimits.return_value = MagicMock()
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    MockAsyncClient.return_value = mock_client

    mock_ten_env = MagicMock(spec=AsyncTenEnv)
    for attr in ("log_info", "log_debug", "log_error", "log_warn"):
        setattr(mock_ten_env, attr, MagicMock())

    common_params = {
        "api_key": "test_api_key_123",
        "model": "lightning_v3.1",
    }

    # Defaults.
    cfg = SmallestTTSConfig(params=dict(common_params))
    cfg.update_params()
    client = SmallestTTSClient(cfg, mock_ten_env)
    assert client.headers["Authorization"] == "Bearer test_api_key_123"
    assert client.headers["Content-Type"] == "application/json"
    assert client.headers["X-Source"] == "ten-framework"
    assert len(client.headers) == 3

    # Merge custom header.
    cfg = SmallestTTSConfig(
        headers={"X-Custom-Header": "custom-value"}, params=dict(common_params)
    )
    cfg.update_params()
    client = SmallestTTSClient(cfg, mock_ten_env)
    assert client.headers["Authorization"] == "Bearer test_api_key_123"
    assert client.headers["X-Custom-Header"] == "custom-value"
    assert len(client.headers) == 4

    # User override of Authorization.
    cfg = SmallestTTSConfig(
        headers={"Authorization": "Bearer custom_token"},
        params=dict(common_params),
    )
    cfg.update_params()
    client = SmallestTTSClient(cfg, mock_ten_env)
    assert client.headers["Authorization"] == "Bearer custom_token"
    print("✅ Headers configuration test passed.")


# ================ test validate ================
def test_validate():
    """validate() requires api_key (or Authorization header) and voice_id."""
    from smallest_tts_python.config import SmallestTTSConfig

    # api_key in params -> ok.
    cfg = SmallestTTSConfig(params={"api_key": "k", "model": "lightning_v3.1"})
    cfg.update_params()
    cfg.validate()

    # Authorization header instead of api_key -> ok.
    cfg = SmallestTTSConfig(
        params={"model": "lightning_v3.1"},
        headers={"Authorization": "Bearer t"},
    )
    cfg.update_params()
    cfg.validate()

    # Neither -> error.
    cfg = SmallestTTSConfig(params={"model": "lightning_v3.1"})
    cfg.update_params()
    try:
        cfg.validate()
        assert False, "expected ValueError when no auth provided"
    except ValueError as e:
        assert "API key or Authorization header is required" in str(e)

    # voice_id is required, but update_params() injects the default
    # ("magnus"), so a bare api_key config still validates.
    cfg = SmallestTTSConfig(params={"api_key": "k"})
    cfg.update_params()
    cfg.validate()  # should not raise
    print("✅ Validate test passed.")


# ================ test to_str sensitive handling ================
def test_to_str_masks_authorization_header():
    """to_str() must not leak an Authorization header in plaintext.

    headers.Authorization is a supported auth path merged into the actual
    HTTP request, so the key-point log (which stringifies the whole config)
    must not contain it verbatim.
    """
    from smallest_tts_python.config import SmallestTTSConfig

    config = SmallestTTSConfig(
        headers={"Authorization": "Bearer header_secret_token"},
        params={"api_key": "test_api_key_123"},
    )

    rendered = config.to_str(sensitive_handling=True)

    assert "Bearer header_secret_token" not in rendered
    assert "test_api_key_123" not in rendered
    print("Authorization header masking test passed.")


def test_to_str_masks_api_key_header_variants():
    """Case/variant coverage for the other header names Smallest accepts."""
    from smallest_tts_python.config import SmallestTTSConfig

    for header_name in ("api-key", "X-Api-Key", "xi-api-key"):
        config = SmallestTTSConfig(headers={header_name: "secret_header_value"})

        rendered = config.to_str(sensitive_handling=True)

        assert (
            "secret_header_value" not in rendered
        ), f"{header_name} was not redacted"
    print("API-key header variant masking test passed.")


def test_to_str_without_sensitive_handling_keeps_raw_values():
    """sensitive_handling=False is an explicit opt-out and must not redact."""
    from smallest_tts_python.config import SmallestTTSConfig

    config = SmallestTTSConfig(
        headers={"Authorization": "Bearer header_secret_token"},
        params={"api_key": "test_api_key_123"},
    )

    rendered = config.to_str(sensitive_handling=False)

    assert "Bearer header_secret_token" in rendered
    assert "test_api_key_123" in rendered
    print("Non-sensitive to_str test passed.")
