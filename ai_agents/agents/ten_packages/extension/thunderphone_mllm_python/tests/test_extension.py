#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Drives the extension through the TEN runtime.

`test_extension_loads` runs without credentials: the addon registers under
its manifest name, `mllm-interface.json` resolves, properties are injected
and `on_init` validates them. With `THUNDERPHONE_API_KEY` set,
`test_session_becomes_ready` opens a real (billed) inline session and waits
for `mllm_server_session_ready`.
"""

import asyncio
import json
import os

import pytest
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
)

ADDON_NAME = "thunderphone_mllm_python"
API_KEY = os.environ.get("THUNDERPHONE_API_KEY", "")

requires_api_key = pytest.mark.skipif(
    not API_KEY, reason="THUNDERPHONE_API_KEY is not set"
)


def properties(**overrides) -> str:
    props = {
        "api_key": API_KEY or "sk_live_invalid_key_used_by_the_load_check",
        "prompt": "You are a test assistant. Say hello and nothing else.",
        "language": "en",
    }
    props.update(overrides)
    return json.dumps(props)


class SessionReadyTester(AsyncExtensionTester):
    """Waits for `mllm_server_session_ready` or a timeout."""

    def __init__(self, timeout: float) -> None:
        super().__init__()
        self.timeout = timeout
        self.session_ready = False
        self._watchdog: asyncio.Task | None = None

    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        self._watchdog = asyncio.create_task(self._stop_after_timeout(ten_env))

    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        if data.get_name() == "mllm_server_session_ready":
            self.session_ready = True
            if self._watchdog is not None:
                self._watchdog.cancel()
            ten_env.stop_test()

    async def _stop_after_timeout(self, ten_env: AsyncTenEnvTester) -> None:
        await asyncio.sleep(self.timeout)
        ten_env.stop_test()


def test_extension_loads():
    tester = SessionReadyTester(timeout=5.0)
    tester.set_test_mode_single(ADDON_NAME, properties(api_key="sk_live_invalid_key_used_by_the_load_check"))
    err = tester.run()
    assert err is None, err.error_message()
    # An invalid key is refused at the WebSocket handshake; the extension
    # logs it and stops instead of raising, so no session becomes ready.
    assert tester.session_ready is False


@requires_api_key
def test_session_becomes_ready():
    tester = SessionReadyTester(timeout=20.0)
    tester.set_test_mode_single(ADDON_NAME, properties())
    err = tester.run()
    assert err is None, err.error_message()
    assert tester.session_ready, "no mllm_server_session_ready within 20 s"
