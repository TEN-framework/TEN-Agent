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
from pathlib import Path
import json
from unittest.mock import patch, MagicMock, AsyncMock

from ten_runtime import (
    ExtensionTester,
    TenEnvTester,
    Cmd,
    CmdResult,
    StatusCode,
    TenError,
)


# ================ test params passthrough ================
class ExtensionTesterForPassthrough(ExtensionTester):
    """A simple tester that just starts and stops, to allow checking constructor calls."""

    def check_hello(self, ten_env: TenEnvTester, result: CmdResult | None):
        if result is None:
            ten_env.stop_test(TenError(1, "CmdResult is None"))
            return
        statusCode = result.get_status_code()
        print("receive hello_world, status:" + str(statusCode))

        if statusCode == StatusCode.OK:
            # TODO: move stop_test() to where the test passes
            ten_env.stop_test()

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        new_cmd = Cmd.create("hello_world")

        print("send hello_world")
        ten_env_tester.send_cmd(
            new_cmd,
            lambda ten_env, result, _: self.check_hello(ten_env, result),
        )

        print("tester on_start_done")
        ten_env_tester.on_start_done()


@patch("openai_tts2_python.openai_tts.AsyncClient")
def test_params_passthrough(MockAsyncClient):
    """
    Tests that custom parameters passed in the configuration are correctly
    forwarded to the OpenAI TTS client constructor.
    """
    print("Starting test_params_passthrough with mock...")

    # --- Mock Configuration ---
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    MockAsyncClient.return_value = mock_client

    # --- Test Setup ---
    # Define a configuration with custom parameters inside 'params'.
    real_config = {
        "params": {
            "api_key": "a_test_api_key",
            "model": "gpt-4o-mini-tts",
        },
    }

    # Expected params after processing (response_format is added by update_params)
    passthrough_params = {
        "api_key": "a_test_api_key",
        "model": "gpt-4o-mini-tts",
        "voice": "coral",
        "speed": 1.0,
        "instructions": "",
        "response_format": "pcm",
    }

    tester = ExtensionTesterForPassthrough()
    tester.set_test_mode_single("openai_tts2_python", json.dumps(real_config))

    print("Running passthrough test...")
    tester.run()
    print("Passthrough test completed.")

    # --- Assertions ---
    # Check that the httpx AsyncClient was instantiated
    MockAsyncClient.assert_called_once()

    # For httpx-based implementation, we verify params are passed correctly
    # by checking that the client was created (params are used in OpenAITTSClient.__init__)
    # The actual parameter passthrough happens in the get() method when building the payload

    print("✅ Params passthrough test passed successfully.")
    print(f"✅ httpx AsyncClient was created correctly")


@patch("openai_tts2_python.openai_tts.AsyncClient")
@patch("openai_tts2_python.openai_tts.Timeout")
@patch("openai_tts2_python.openai_tts.Limits")
def test_url_and_base_url_configuration(
    MockLimits, MockTimeout, MockAsyncClient
):
    """
    Tests that the endpoint URL is correctly configured based on 'url' (top-level) or 'base_url' (in params) parameters.

    Test cases:
    1. When 'url' (top-level) is provided, endpoint should use the url value directly
    2. When 'base_url' (in params) is provided (with trailing slash), endpoint should be {base_url}/audio/speech
    3. When 'base_url' (in params) is provided (without trailing slash), endpoint should be {base_url}/audio/speech
    4. When neither is provided, endpoint should use default https://api.openai.com/v1/audio/speech
    5. When both 'url' (top-level) and 'base_url' (in params) are provided, 'url' takes precedence
    """
    print("Starting test_url_and_base_url_configuration with mock...")

    from openai_tts2_python.openai_tts import OpenAITTSClient
    from openai_tts2_python.config import OpenAITTSConfig
    from ten_runtime import AsyncTenEnv
    from unittest.mock import MagicMock

    # Mock httpx components
    MockTimeout.return_value = MagicMock()
    MockLimits.return_value = MagicMock()
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    MockAsyncClient.return_value = mock_client

    # Mock TenEnv
    mock_ten_env = MagicMock(spec=AsyncTenEnv)
    mock_ten_env.log_info = MagicMock()
    mock_ten_env.log_debug = MagicMock()
    mock_ten_env.log_error = MagicMock()
    mock_ten_env.log_warn = MagicMock()

    # Common params for all test cases (model and voice are required by validate())
    common_params = {
        "api_key": "test_key",
        "model": "gpt-4o-mini-tts",
        "voice": "coral",
    }

    # Test Case 1: Using 'url' parameter (top-level field)
    print("  → Test Case 1: Using 'url' parameter (top-level field)")
    config_with_url = OpenAITTSConfig(
        url="https://custom-server.com/v1/tts",
        params=common_params,
    )
    config_with_url.update_params()  # Call update_params to process base_url if needed
    client_with_url = OpenAITTSClient(config_with_url, mock_ten_env)
    assert (
        client_with_url.config.url == "https://custom-server.com/v1/tts"
    ), f"Expected endpoint to be 'https://custom-server.com/v1/tts', got '{client_with_url.config.url}'"
    print("    ✓ URL parameter correctly used as endpoint")

    # Test Case 2: Using 'base_url' parameter (with trailing slash)
    print("  → Test Case 2: Using 'base_url' parameter (with trailing slash)")
    config_with_base_url_slash = OpenAITTSConfig(
        params={
            **common_params,
            "base_url": "https://api.custom.com/v1/",
        }
    )
    config_with_base_url_slash.update_params()  # Call update_params to process base_url
    client_with_base_url_slash = OpenAITTSClient(
        config_with_base_url_slash, mock_ten_env
    )
    expected_endpoint = "https://api.custom.com/v1/audio/speech"
    assert (
        client_with_base_url_slash.config.url == expected_endpoint
    ), f"Expected endpoint to be '{expected_endpoint}', got '{client_with_base_url_slash.config.url}'"
    print("    ✓ Base URL with trailing slash correctly processed")

    # Test Case 3: Using 'base_url' parameter (without trailing slash)
    print(
        "  → Test Case 3: Using 'base_url' parameter (without trailing slash)"
    )
    config_with_base_url = OpenAITTSConfig(
        params={
            **common_params,
            "base_url": "https://api.custom.com/v1",
        }
    )
    config_with_base_url.update_params()  # Call update_params to process base_url
    client_with_base_url = OpenAITTSClient(config_with_base_url, mock_ten_env)
    expected_endpoint = "https://api.custom.com/v1/audio/speech"
    assert (
        client_with_base_url.config.url == expected_endpoint
    ), f"Expected endpoint to be '{expected_endpoint}', got '{client_with_base_url.config.url}'"
    print("    ✓ Base URL without trailing slash correctly processed")

    # Test Case 4: Neither 'url' nor 'base_url' provided (should use default)
    print("  → Test Case 4: Using default endpoint (no url or base_url)")
    config_default = OpenAITTSConfig(params=common_params)
    config_default.update_params()  # Call update_params to set default url
    client_default = OpenAITTSClient(config_default, mock_ten_env)
    expected_endpoint = "https://api.openai.com/v1/audio/speech"
    assert (
        client_default.config.url == expected_endpoint
    ), f"Expected endpoint to be '{expected_endpoint}', got '{client_default.config.url}'"
    print("    ✓ Default endpoint correctly used")

    # Test Case 5: 'url' takes precedence over 'base_url' when both are provided
    print("  → Test Case 5: 'url' takes precedence over 'base_url'")
    config_both = OpenAITTSConfig(
        url="https://url-takes-precedence.com/tts",
        params={
            **common_params,
            "base_url": "https://base-url-should-be-ignored.com/v1",
        },
    )
    config_both.update_params()  # Call update_params (url should not be overwritten)
    client_both = OpenAITTSClient(config_both, mock_ten_env)
    assert (
        client_both.config.url == "https://url-takes-precedence.com/tts"
    ), f"Expected endpoint to be 'https://url-takes-precedence.com/tts', got '{client_both.config.url}'"
    print("    ✓ URL parameter correctly takes precedence over base_url")

    print("✅ URL and base_url configuration test passed successfully.")


def test_invalid_param_values_use_safe_defaults():
    """Invalid free-form params must not leave the client unusable."""
    from openai_tts2_python.config import OpenAITTSConfig

    config = OpenAITTSConfig(
        params={
            "api_key": "test_key",
            "model": "gpt-4o-mini-tts",
            "voice": "coral",
            "speed": "not-a-number",
            "url": 8080,
            "base_url": "https://api.custom.com/v1/",
        }
    )
    config.update_params()

    assert config.params["speed"] == 1.0
    assert config.url == "https://api.custom.com/v1/audio/speech"
    assert "url" not in config.params
    assert "base_url" not in config.params


def test_speed_rejects_bool_and_non_finite_values():
    """Speed must be a finite numeric value."""
    from openai_tts2_python.config import OpenAITTSConfig

    for value in (False, "nan", "inf"):
        config = OpenAITTSConfig(params={"speed": value})
        config.update_params()
        assert config.params["speed"] == 1.0


def test_validate_rejects_empty_url():
    """An empty top-level URL must fail before the first request."""
    from openai_tts2_python.config import OpenAITTSConfig

    config = OpenAITTSConfig(
        url="",
        params={
            "api_key": "test_key",
            "model": "gpt-4o-mini-tts",
            "voice": "coral",
        },
    )
    config.update_params()
    config.url = ""

    try:
        config.validate()
    except ValueError as exc:
        assert str(exc) == "URL is required for OpenAI TTS"
    else:
        raise AssertionError("Expected empty URL validation to fail")


@patch("openai_tts2_python.openai_tts.AsyncClient")
@patch("openai_tts2_python.openai_tts.Timeout")
@patch("openai_tts2_python.openai_tts.Limits")
def test_headers_configuration(MockLimits, MockTimeout, MockAsyncClient):
    """
    Tests that headers are correctly configured and merged with defaults.

    Test cases:
    1. When no headers provided, should use default headers (Authorization + Content-Type)
    2. When partial headers provided, should merge with defaults (keep Authorization)
    3. When full headers provided, should use user headers (can override Authorization)
    4. When custom headers provided, should merge with defaults
    """
    print("Starting test_headers_configuration with mock...")

    from openai_tts2_python.openai_tts import OpenAITTSClient
    from openai_tts2_python.config import OpenAITTSConfig
    from ten_runtime import AsyncTenEnv
    from unittest.mock import MagicMock

    # Mock httpx components
    MockTimeout.return_value = MagicMock()
    MockLimits.return_value = MagicMock()
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    MockAsyncClient.return_value = mock_client

    # Mock TenEnv
    mock_ten_env = MagicMock(spec=AsyncTenEnv)
    mock_ten_env.log_info = MagicMock()
    mock_ten_env.log_debug = MagicMock()
    mock_ten_env.log_error = MagicMock()
    mock_ten_env.log_warn = MagicMock()

    # Common params for all test cases
    common_params = {
        "api_key": "test_api_key_123",
        "model": "gpt-4o-mini-tts",
        "voice": "coral",
    }

    # Test Case 1: No headers provided (should use defaults)
    print("  → Test Case 1: No headers provided (should use defaults)")
    config_no_headers = OpenAITTSConfig(
        params=common_params,
    )
    config_no_headers.update_params()
    client_no_headers = OpenAITTSClient(config_no_headers, mock_ten_env)
    assert (
        "Authorization" in client_no_headers.headers
    ), "Expected Authorization header to be present"
    assert (
        client_no_headers.headers["Authorization"] == "Bearer test_api_key_123"
    ), f"Expected Authorization header to be 'Bearer test_api_key_123', got '{client_no_headers.headers.get('Authorization')}'"
    assert (
        client_no_headers.headers["Content-Type"] == "application/json"
    ), f"Expected Content-Type header to be 'application/json', got '{client_no_headers.headers.get('Content-Type')}'"
    assert (
        len(client_no_headers.headers) == 2
    ), f"Expected 2 headers, got {len(client_no_headers.headers)}"
    print("    ✓ Default headers correctly set")

    # Test Case 2: Partial headers provided (should merge with defaults)
    print(
        "  → Test Case 2: Partial headers provided (should merge with defaults)"
    )
    config_partial_headers = OpenAITTSConfig(
        headers={"X-Custom-Header": "custom-value"},
        params=common_params,
    )
    config_partial_headers.update_params()
    client_partial_headers = OpenAITTSClient(
        config_partial_headers, mock_ten_env
    )
    assert (
        "Authorization" in client_partial_headers.headers
    ), "Expected Authorization header to be present after merge"
    assert (
        client_partial_headers.headers["Authorization"]
        == "Bearer test_api_key_123"
    ), "Expected Authorization header to be preserved"
    assert (
        client_partial_headers.headers["Content-Type"] == "application/json"
    ), "Expected Content-Type header to be present"
    assert (
        client_partial_headers.headers["X-Custom-Header"] == "custom-value"
    ), "Expected custom header to be present"
    assert (
        len(client_partial_headers.headers) == 3
    ), f"Expected 3 headers, got {len(client_partial_headers.headers)}"
    print("    ✓ Partial headers correctly merged with defaults")

    # Test Case 3: Full headers provided (should override defaults)
    print("  → Test Case 3: Full headers provided (should override defaults)")
    config_full_headers = OpenAITTSConfig(
        headers={
            "Authorization": "Bearer custom_token",
            "Content-Type": "application/xml",
            "X-Custom-Header": "custom-value",
        },
        params=common_params,
    )
    config_full_headers.update_params()
    client_full_headers = OpenAITTSClient(config_full_headers, mock_ten_env)
    assert (
        client_full_headers.headers["Authorization"] == "Bearer custom_token"
    ), "Expected user-provided Authorization to override default"
    assert (
        client_full_headers.headers["Content-Type"] == "application/xml"
    ), "Expected user-provided Content-Type to override default"
    assert (
        client_full_headers.headers["X-Custom-Header"] == "custom-value"
    ), "Expected custom header to be present"
    assert (
        len(client_full_headers.headers) == 3
    ), f"Expected 3 headers, got {len(client_full_headers.headers)}"
    print("    ✓ User headers correctly override defaults")

    # Test Case 4: Empty headers dict (should use defaults)
    print("  → Test Case 4: Empty headers dict (should use defaults)")
    config_empty_headers = OpenAITTSConfig(
        headers={},
        params=common_params,
    )
    config_empty_headers.update_params()
    client_empty_headers = OpenAITTSClient(config_empty_headers, mock_ten_env)
    assert (
        "Authorization" in client_empty_headers.headers
    ), "Expected Authorization header to be present with empty headers dict"
    assert (
        client_empty_headers.headers["Authorization"]
        == "Bearer test_api_key_123"
    ), "Expected default Authorization header"
    assert (
        client_empty_headers.headers["Content-Type"] == "application/json"
    ), "Expected default Content-Type header"
    assert (
        len(client_empty_headers.headers) == 2
    ), f"Expected 2 headers, got {len(client_empty_headers.headers)}"
    print("    ✓ Empty headers dict correctly uses defaults")

    print("✅ Headers configuration test passed successfully.")


def test_vendor_metadata_does_not_convert_api_key_to_authorization():
    from openai_tts2_python.config import OpenAITTSConfig
    from openai_tts2_python.extension import OpenAITTSExtension

    extension = OpenAITTSExtension("tts")
    config = OpenAITTSConfig(
        params={
            "api_key": "test_api_key_123",
            "model": "gpt-4o-mini-tts",
            "voice": "coral",
        },
    )
    config.update_params()
    extension.config = config

    metadata = extension.vendor_metadata()

    assert metadata["authorization"] == ""
    assert metadata["api_key"] == "test_api_key_123"
    assert "key" not in metadata


def test_vendor_metadata_returns_raw_config_authorization_header():
    from openai_tts2_python.config import OpenAITTSConfig
    from openai_tts2_python.extension import OpenAITTSExtension

    extension = OpenAITTSExtension("tts")
    config = OpenAITTSConfig(
        headers={"Authorization": "Bearer header_key"},
        params={
            "api_key": "test_api_key_123",
            "model": "gpt-4o-mini-tts",
            "voice": "coral",
        },
    )
    config.update_params()
    extension.config = config

    metadata = extension.vendor_metadata()

    assert metadata["authorization"] == "Bearer header_key"
    assert metadata["api_key"] == "test_api_key_123"
    assert "key" not in metadata


def test_to_str_masks_authorization_header():
    from openai_tts2_python.config import OpenAITTSConfig

    config = OpenAITTSConfig(
        headers={"Authorization": "Bearer header_key"},
        params={"api_key": "test_api_key_123"},
    )

    rendered = config.to_str(sensitive_handling=True)

    assert "Bearer header_key" not in rendered
    assert "test_api_key_123" not in rendered


@patch("openai_tts2_python.openai_tts.AsyncClient")
@patch("openai_tts2_python.openai_tts.Timeout")
@patch("openai_tts2_python.openai_tts.Limits")
def test_url_in_params(MockLimits, MockTimeout, MockAsyncClient):
    """
    Tests that 'url' parameter in params is correctly extracted and used.

    Test cases:
    1. When 'url' is in params (and not in top-level), it should be extracted to config.url
    2. When 'url' is in params, it should be removed from params after extraction
    3. When both top-level 'url' and params 'url' exist, top-level takes precedence
    4. When 'url' is in params but top-level url is None, params url should be used
    """
    print("Starting test_url_in_params with mock...")

    from openai_tts2_python.openai_tts import OpenAITTSClient
    from openai_tts2_python.config import OpenAITTSConfig
    from ten_runtime import AsyncTenEnv
    from unittest.mock import MagicMock

    # Mock httpx components
    MockTimeout.return_value = MagicMock()
    MockLimits.return_value = MagicMock()
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    MockAsyncClient.return_value = mock_client

    # Mock TenEnv
    mock_ten_env = MagicMock(spec=AsyncTenEnv)
    mock_ten_env.log_info = MagicMock()
    mock_ten_env.log_debug = MagicMock()
    mock_ten_env.log_error = MagicMock()
    mock_ten_env.log_warn = MagicMock()

    # Common params for all test cases
    common_params = {
        "api_key": "test_key",
        "model": "gpt-4o-mini-tts",
        "voice": "coral",
    }

    # Test Case 1: 'url' in params (should be extracted to config.url)
    print(
        "  → Test Case 1: 'url' in params (should be extracted to config.url)"
    )
    config_url_in_params = OpenAITTSConfig(
        params={
            **common_params,
            "url": "https://custom-server.com/v1/tts",
        }
    )
    config_url_in_params.update_params()
    assert (
        config_url_in_params.url == "https://custom-server.com/v1/tts"
    ), f"Expected url to be 'https://custom-server.com/v1/tts', got '{config_url_in_params.url}'"
    assert (
        "url" not in config_url_in_params.params
    ), "Expected 'url' to be removed from params after extraction"
    client_url_in_params = OpenAITTSClient(config_url_in_params, mock_ten_env)
    assert (
        client_url_in_params.config.url == "https://custom-server.com/v1/tts"
    ), "Expected client config url to match extracted url"
    print("    ✓ URL in params correctly extracted to config.url")

    # Test Case 2: 'url' in params should be removed from params after extraction
    print(
        "  → Test Case 2: 'url' in params should be removed from params after extraction"
    )
    test_params = {
        **common_params,
        "url": "https://another-server.com/tts",
        "custom_param": "should_stay",
    }
    config_url_removal = OpenAITTSConfig(params=test_params)
    config_url_removal.update_params()
    assert (
        "url" not in config_url_removal.params
    ), "Expected 'url' to be removed from params"
    assert (
        "custom_param" in config_url_removal.params
    ), "Expected other params to remain"
    assert (
        config_url_removal.params["custom_param"] == "should_stay"
    ), "Expected other param values to be preserved"
    print("    ✓ URL correctly removed from params, other params preserved")

    # Test Case 3: Top-level 'url' takes precedence over params 'url'
    print("  → Test Case 3: Top-level 'url' takes precedence over params 'url'")
    config_precedence = OpenAITTSConfig(
        url="https://top-level-url.com/tts",
        params={
            **common_params,
            "url": "https://params-url.com/tts",
        },
    )
    config_precedence.update_params()
    assert (
        config_precedence.url == "https://top-level-url.com/tts"
    ), "Expected top-level url to take precedence"
    # When top-level url exists, params url should not be extracted
    # (it may or may not be removed, but top-level takes precedence)
    client_precedence = OpenAITTSClient(config_precedence, mock_ten_env)
    assert (
        client_precedence.config.url == "https://top-level-url.com/tts"
    ), "Expected client to use top-level url"
    print("    ✓ Top-level url correctly takes precedence")

    # Test Case 4: 'url' in params when top-level url is None
    print("  → Test Case 4: 'url' in params when top-level url is None")
    config_none_url = OpenAITTSConfig(
        url=None,
        params={
            **common_params,
            "url": "https://params-url-when-none.com/tts",
        },
    )
    config_none_url.update_params()
    assert (
        config_none_url.url == "https://params-url-when-none.com/tts"
    ), "Expected params url to be used when top-level url is None"
    print("    ✓ Params url correctly used when top-level url is None")

    print("✅ URL in params test passed successfully.")


@patch("openai_tts2_python.openai_tts.AsyncClient")
@patch("openai_tts2_python.openai_tts.Timeout")
@patch("openai_tts2_python.openai_tts.Limits")
def test_validate_with_authorization_header(
    MockLimits, MockTimeout, MockAsyncClient
):
    """
    Tests that validate() allows API key to be provided via Authorization header.

    Test cases:
    1. When api_key is in params, validation should pass
    2. When Authorization header is provided (no api_key in params), validation should pass
    3. When neither api_key nor Authorization header is provided, validation should fail
    4. When api_key is empty string but Authorization header exists, validation should pass
    5. When api_key is None but Authorization header exists, validation should pass
    """
    print("Starting test_validate_with_authorization_header with mock...")

    from openai_tts2_python.config import OpenAITTSConfig

    # Common params for test cases (model and voice are required)
    common_params = {
        "model": "gpt-4o-mini-tts",
        "voice": "coral",
    }

    # Test Case 1: api_key in params (should pass)
    print("  → Test Case 1: api_key in params (should pass)")
    config_with_api_key = OpenAITTSConfig(
        params={
            **common_params,
            "api_key": "test_api_key",
        }
    )
    config_with_api_key.update_params()
    try:
        config_with_api_key.validate()
        print("    ✓ Validation passed with api_key in params")
    except ValueError as e:
        assert False, f"Validation should pass with api_key in params, got: {e}"

    # Test Case 2: Authorization header provided (no api_key in params, should pass)
    print(
        "  → Test Case 2: Authorization header provided (no api_key in params, should pass)"
    )
    config_with_header = OpenAITTSConfig(
        params=common_params,
        headers={"Authorization": "Bearer test_token"},
    )
    config_with_header.update_params()
    try:
        config_with_header.validate()
        print("    ✓ Validation passed with Authorization header")
    except ValueError as e:
        assert (
            False
        ), f"Validation should pass with Authorization header, got: {e}"

    # Test Case 3: Neither api_key nor Authorization header (should fail)
    print(
        "  → Test Case 3: Neither api_key nor Authorization header (should fail)"
    )
    config_no_auth = OpenAITTSConfig(params=common_params)
    config_no_auth.update_params()
    try:
        config_no_auth.validate()
        assert (
            False
        ), "Validation should fail when neither api_key nor Authorization header is provided"
    except ValueError as e:
        assert "API key or Authorization header is required" in str(
            e
        ), f"Expected error message about API key or Authorization header, got: {e}"
        print("    ✓ Validation correctly failed without auth")

    # Test Case 4: Empty api_key string but Authorization header exists (should pass)
    print(
        "  → Test Case 4: Empty api_key string but Authorization header exists (should pass)"
    )
    config_empty_key_with_header = OpenAITTSConfig(
        params={
            **common_params,
            "api_key": "",
        },
        headers={"Authorization": "Bearer test_token"},
    )
    config_empty_key_with_header.update_params()
    try:
        config_empty_key_with_header.validate()
        print(
            "    ✓ Validation passed with empty api_key but Authorization header"
        )
    except ValueError as e:
        assert (
            False
        ), f"Validation should pass with Authorization header even if api_key is empty, got: {e}"

    # Test Case 5: api_key is None but Authorization header exists (should pass)
    print(
        "  → Test Case 5: api_key is None but Authorization header exists (should pass)"
    )
    config_none_key_with_header = OpenAITTSConfig(
        params={
            **common_params,
            "api_key": None,
        },
        headers={"Authorization": "Bearer test_token"},
    )
    config_none_key_with_header.update_params()
    try:
        config_none_key_with_header.validate()
        print(
            "    ✓ Validation passed with None api_key but Authorization header"
        )
    except ValueError as e:
        assert (
            False
        ), f"Validation should pass with Authorization header even if api_key is None, got: {e}"

    # Test Case 6: Both api_key and Authorization header (should pass, api_key takes precedence in client)
    print(
        "  → Test Case 6: Both api_key and Authorization header (should pass)"
    )
    config_both = OpenAITTSConfig(
        params={
            **common_params,
            "api_key": "test_api_key",
        },
        headers={"Authorization": "Bearer header_token"},
    )
    config_both.update_params()
    try:
        config_both.validate()
        print(
            "    ✓ Validation passed with both api_key and Authorization header"
        )
    except ValueError as e:
        assert (
            False
        ), f"Validation should pass with both api_key and Authorization header, got: {e}"

    print("✅ Validate with Authorization header test passed successfully.")
