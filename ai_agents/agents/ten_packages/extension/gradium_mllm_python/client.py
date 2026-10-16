"""
Websocket client for Gradium's real-time speech-to-speech translation API.

Protocol, confirmed directly by Gradium (2026-08-20) for /api/speech/s2s:
  connect -> send {"type": "setup", ...} -> wait for {"type": "ready"} ->
  stream {"type": "audio", "audio": <base64 pcm16>} both ways ->
  {"type": "text", ...} carries translated output text (no separate
  source-language transcript) -> {"type": "end_of_stream"} closes the turn
  -> {"type": "error", ...} on failure. No "vad" event on this endpoint.
"""

import asyncio
import base64
import json
from typing import Any, AsyncIterator

import websockets
from ten_runtime import AsyncTenEnv

from .config import GradiumMLLMConfig
from .const import WS_MSG_TYPE_ERROR, WS_MSG_TYPE_READY


class GradiumS2SClient:
    """Thin duplex websocket wrapper -- no reconnect/backoff logic here; that lives in extension.py."""

    def __init__(self, config: GradiumMLLMConfig, ten_env: AsyncTenEnv):
        self.config = config
        self.ten_env = ten_env
        self.ws: Any | None = None

    async def connect(self, ready_timeout: float = 10.0) -> None:
        headers = {"x-api-key": self.config.api_key}
        url = self.config.websocket_url()
        self.ten_env.log_info(f"[gradium] connecting to {url}")

        self.ws = await websockets.connect(url, additional_headers=headers)

        await self._send_json(self.config.setup_message())
        await self._wait_for_ready(ready_timeout)

    async def _wait_for_ready(self, timeout: float) -> None:
        assert self.ws is not None
        raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        message = self._parse(raw)
        if message is None:
            raise RuntimeError("Gradium sent an unparseable message before ready")
        if message.get("type") == WS_MSG_TYPE_ERROR:
            raise RuntimeError(message.get("message", "Gradium setup failed"))
        if message.get("type") != WS_MSG_TYPE_READY:
            raise RuntimeError(
                f"Expected 'ready' from Gradium, got {message.get('type')!r}"
            )

    async def send_audio(self, pcm_bytes: bytes) -> None:
        assert self.ws is not None
        audio_b64 = base64.b64encode(pcm_bytes).decode("utf-8")
        await self._send_json({"type": "audio", "audio": audio_b64})

    async def send_end_of_stream(self) -> None:
        if self.ws is not None:
            await self._send_json({"type": "end_of_stream"})

    async def _send_json(self, payload: dict[str, Any]) -> None:
        assert self.ws is not None
        await self.ws.send(json.dumps(payload))

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        assert self.ws is not None
        async for raw in self.ws:
            message = self._parse(raw)
            if message is not None:
                yield message

    def _parse(self, raw: str | bytes) -> dict[str, Any] | None:
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except Exception as e:
            self.ten_env.log_warn(f"[gradium] failed to parse message: {e}")
            return None

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
