#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from types import SimpleNamespace
import asyncio
import threading

import pytest
from unittest.mock import patch, MagicMock
import aiohttp


@pytest.fixture(scope="function")
def patch_smallest_ws():
    """Patch Smallest ASR's aiohttp WebSocket client used in the extension.

    The Smallest AI Pulse extension uses aiohttp.ClientSession.ws_connect and
    then iterates over the returned WebSocket for incoming messages.

    This fixture:
    - Replaces aiohttp.ClientSession with a lightweight mock session
    - Provides a mock WebSocket object with:
      - async send_str (finalize control message)
      - async send_bytes (binary PCM audio)
      - async close
      - async iterator matching aiohttp's close-frame semantics
    - Exposes the WebSocket and message list so tests can control behavior.
    """

    messages = []
    messages_lock = threading.Lock()

    class MockWebSocketMessage:
        """Mock aiohttp WebSocket message."""

        def __init__(self, msg_type, data=None, exception=None):
            self.type = msg_type
            self.data = data
            self._exception = exception

        def exception(self):
            return self._exception

    class MockWebSocket:
        def __init__(self) -> None:
            self.sent_messages: list[str] = []
            self.sent_bytes: list[bytes] = []
            self.closed: bool = False
            self.close_code: int | None = None
            self._exception = None

        def reset(self) -> None:
            """Prepare the shared socket for a fresh ws_connect call."""
            self.closed = False
            self.close_code = None
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
                # Keep iterating until closed, allowing messages to be added from other threads
                processed_count = 0
                while not self.closed:
                    with messages_lock:
                        # Get new messages that haven't been processed yet
                        current_messages = messages[processed_count:]
                        processed_count = len(messages)

                    if current_messages:
                        for msg in current_messages:
                            # ClientWebSocketResponse.__anext__ consumes close
                            # frames and ends iteration instead of yielding
                            # them to an async-for loop.
                            if msg.type in (
                                aiohttp.WSMsgType.CLOSE,
                                aiohttp.WSMsgType.CLOSING,
                                aiohttp.WSMsgType.CLOSED,
                            ):
                                self.closed = True
                                self.close_code = (
                                    msg.data
                                    if isinstance(msg.data, int)
                                    else 1000
                                )
                                return
                            yield msg
                    else:
                        # Small sleep to avoid busy waiting when no messages
                        await asyncio.sleep(0.1)

            return _gen()

    class MockSession:
        def __init__(self, *args, **kwargs) -> None:
            self.closed: bool = False

        async def ws_connect(self, url, headers=None, timeout=None):
            return prepare_connection()

        async def close(self) -> None:
            self.closed = True

    ws = MockWebSocket()

    def prepare_connection():
        """Reset the shared socket and discard the previous session's queue."""
        ws.reset()
        with messages_lock:
            messages.clear()
        return ws

    # Patch the ClientSession used inside the Smallest AI extension module
    with patch(
        "ten_packages.extension.smallest_asr_python.extension.aiohttp.ClientSession",
        MockSession,
    ):

        def add_message(msg):
            """Thread-safe helper to add messages."""
            with messages_lock:
                messages.append(msg)

        fixture_obj = SimpleNamespace(
            ws=ws,
            messages=messages,
            messages_lock=messages_lock,  # Expose lock for thread-safe access
            prepare_connection=prepare_connection,
            add_message=add_message,  # Helper function to add messages thread-safely
            WSMsgType=aiohttp.WSMsgType,  # Expose WSMsgType for tests
            MockWebSocketMessage=MockWebSocketMessage,  # Helper for creating messages
        )

        yield fixture_obj
