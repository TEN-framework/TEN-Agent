import asyncio
from unittest.mock import MagicMock

import pytest
from dashscope.audio.tts_v2 import SpeechSynthesizerObjectPool

from .. import cosy_tts
from ..config import CosyTTSConfig
from ..cosy_tts import (
    CosyTTSClient,
    CosyTTSProviderError,
    SharedPool,
)
from .test_connection_reuse import (
    PROPERTY_JSON,
    SERVER_PORT,
    FakeDashScopeServer,
)


@pytest.fixture
def client_server() -> FakeDashScopeServer:
    server = FakeDashScopeServer(SERVER_PORT)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def _config() -> CosyTTSConfig:
    config = CosyTTSConfig.model_validate(
        {
            "headers": {"X-Test": "value"},
            "params": {
                "api_key": "test-key",
                "model": "cosyvoice-v3-flash",
                "sample_rate": 16000,
                "url": "ws://127.0.0.1:12345",
                "voice": "longanyang",
            },
        }
    )
    config.update_params()
    return config


def test_url_and_vendor_request_headers() -> None:
    headers = SharedPool._headers(_config())

    assert headers["Authorization"] == "Bearer test-key"
    assert headers["User-Agent"] == "ten-cosy-tts/0.4.4"
    assert headers["X-Test"] == "value"


def test_transient_startup_failure_is_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def register(_cls, _config) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("websocket handshake timed out")

    monkeypatch.setattr(
        SharedPool,
        "register",
        classmethod(register),
    )
    monkeypatch.setattr(
        cosy_tts,
        "TTS_STARTUP_RETRY_DELAYS_SECONDS",
        (0.0, 0.0),
    )
    client = CosyTTSClient(_config(), MagicMock(), "cosy")

    delay_ms = asyncio.run(client.start())

    assert delay_ms >= 0
    assert calls == 2
    assert client._registered is True


def test_authentication_startup_failure_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def register(_cls, _config) -> None:
        nonlocal calls
        calls += 1
        raise OSError("401 Unauthorized: invalid API key")

    monkeypatch.setattr(
        SharedPool,
        "register",
        classmethod(register),
    )
    client = CosyTTSClient(_config(), MagicMock(), "cosy")

    with pytest.raises(CosyTTSProviderError) as exc_info:
        asyncio.run(client.start())

    assert calls == 1
    assert exc_info.value.error.code == "InvalidApiKey"


def test_sdk_singleton_attribute_is_deleted() -> None:
    had_instance = hasattr(SpeechSynthesizerObjectPool, "_instance")
    original_instance = getattr(
        SpeechSynthesizerObjectPool,
        "_instance",
        None,
    )
    sentinel = object()
    setattr(SpeechSynthesizerObjectPool, "_instance", sentinel)
    try:
        SharedPool._delete_sdk_instance(sentinel)
        assert not hasattr(SpeechSynthesizerObjectPool, "_instance")
    finally:
        if had_instance:
            setattr(
                SpeechSynthesizerObjectPool,
                "_instance",
                original_instance,
            )
        elif hasattr(SpeechSynthesizerObjectPool, "_instance"):
            delattr(SpeechSynthesizerObjectPool, "_instance")


def test_pool_stop_start_recreates_sdk_singleton(
    client_server: FakeDashScopeServer,
) -> None:
    config = CosyTTSConfig.model_validate_json(PROPERTY_JSON)
    config.update_params()

    for _ in range(2):
        SharedPool.register(config)
        assert SharedPool._pool is not None
        SharedPool.release_client()
        assert not hasattr(SpeechSynthesizerObjectPool, "_instance")
