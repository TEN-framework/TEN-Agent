#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import base64
import json
from typing import TYPE_CHECKING, Any, AsyncGenerator
from urllib.parse import urlencode

import aiohttp

from .struct import (
    ClientToServerMessage,
    InputAudioBufferAppend,
    ServerToClientMessage,
    parse_server_message,
    to_json,
)

if TYPE_CHECKING:
    from ten_runtime import AsyncTenEnv


def smart_str(s: str, max_field_len: int = 128) -> str:
    """Parse a JSON frame and truncate its audio/delta field for logging."""
    try:
        data = json.loads(s)
        if "delta" in data:
            key = "delta"
        elif "audio" in data:
            key = "audio"
        else:
            return s
        if isinstance(data[key], str) and len(data[key]) > max_field_len:
            data[key] = data[key][:max_field_len] + "..."
        return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        return s


def build_url(base_url: str, path: str, query: dict[str, str]) -> str:
    """``base_url + path`` with ``query`` merged into any query the path has."""
    url = base_url.rstrip("/") + path
    if not query:
        return url
    return url + ("&" if "?" in url else "?") + urlencode(query)


class ThunderPhoneConnection:
    """One WebSocket to ThunderPhone's realtime endpoint, i.e. one call."""

    def __init__(
        self,
        ten_env: "AsyncTenEnv",
        base_url: str,
        path: str,
        api_key: str,
        query: dict[str, str],
        verbose: bool = False,
    ):
        self.ten_env = ten_env
        self.url = build_url(base_url, path, query)
        self.api_key = api_key
        self.verbose = verbose
        self.websocket: aiohttp.ClientWebSocketResponse | None = None
        self.session = aiohttp.ClientSession()

    async def connect(self) -> None:
        self.websocket = await self.session.ws_connect(
            url=self.url,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    @property
    def close_code(self) -> int | None:
        return self.websocket.close_code if self.websocket else None

    async def send_audio_data(self, audio_data: bytes) -> None:
        """audio_data is pcm16 mono little-endian at the configured rate."""
        await self.send_request(
            InputAudioBufferAppend(
                audio=base64.b64encode(audio_data).decode("utf-8")
            )
        )

    async def send_request(self, message: ClientToServerMessage) -> None:
        assert self.websocket is not None
        message_str = to_json(message)
        if self.verbose:
            self.ten_env.log_info(f"-> {smart_str(message_str)}")
        await self.websocket.send_str(message_str)

    async def listen(self) -> AsyncGenerator[ServerToClientMessage, None]:
        assert self.websocket is not None
        try:
            async for msg in self.websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if self.verbose:
                        self.ten_env.log_info(f"<- {smart_str(msg.data)}")
                    parsed = self.handle_server_message(msg.data)
                    if parsed is not None:
                        yield parsed
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.ten_env.log_error(
                        f"Error during receive: {self.websocket.exception()}"
                    )
                    break
        except asyncio.CancelledError:
            self.ten_env.log_info("Receive messages task cancelled")

    def handle_server_message(self, message: str) -> ServerToClientMessage | None:
        try:
            return parse_server_message(message)
        except Exception as e:  # a malformed frame must not end the call
            self.ten_env.log_warn(f"Error handling message {e}")
            return None

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        if not self.session.closed:
            await self.session.close()
