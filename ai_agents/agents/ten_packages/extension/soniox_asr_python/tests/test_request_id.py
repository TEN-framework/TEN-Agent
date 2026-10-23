#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ten_ai_base.message import ModuleErrorCode

from ..extension import SonioxASRExtension


@pytest.mark.asyncio
async def test_handle_error_preserves_request_id_in_log_and_metadata():
    ext = SonioxASRExtension("test")
    ext.ten_env = MagicMock()
    ext.send_asr_error = AsyncMock()

    request_id = "3d37a3bd-5078-47ee-a369-b204e3bbedda"
    await ext._handle_error(
        503,
        "Cannot continue request (code 11)",
        request_id=request_id,
        error_type="service_unavailable",
    )

    # Log must include request_id for vendor log correlation.
    log_msg = ext.ten_env.log_error.call_args.args[0]
    assert request_id in log_msg
    assert "service_unavailable" in log_msg

    error = ext.send_asr_error.await_args.args[0]
    assert error.metadata.get("request_id") == request_id
    assert error.metadata.get("error_type") == "service_unavailable"
    assert request_id in error.message
    assert int(error.code) == int(ModuleErrorCode.NON_FATAL_ERROR.value)

    vendor_info = ext.send_asr_error.await_args.args[1]
    assert vendor_info.code == "503"


def test_vendor_error_includes_request_id(patch_soniox_ws):
    from .conftest import create_fake_websocket_mocks, inject_websocket_mocks
    from ten_runtime import (
        AsyncExtensionTester,
        AsyncTenEnvTester,
        AudioFrame,
        Data,
        TenError,
        TenErrorCode,
    )
    from typing_extensions import override

    class RequestIdTester(AsyncExtensionTester):
        def __init__(self):
            super().__init__()
            self.sender_task: asyncio.Task[None] | None = None
            self.stopped = False
            self.request_id = "3d37a3bd-5078-47ee-a369-b204e3bbedda"

        async def audio_sender(self, ten_env: AsyncTenEnvTester):
            for _ in range(3):
                if self.stopped:
                    break
                chunk = b"\x01\x02" * 160
                audio_frame = AudioFrame.create("pcm_frame")
                audio_frame.set_property_from_json(
                    "metadata", json.dumps({"session_id": "req_id"})
                )
                audio_frame.alloc_buf(len(chunk))
                buf = audio_frame.lock_buf()
                buf[:] = chunk
                audio_frame.unlock_buf(buf)
                await ten_env.send_audio_frame(audio_frame)
                await asyncio.sleep(0.05)

        @override
        async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
            self.sender_task = asyncio.create_task(
                self.audio_sender(ten_env_tester)
            )

        @override
        async def on_data(
            self, ten_env_tester: AsyncTenEnvTester, data: Data
        ) -> None:
            if data.get_name() != "error":
                return
            payload = json.loads(data.get_property_to_json()[0])
            metadata = payload.get("metadata") or {}
            if metadata.get("request_id") != self.request_id:
                ten_env_tester.stop_test(
                    TenError.create(
                        error_code=TenErrorCode.ErrorCodeGeneric,
                        error_message=(
                            f"request_id missing in error metadata: {payload}"
                        ),
                    )
                )
                return
            if self.request_id not in payload.get("message", ""):
                ten_env_tester.stop_test(
                    TenError.create(
                        error_code=TenErrorCode.ErrorCodeGeneric,
                        error_message=(
                            f"request_id missing in error message: {payload}"
                        ),
                    )
                )
                return
            self.stopped = True
            if self.sender_task:
                self.sender_task.cancel()
            ten_env_tester.stop_test()

        @override
        async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
            self.stopped = True
            if self.sender_task:
                self.sender_task.cancel()

    async def custom_connect():
        await patch_soniox_ws.websocket_client.trigger_open()
        await asyncio.sleep(0.1)
        await patch_soniox_ws.websocket_client.trigger_error(
            503,
            "Cannot continue request (code 11)",
            request_id="3d37a3bd-5078-47ee-a369-b204e3bbedda",
            error_type="service_unavailable",
        )

    mocks = create_fake_websocket_mocks(
        patch_soniox_ws, on_connect=custom_connect
    )
    inject_websocket_mocks(patch_soniox_ws, mocks)

    property_json = {
        "params": {
            "api_key": "fake_key",
            "url": "wss://fake.soniox.com/transcribe-websocket",
            "sample_rate": 16000,
            "dump": False,
            "dump_path": ".",
        }
    }
    tester = RequestIdTester()
    tester.set_test_mode_single("soniox_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"request_id test failed: {err.error_message()}"
