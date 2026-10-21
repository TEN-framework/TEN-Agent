import pytest

from ..recognition import validate_endpoint


def test_accepts_default_wss():
    validate_endpoint(
        "wss://speech-api.oruk.ai/v1/realtime?model=oruk-realtime"
    )


def test_rejects_non_wss():
    with pytest.raises(ValueError):
        validate_endpoint("https://speech-api.oruk.ai/v1/realtime")


def test_rejects_credentials_in_url():
    with pytest.raises(ValueError):
        validate_endpoint("wss://user:pass@speech-api.oruk.ai/v1/realtime")


def test_rejects_extra_query_params():
    with pytest.raises(ValueError):
        validate_endpoint(
            "wss://speech-api.oruk.ai/v1/realtime?model=oruk-realtime&token=abc"
        )


def test_allows_ws_on_loopback():
    validate_endpoint("ws://127.0.0.1:8080/v1/realtime")
