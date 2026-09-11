from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

import websockets
from ten_runtime import AsyncTenEnv
from websockets.legacy.client import WebSocketClientProtocol

from .config import BytedanceMLLMConfig
from .protocol import (
    ClientEvent,
    MessageType,
    Serialization,
    ServerMessage,
    build_client_event,
    parse_server_message,
)


def _truncate_payload(payload: bytes, limit: int = 160) -> str:
    if len(payload) <= limit:
        return payload.decode("utf-8", errors="replace")
    return payload[:limit].decode("utf-8", errors="replace") + "..."


class BytedanceRealtimeConnection:
    def __init__(
        self,
        ten_env: AsyncTenEnv,
        config: BytedanceMLLMConfig,
        session_id: str,
    ):
        self.ten_env = ten_env
        self.config = config
        self.session_id = session_id
        self.websocket: WebSocketClientProtocol | None = None

    async def connect(self) -> None:
        connect_id = str(uuid.uuid4())
        headers = {
            "X-Api-App-ID": self.config.app_id,
            "X-Api-Access-Key": self.config.access_key,
            "X-Api-Resource-Id": self.config.resource_id,
            "X-Api-App-Key": self.config.app_key,
            "X-Api-Connect-Id": connect_id,
        }

        self.ten_env.log_info(
            f"[Doubao] connecting to {self.config.api_url}, "
            f"connect_id={connect_id}"
        )
        self.websocket = await websockets.connect(
            self.config.api_url,
            additional_headers=headers,
            max_size=100_000_000,
            compression=None,
        )

    async def send_start_connection(self) -> None:
        await self._send(
            build_client_event(ClientEvent.START_CONNECTION, payload={})
        )

    async def send_finish_connection(self) -> None:
        await self._send(
            build_client_event(ClientEvent.FINISH_CONNECTION, payload={})
        )

    async def send_start_session(self, payload: dict) -> None:
        await self._send(
            build_client_event(
                ClientEvent.START_SESSION,
                payload=payload,
                session_id=self.session_id,
            )
        )

    async def send_finish_session(self) -> None:
        await self._send(
            build_client_event(
                ClientEvent.FINISH_SESSION,
                payload={},
                session_id=self.session_id,
            )
        )

    async def send_audio_data(self, audio_data: bytes) -> None:
        await self._send(
            build_client_event(
                ClientEvent.TASK_REQUEST,
                payload=audio_data,
                session_id=self.session_id,
                message_type=MessageType.AUDIO_ONLY_REQUEST,
                serialization=Serialization.RAW,
            )
        )

    async def send_text_query(self, text: str) -> None:
        await self._send(
            build_client_event(
                ClientEvent.CHAT_TEXT_QUERY,
                payload={"content": text},
                session_id=self.session_id,
            )
        )

    async def send_client_interrupt(self) -> None:
        await self._send(
            build_client_event(
                ClientEvent.CLIENT_INTERRUPT,
                payload={},
                session_id=self.session_id,
            )
        )

    async def listen(self) -> AsyncGenerator[ServerMessage, None]:
        if self.websocket is None:
            raise RuntimeError("websocket is not connected")

        async for message in self.websocket:
            if isinstance(message, str):
                raise RuntimeError(message)
            parsed = parse_server_message(message)
            if self.config.verbose:
                self.ten_env.log_info(
                    f"[Doubao] <- event={parsed.event} "
                    f"payload={_truncate_payload(parsed.payload)}"
                )
            yield parsed

    async def close(self) -> None:
        if self.websocket is None:
            return
        await self.websocket.close()
        self.websocket = None

    async def _send(self, message: bytes) -> None:
        if self.websocket is None:
            raise RuntimeError("websocket is not connected")
        if self.config.verbose:
            self.ten_env.log_info(
                f"[Doubao] -> {json.dumps(list(message[:32]))}"
            )
        await self.websocket.send(message)
