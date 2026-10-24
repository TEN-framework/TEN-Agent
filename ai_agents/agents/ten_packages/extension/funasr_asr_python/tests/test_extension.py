#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from funasr_asr_python.config import FunASRConfig
from funasr_asr_python.extension import FunASRExtension


@pytest.fixture
def extension() -> FunASRExtension:
    instance = FunASRExtension("test_funasr")
    instance.ten_env = MagicMock()
    instance.ten_env.log_debug = MagicMock()
    instance.ten_env.log_error = MagicMock()
    instance.ten_env.log_info = MagicMock()
    instance.ten_env.log_warn = MagicMock()
    instance.ten_env.send_data = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_start_connection_reports_connected(
    extension: FunASRExtension,
) -> None:
    extension.config = FunASRConfig(params={})
    extension.on_connected = AsyncMock()
    extension.audio_timeline = MagicMock()
    extension.audio_timeline.get_total_user_audio_duration.return_value = 0

    with patch("funasr_asr_python.extension.FunASRClient") as client_class:
        client = client_class.return_value
        client.connect = AsyncMock()
        client.is_connected.return_value = False

        await extension.start_connection()

    extension.on_connected.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_start_connection_failure_reports_disconnected(
    extension: FunASRExtension,
) -> None:
    extension.config = FunASRConfig(params={})
    extension.send_asr_error = AsyncMock()
    extension.on_disconnected = AsyncMock()

    with patch("funasr_asr_python.extension.FunASRClient") as client_class:
        client = client_class.return_value
        client.connect = AsyncMock(side_effect=RuntimeError("load failed"))
        client.is_connected.return_value = False

        await extension.start_connection()

    assert extension.send_asr_error.await_count == 1
    extension.on_disconnected.assert_awaited_once()
    assert extension.client is None


@pytest.mark.asyncio
async def test_stop_connection_reports_disconnected(
    extension: FunASRExtension,
) -> None:
    client = MagicMock()
    client.disconnect = AsyncMock()
    extension.client = client
    extension.on_disconnected = AsyncMock()

    await extension.stop_connection()

    extension.on_disconnected.assert_awaited_once_with(
        code=0, message="stopped"
    )


@pytest.mark.asyncio
async def test_finalize_always_reports_completion(
    extension: FunASRExtension,
) -> None:
    extension.config = FunASRConfig(finalize_mode="disconnect")
    client = MagicMock()
    client.finalize = AsyncMock()
    extension.client = client
    extension.send_asr_finalize_end = AsyncMock()

    await extension.finalize(None)

    client.finalize.assert_awaited_once_with()
    extension.send_asr_finalize_end.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_send_audio_does_not_mask_lock_failure(
    extension: FunASRExtension,
) -> None:
    client = MagicMock()
    client.is_connected.return_value = True
    extension.client = client
    frame = MagicMock()
    frame.lock_buf.side_effect = RuntimeError("lock failed")

    result = await extension.send_audio(frame, None)

    assert result is False
    frame.unlock_buf.assert_not_called()


@pytest.mark.asyncio
async def test_result_uses_detected_language_when_config_is_auto(
    extension: FunASRExtension,
) -> None:
    extension.config = FunASRConfig(params={"language": "auto"})
    extension.audio_timeline = MagicMock()
    extension.audio_timeline.get_audio_duration_before_time.return_value = 0
    extension.send_asr_result = AsyncMock()

    await extension._on_result(
        text="你好",
        start_ms=0,
        duration_ms=1000,
        language="zh",
        final=False,
    )

    result = extension.send_asr_result.await_args.args[0]
    assert result.language == "zh-CN"
