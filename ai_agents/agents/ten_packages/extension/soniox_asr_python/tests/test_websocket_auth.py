import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ..websocket import SonioxWebsocketClient


@pytest.mark.asyncio
async def test_connect_sends_api_key_in_authorization_header():
    client = SonioxWebsocketClient(
        "wss://stt-rt.soniox.com/transcribe-websocket",
        json.dumps({"model": "stt-rt-preview"}),
        "test-api-key",
    )
    client._work = AsyncMock()
    ws = MagicMock()
    ws.send = AsyncMock()

    class WebSocketContext:
        async def __aenter__(self):
            return ws

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    with patch(
        "soniox_asr_python.websocket.websockets.connect",
        return_value=WebSocketContext(),
    ) as connect:
        await client.connect()

    connect.assert_called_once_with(
        "wss://stt-rt.soniox.com/transcribe-websocket",
        additional_headers={"Authorization": "Bearer test-api-key"},
    )
    ws.send.assert_awaited_once_with(json.dumps({"model": "stt-rt-preview"}))
