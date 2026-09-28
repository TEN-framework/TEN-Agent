import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlencode

import websockets
from websockets.protocol import State

from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR
from ten_ai_base.timeline import AudioTimeline
from ten_runtime import AsyncTenEnv


class XAIASRRecognitionCallback(ABC):
    @abstractmethod
    async def on_open(self):
        pass

    @abstractmethod
    async def on_partial_result(self, message_data: dict[str, Any]):
        pass

    @abstractmethod
    async def on_done(self, message_data: dict[str, Any]):
        pass

    @abstractmethod
    async def on_error(self, error_msg: str, error_code: int | None = None):
        pass

    @abstractmethod
    async def on_close(self):
        pass


class XAIASRRecognition:
    def __init__(
        self,
        api_key: str,
        audio_timeline: AudioTimeline,
        ten_env: AsyncTenEnv,
        config: dict[str, Any],
        callback: XAIASRRecognitionCallback,
    ):
        self.api_key = api_key
        self.audio_timeline = audio_timeline
        self.ten_env = ten_env
        self.config = config or {}
        self.callback = callback
        self.websocket = None
        self.is_started = False
        self.ready_event = asyncio.Event()
        self.done_event = asyncio.Event()
        self.done_payload: dict[str, Any] | None = None
        self._message_task: asyncio.Task | None = None
        self._open_notified = False

    def _build_url(self) -> str:
        base_url = self.config.get("base_url", "wss://api.x.ai/v1/stt")
        query_params: dict[str, Any] = {}
        for key in (
            "sample_rate",
            "encoding",
            "interim_results",
            "endpointing",
            "language",
            "multichannel",
            "channels",
            "diarize",
        ):
            value = self.config.get(key)
            if value is not None:
                query_params[key] = (
                    str(value).lower() if isinstance(value, bool) else value
                )
        return f"{base_url}?{urlencode(query_params, doseq=True)}"

    async def start(self, timeout: int = 10) -> None:
        url = self._build_url()
        self.ten_env.log_info(f"Connecting to xAI STT: {url}")
        self.websocket = await websockets.connect(
            url,
            additional_headers={"Authorization": f"Bearer {self.api_key}"},
            open_timeout=timeout,
        )
        try:
            self.is_started = True
            self.ready_event.clear()
            self.done_event.clear()
            self.done_payload = None
            self._open_notified = False
            first_message = await asyncio.wait_for(
                self.websocket.recv(), timeout=timeout
            )
            if isinstance(first_message, bytes):
                raise RuntimeError(
                    "Unexpected binary message during xAI STT startup"
                )
            first_event = json.loads(first_message)
            self.ten_env.log_debug(
                f"vendor_result: startup: {first_message}",
                category=LOG_CATEGORY_VENDOR,
            )
            if first_event.get("type") != "transcript.created":
                raise RuntimeError(
                    f"Unexpected xAI STT startup event: "
                    f"type={first_event.get('type')!r}, payload={first_message!r}"
                )
            self.ready_event.set()
            self._open_notified = True
            await self.callback.on_open()
            self._message_task = asyncio.create_task(self._message_handler())
        except Exception:
            self.is_started = False
            if self.websocket is not None:
                try:
                    await self.websocket.close()
                except Exception:
                    pass
                self.websocket = None
            raise

    async def _message_handler(self) -> None:
        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    continue
                event = json.loads(message)
                self.ten_env.log_debug(
                    f"vendor_result: on_recognized: {message}",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )
                event_type = event.get("type", "")
                if event_type == "transcript.created":
                    self.ready_event.set()
                    if not self._open_notified:
                        self._open_notified = True
                        await self.callback.on_open()
                elif event_type == "transcript.partial":
                    await self.callback.on_partial_result(event)
                elif event_type == "transcript.done":
                    self.done_payload = event
                    self.done_event.set()
                    await self.callback.on_done(event)
                elif event_type == "error":
                    await self.callback.on_error(
                        str(event.get("message", "Unknown error")),
                        event.get("code"),
                    )
        except websockets.exceptions.ConnectionClosed as e:
            self.ten_env.log_info(f"xAI STT websocket closed: {e}")
        except Exception as e:
            await self.callback.on_error(
                f"WebSocket message handler error: {e}"
            )
        finally:
            self.is_started = False
            await self.callback.on_close()

    async def send_audio_frame(self, audio_data: bytes) -> None:
        if not self.websocket or not self.is_connected():
            raise RuntimeError("WebSocket not connected")
        await self.ready_event.wait()
        sample_rate = int(self.config.get("sample_rate", 16000))
        encoding = str(self.config.get("encoding", "pcm")).lower()
        channels = int(self.config.get("channels", 1) or 1)
        bytes_per_sample = 1 if encoding in {"mulaw", "alaw"} else 2
        bytes_per_ms = sample_rate / 1000 * bytes_per_sample * channels
        duration_ms = (
            int(len(audio_data) / bytes_per_ms) if bytes_per_ms > 0 else 0
        )
        self.audio_timeline.add_user_audio(duration_ms)
        await self.websocket.send(audio_data)

    async def send_audio_done(self) -> None:
        if self.websocket and self.is_connected():
            await self.websocket.send(json.dumps({"type": "audio.done"}))

    async def wait_for_done(self, timeout_ms: int) -> dict[str, Any] | None:
        try:
            await asyncio.wait_for(self.done_event.wait(), timeout_ms / 1000)
        except asyncio.TimeoutError:
            return None
        return self.done_payload

    async def close(self) -> None:
        if self.websocket:
            try:
                if self.websocket.state == State.OPEN:
                    await self.websocket.close()
            except Exception as e:
                self.ten_env.log_info(f"Error closing websocket: {e}")
        if self._message_task and not self._message_task.done():
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
        self.is_started = False

    def is_connected(self) -> bool:
        return (
            self.is_started
            and self.websocket is not None
            and self.websocket.state == State.OPEN
        )
