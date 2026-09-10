import json
from unittest.mock import MagicMock, patch

# pylint: disable=protected-access

from ..config import CosyTTSConfig
from ..cosy_tts import (
    AUDIO_FORMAT_MAPPING,
    MESSAGE_TYPE_CMD_ERROR,
    AsyncIteratorCallback,
    ProviderError,
    SharedPool,
)


def _reset_shared_pool() -> None:
    SharedPool._pool = None
    SharedPool._signature = None
    SharedPool._clients = 0


def test_unsupported_control_params_are_ignored():
    config = CosyTTSConfig(
        params={
            "api_key": "test-key",
            "model": "cosyvoice-v3-flash",
            "voice": "longanyang",
            "pool_size": 4,
            "format": "mp3",
            "enable_ssml": True,
            "headers": {"X-Nested": "ignored"},
            "base_url": "wss://ignored.example.com",
            "workspace_id": "ignored-workspace",
            "future_protocol_parameter": "future-value",
        }
    )
    config.update_params()
    config.validate_params()

    assert config.format == "pcm"
    assert config.provider_params() == {
        "future_protocol_parameter": "future-value",
    }


def test_top_level_url_takes_precedence_over_params_url():
    config = CosyTTSConfig(
        url="wss://top-level.example.com/api-ws/v1/inference",
        params={
            "url": "wss://params.example.com/api-ws/v1/inference",
        },
    )

    config.update_params()

    assert config.url == "wss://top-level.example.com/api-ws/v1/inference"
    assert config.provider_params() == {}


def test_params_url_is_fallback_when_top_level_url_is_empty():
    config = CosyTTSConfig(
        params={
            "url": "wss://params.example.com/api-ws/v1/inference",
        },
    )

    config.update_params()

    assert config.url == "wss://params.example.com/api-ws/v1/inference"
    assert config.provider_params() == {}


def test_to_str_redacts_nested_provider_secrets():
    secret = "nested-provider-secret"
    config = CosyTTSConfig(
        params={"provider": {"token": secret}},
    )

    assert secret not in config.to_str()


def test_config_has_no_legacy_blacklist():
    assert "black_list_params" not in CosyTTSConfig.model_fields


def test_update_params_extracts_only_typed_fields():
    config = CosyTTSConfig(
        params={
            "api_key": "test-key",
            "model": "cosyvoice-v3-flash",
            "voice": "longanyang",
            "dump": True,
            "future_protocol_parameter": "future-value",
        }
    )

    config.update_params()

    assert config.api_key == "test-key"
    assert config.dump is False
    assert config.provider_params() == {
        "dump": True,
        "future_protocol_parameter": "future-value",
    }


def test_provider_error_is_queued_for_immediate_reporting():
    queue = MagicMock()
    loop = MagicMock()
    callback = AsyncIteratorCallback(MagicMock(), queue, loop, "request-id")
    callback.bind_task("task-id")
    message = json.dumps(
        {
            "header": {
                "task_id": "task-id",
                "error_code": "RequestTimeout",
                "error_message": "request timeout after 23 seconds",
            }
        }
    )

    with patch("asyncio.run_coroutine_threadsafe") as submit:
        callback.on_error(message)

    queued_item = queue.put.call_args.args[0]
    assert queued_item.message_type == MESSAGE_TYPE_CMD_ERROR
    assert queued_item.request_id == "request-id"
    assert queued_item.task_id == "task-id"
    assert queued_item.payload == ProviderError(
        code="RequestTimeout",
        message="request timeout after 23 seconds",
        task_id="task-id",
    )
    submit.assert_called_once_with(queue.put.return_value, loop)


def test_pool_uses_custom_url_and_headers():
    _reset_shared_pool()
    pool = MagicMock()
    config = CosyTTSConfig(
        api_key="test-key",
        model="cosyvoice-v3-flash",
        voice="longanyang",
        url="wss://example.com/api-ws/v1/inference",
        headers={"X-Test": "value"},
    )

    with patch(
        "cosy_tts_python.cosy_tts.SpeechSynthesizerObjectPool",
        return_value=pool,
    ) as pool_class:
        SharedPool.register(config)
        SharedPool.release_client()

    pool_class.assert_called_once_with(
        max_size=2,
        url="wss://example.com/api-ws/v1/inference",
        headers={
            "Authorization": "Bearer test-key",
            "User-Agent": "ten-cosy-tts/0.4.4",
            "X-Test": "value",
        },
    )
    pool.shutdown.assert_called_once()
    _reset_shared_pool()


def test_borrow_forwards_provider_params_and_pcm_sample_rate():
    _reset_shared_pool()
    pool = MagicMock()
    synthesizer = MagicMock()
    pool.borrow_synthesizer.return_value = synthesizer
    config = CosyTTSConfig(
        api_key="test-key",
        model="cosyvoice-v3-flash",
        voice="longanyang",
        sample_rate=24000,
        params={
            "api_key": "test-key",
            "model": "cosyvoice-v3-flash",
            "voice": "longanyang",
            "sample_rate": 24000,
            "instruction": "speak happily",
            "future_protocol_parameter": "future-value",
        },
    )
    config.update_params()

    with patch(
        "cosy_tts_python.cosy_tts.SpeechSynthesizerObjectPool",
        return_value=pool,
    ):
        SharedPool.register(config)
        callback = MagicMock()
        lease = SharedPool.borrow(config, callback)
        SharedPool.return_lease(lease)
        SharedPool.release_client()

    pool.borrow_synthesizer.assert_called_once_with(
        callback=callback,
        format=AUDIO_FORMAT_MAPPING[24000],
        model="cosyvoice-v3-flash",
        voice="longanyang",
        additional_params={
            "instruction": "speak happily",
            "future_protocol_parameter": "future-value",
        },
    )
    pool.return_synthesizer.assert_called_once_with(synthesizer)
    _reset_shared_pool()
