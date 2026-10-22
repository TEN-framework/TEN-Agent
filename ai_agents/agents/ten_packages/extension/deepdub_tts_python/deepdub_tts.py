import asyncio
import base64
import json
import time
from typing import Awaitable, Callable, Optional

import websockets

from ten_runtime import AsyncTenEnv

from .config import DeepdubTTSConfig


class DeepdubTTSException(Exception):
    def __init__(self, message: str, code: int = -1):
        super().__init__(message)
        self.message = message
        self.code = code


AudioCb = Callable[[bytes], Awaitable[None]]
FinishCb = Callable[[], Awaitable[None]]
ErrorCb = Callable[[DeepdubTTSException], Awaitable[None]]


class DeepdubStreamingClient:
    """One persistent text-streaming WebSocket per instance.

    Connect → recv status → send `stream-config` → push `stream-text` frames as
    they arrive → receive interleaved audio and `isFinished` boundaries.
    """

    def __init__(
        self,
        config: DeepdubTTSConfig,
        ten_env: Optional[AsyncTenEnv],
        on_audio: AudioCb,
        on_finish: FinishCb,
        on_error: ErrorCb,
    ):
        self.config = config
        self.ten_env = ten_env
        self.on_audio = on_audio
        self.on_finish = on_finish
        self.on_error = on_error

        self._ws: Optional[websockets.ClientConnection] = None
        self._ready = asyncio.Event()
        self._stopping = False
        self._discarding = False
        self._reader_task: Optional[asyncio.Task] = None
        self._supervisor_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()
        self._send_lock = asyncio.Lock()

    # ---------- lifecycle ----------

    async def start(self) -> None:
        self._supervisor_task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self._stopping = True
        await self._close_ws()
        if self._supervisor_task:
            await self._stopped.wait()

    async def cancel(self) -> None:
        """Drop the in-flight stream; reconnect from scratch."""
        self._discarding = True
        await self._close_ws()
        # supervisor will reconnect

    # ---------- public send API ----------

    async def wait_ready(self, timeout: float = 10.0) -> None:
        await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    async def send_text(self, text: str) -> None:
        if not text:
            return
        await self.wait_ready()
        async with self._send_lock:
            assert self._ws is not None
            await self._ws.send(
                json.dumps({"action": "stream-text", "data": {"text": text}})
            )

    async def send_cancel(self) -> None:
        async with self._send_lock:
            if self._ws is not None:
                try:
                    await self._ws.send(json.dumps({"action": "cancel"}))
                except Exception:
                    pass

    # ---------- internals ----------

    async def _close_ws(self) -> None:
        ws = self._ws
        self._ws = None
        self._ready.clear()
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None

    async def _supervise(self) -> None:
        backoff = 0.5
        while not self._stopping:
            try:
                await self._connect_and_run()
                backoff = 0.5
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_warn(f"deepdub stream loop error: {e}")
                try:
                    await self.on_error(
                        e
                        if isinstance(e, DeepdubTTSException)
                        else DeepdubTTSException(str(e))
                    )
                except Exception:
                    pass
                if self._stopping:
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
            finally:
                self._discarding = False
                await self._close_ws()
        self._stopped.set()

    async def _connect_and_run(self) -> None:
        headers = {"x-api-key": self.config.api_key}
        if self.ten_env:
            self.ten_env.log_info("deepdub stream WS connecting")
        t0 = time.time()
        async with websockets.connect(
            self.config.url,
            additional_headers=headers,
            max_size=1024 * 1024 * 16,
        ) as ws:
            self._ws = ws
            # Initial status frame.
            status_raw = await ws.recv()
            status = json.loads(status_raw)
            if status.get("action") == "error":
                raise DeepdubTTSException(
                    status.get("message", "connection rejected")
                )
            # Send stream-config (pre-warm).
            cfg = {
                "model": self.config.model,
                "locale": self.config.locale,
                "voicePromptId": self.config.voice_prompt_id,
                "format": self.config.format,
                "sampleRate": self.config.sample_rate,
                "acceptEmojis": self.config.accept_emojis,
                "temperature": self.config.temperature,
                "variance": self.config.variance,
                "tempo": self.config.tempo,
                "promptBoost": self.config.prompt_boost,
            }
            await ws.send(
                json.dumps({"action": "stream-config", "config": cfg})
            )
            self._ready.set()
            if self.ten_env:
                self.ten_env.log_info(
                    f"deepdub stream WS ready ({int((time.time()-t0)*1000)}ms)"
                )
            self._keepalive_task = asyncio.create_task(self._keepalive())
            await self._read_loop(ws)

    async def _keepalive(self) -> None:
        try:
            while not self._stopping and self._ws is not None:
                await asyncio.sleep(self.config.keepalive_interval_seconds)
                if self._ws is None:
                    return
                async with self._send_lock:
                    if self._ws is not None:
                        try:
                            await self._ws.send(json.dumps({"action": "ping"}))
                        except Exception:
                            return
        except asyncio.CancelledError:
            return

    async def _read_loop(self, ws: websockets.ClientConnection) -> None:
        while not self._stopping:
            raw = await ws.recv()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            action = msg.get("action")
            if action in ("pong", "status"):
                continue
            err = msg.get("error")
            if err and not msg.get("generationId"):
                await self.on_error(DeepdubTTSException(str(err)))
                continue
            if self._discarding:
                # Drop frames belonging to the cancelled run.
                continue
            data = msg.get("data")
            if data:
                try:
                    pcm = base64.b64decode(data)
                except Exception:
                    pcm = b""
                if pcm:
                    await self.on_audio(pcm)
            if msg.get("isFinished"):
                await self.on_finish()
