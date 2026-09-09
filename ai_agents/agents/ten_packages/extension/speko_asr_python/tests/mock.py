#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from types import SimpleNamespace
import asyncio
import threading

import pytest
from unittest.mock import patch
import aiohttp


@pytest.fixture(scope="function")
def patch_speko_ws():
    """Patch the aiohttp WebSocket client used in the Speko extension.

    The extension uses aiohttp.ClientSession.ws_connect, sends one JSON
    config frame, then iterates over the WebSocket for incoming router
    frames while pushing binary PCM out.

    Each ws_connect returns a FRESH mock socket (the router closes the
    session after an end frame, so reconnects are part of the normal
    flow and tests must be able to observe them). Sockets are collected
    on `sockets`; `ws` stays an alias for the first one. A socket only
    delivers frames added after its creation, so a reconnected socket
    never replays history.
    """

    messages = []
    messages_lock = threading.Lock()
    sockets = []

    class MockWebSocketMessage:
        """Mock aiohttp WebSocket message."""

        def __init__(self, msg_type, data=None, exception=None):
            self.type = msg_type
            self.data = data
            self._exception = exception

        def exception(self):
            return self._exception

    class MockWebSocket:
        def __init__(self, start_index: int = 0) -> None:
            self.sent_messages: list[str] = []
            self.sent_bytes: list[bytes] = []
            self.closed: bool = False
            self.connect_headers = None
            self._start_index = start_index
            self._exception = None

        async def send_str(self, data: str) -> bool:
            self.sent_messages.append(data)
            return True

        async def send_bytes(self, data: bytes) -> bool:
            self.sent_bytes.append(data)
            return True

        async def close(self) -> bool:
            self.closed = True
            return True

        def exception(self):
            return self._exception

        def __aiter__(self):
            async def _gen():
                # Deliver frames added after this socket was created,
                # until the socket is closed. New frames may arrive from
                # other threads.
                processed_count = self._start_index
                while not self.closed:
                    with messages_lock:
                        current_messages = messages[processed_count:]
                        processed_count = len(messages)

                    if current_messages:
                        for msg in current_messages:
                            yield msg
                    else:
                        await asyncio.sleep(0.1)

            return _gen()

    class MockSession:
        def __init__(self, *args, **kwargs) -> None:
            self.closed: bool = False

        async def ws_connect(self, url, headers=None, timeout=None):
            with messages_lock:
                start_index = len(messages)
            if not sockets:
                # The first socket sees the whole feed so tests may
                # queue frames before the connection lands.
                start_index = 0
            new_ws = MockWebSocket(start_index=start_index)
            new_ws.connect_headers = headers
            sockets.append(new_ws)
            return new_ws

        async def close(self) -> None:
            self.closed = True

    with patch(
        "ten_packages.extension.speko_asr_python.extension."
        "aiohttp.ClientSession",
        MockSession,
    ):

        def add_message(msg):
            """Thread-safe helper to add messages."""
            with messages_lock:
                messages.append(msg)

        class FixtureNamespace(SimpleNamespace):
            @property
            def ws(self):
                return sockets[0] if sockets else None

        fixture_obj = FixtureNamespace(
            sockets=sockets,
            messages=messages,
            messages_lock=messages_lock,
            add_message=add_message,
            WSMsgType=aiohttp.WSMsgType,
            MockWebSocketMessage=MockWebSocketMessage,
        )

        yield fixture_obj
