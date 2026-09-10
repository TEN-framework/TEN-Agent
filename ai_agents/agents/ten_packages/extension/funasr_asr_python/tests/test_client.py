#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from funasr_asr_python.funasr_client import FunASRClient


def pcm_samples(count: int) -> bytes:
    return np.zeros(count, dtype=np.int16).tobytes()


@pytest.fixture
def client() -> FunASRClient:
    result_callback = AsyncMock()
    instance = FunASRClient(
        sample_rate=10,
        on_result_callback=result_callback,
    )
    instance.model = MagicMock()
    instance.model.generate.return_value = [{"text": "hello"}]
    instance.is_connected_flag = True
    return instance


@pytest.mark.asyncio
async def test_process_audio_reports_cumulative_start_offset(
    client: FunASRClient,
) -> None:
    client.audio_buffer.extend(pcm_samples(10))
    await client._process_audio()
    client.audio_buffer.extend(pcm_samples(10))
    await client._process_audio()

    assert client.on_result_callback.await_args_list[0].kwargs["start_ms"] == 0
    assert (
        client.on_result_callback.await_args_list[1].kwargs["start_ms"] == 1000
    )


@pytest.mark.asyncio
async def test_process_audio_preserves_samples_beyond_max_chunk(
    client: FunASRClient,
) -> None:
    client.max_audio_length_ms = 1000
    client.audio_buffer.extend(pcm_samples(15))

    await client._process_audio()

    assert bytes(client.audio_buffer) == pcm_samples(5)


@pytest.mark.asyncio
async def test_process_audio_extracts_sensevoice_language(
    client: FunASRClient,
) -> None:
    client.model.generate.return_value = [
        {"text": "<|zh|><|NEUTRAL|><|Speech|><|woitn|>你好"}
    ]
    client.audio_buffer.extend(pcm_samples(10))

    await client._process_audio()

    assert client.on_result_callback.await_args.kwargs["language"] == "zh"


@pytest.mark.asyncio
async def test_connect_failure_is_reported_by_extension_only() -> None:
    error_callback = AsyncMock()
    client = FunASRClient(on_error_callback=error_callback)

    with patch(
        "funasr_asr_python.funasr_client.AutoModel",
        side_effect=RuntimeError("load failed"),
    ):
        with pytest.raises(RuntimeError, match="load failed"):
            await client.connect()

    error_callback.assert_not_awaited()
    assert not client.is_connected()
