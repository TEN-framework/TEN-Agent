from datetime import datetime
import json
import os
import asyncio
from typing import Any, Optional

import aiohttp
from typing_extensions import override

from .const import (
    DUMP_FILE_NAME,
    FATAL_ERROR_CODES,
    MODULE_NAME_ASR,
    MSG_TYPE_END,
    MSG_TYPE_ERROR,
    MSG_TYPE_READY,
    MSG_TYPE_TRANSCRIPT,
)
from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorVendorInfo,
    ModuleErrorCode,
)
from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
)
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_VENDOR,
)
from ten_ai_base.dumper import Dumper
from .config import SpekoASRConfig
from .reconnect_manager import ReconnectManager


class SpekoASRExtension(AsyncASRBaseExtension):
    """Streaming transcription through the Speko model router.

    The router (api.speko.ai) benchmarks STT providers per language and
    dials the best one for each session, failing over between providers
    before the first byte. This extension speaks the router's WebSocket
    wire: one JSON config frame, then bare little-endian 16-bit PCM
    binary frames, with JSON transcript frames coming back.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.connected: bool = False
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.config: SpekoASRConfig | None = None
        self.audio_dumper: Dumper | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        # Audio-timeline position where the current utterance began
        # (the previous final's end). Advanced on every final.
        self._utterance_start_ms: int = 0
        self._serving_provider: str = ""
        self.reconnect_manager: ReconnectManager | None = None

        self._message_task: Optional[asyncio.Task] = None
        # True while the router is winding a session down on purpose
        # (after an end frame or a fatal error), so the message loop can
        # tell an expected close from a mid-session drop.
        self._server_ended: bool = False
        # In-flight reconnection tasks. Reconnection always runs on its
        # own task (never awaited inline) so it cannot cancel the caller;
        # see `_schedule_reconnect`. Tracked here so tasks are not
        # garbage collected mid-flight and can be cancelled on shutdown.
        self._reconnecting: bool = False
        self._reconnect_tasks: set[asyncio.Task] = set()

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None
        # Cancel any in-flight reconnection before tearing down the
        # connection so a pending reconnect cannot re-open the socket
        # during shutdown.
        await self._cancel_reconnect_tasks()
        await self.stop_connection()

    async def _cancel_reconnect_tasks(self) -> None:
        """Cancel and drain any outstanding reconnection tasks."""
        tasks = list(self._reconnect_tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._reconnect_tasks.clear()
        self._reconnecting = False

    @override
    def vendor(self) -> str:
        """Get the name of the ASR vendor."""
        return "speko"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        return {
            "url": self.config.url if self.config else "",
            "model": "auto",
            # Provider the router dialed for this session, once known.
            "provider": self._serving_provider,
        }

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        # 0.5s base backoff: 0.5, 1, 2, 4, 8 — first retry is fast for
        # transient blips while the budget survives a ~10s outage.
        self.reconnect_manager = ReconnectManager(
            base_delay=0.5, logger=ten_env
        )

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            self.config = SpekoASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)
            ten_env.log_info(
                f"KEYPOINT vendor_config: "
                f"{self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            api_key = self.config.api_key or self.config.params.get(
                "api_key", ""
            )
            if not api_key:
                raise ValueError(
                    "Speko API key is required. Provide it in "
                    "params.api_key or set the SPEKO_API_KEY environment "
                    "variable."
                )
            self.config.validate_config()

            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
        except Exception as e:
            ten_env.log_error(f"invalid property: {e}")
            self.config = SpekoASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def start_connection(self) -> None:
        assert self.config is not None
        self.ten_env.log_info("start_connection")

        try:
            await self.stop_connection()

            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()

            if self.audio_dumper:
                await self.audio_dumper.start()

            api_key = self.config.api_key or self.config.params.get(
                "api_key", ""
            )
            headers = {
                "Authorization": f"Bearer {api_key}",
                **self.config.routing_headers(),
            }

            self.ten_env.log_info(
                f"Connecting to Speko router WebSocket: {self.config.url}",
                category=LOG_CATEGORY_VENDOR,
            )

            try:
                timeout = aiohttp.ClientTimeout(total=30)
                self.ws = await asyncio.wait_for(
                    self.session.ws_connect(
                        self.config.url, headers=headers, timeout=timeout
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                self.ten_env.log_error("WebSocket connection timeout")
                raise
            except aiohttp.WSServerHandshakeError as e:
                # A rejected handshake (401/403 for a bad key, or any
                # other refusal) is reported non-fatal and retried: the
                # ReconnectManager caps attempts and escalates to a
                # fatal error when the budget is exhausted.
                self.ten_env.log_error(
                    f"Speko router rejected the handshake: {e.status}"
                )
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message=(
                            "Speko router rejected the handshake "
                            f"(HTTP {e.status})."
                        ),
                    ),
                    ModuleErrorVendorInfo(
                        vendor=self.vendor(),
                        code=str(e.status),
                        message=str(e),
                    ),
                )
                self.connected = False
                self._schedule_reconnect()
                return
            except Exception as e:
                self.ten_env.log_error(f"WebSocket connection failed: {e}")
                raise

            # The router expects the config frame as the first text frame
            # within five seconds of the upgrade.
            await self.ws.send_str(json.dumps(self.config.config_frame()))

            self.connected = True
            self._server_ended = False
            await self.on_connected()
            self.sent_user_audio_duration_ms_before_last_reset += (
                self.audio_timeline.get_total_user_audio_duration()
            )
            self.audio_timeline.reset()

            self._message_task = asyncio.create_task(self._process_messages())

            self.ten_env.log_info(
                "start_connection completed",
                category=LOG_CATEGORY_VENDOR,
            )

        except Exception as e:
            self.ten_env.log_error(f"KEYPOINT start_connection failed: {e}")
            self.connected = False
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=str(e),
                ),
            )
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Trigger a reconnection attempt on an independent task.

        Reconnection must never be awaited from within `_message_task`.
        The reconnect path runs `start_connection()` ->
        `stop_connection()`, and `stop_connection()` cancels
        `_message_task`. Awaiting the reconnect inline would therefore
        cancel the very task executing it.

        A dead socket often trips several callers at once (send_audio
        and the message loop), so an in-flight guard keeps concurrent
        start_connection/stop_connection pairs from racing each other.
        """
        if self._reconnecting:
            self.ten_env.log_debug("reconnect already in flight, skip")
            return
        self._reconnecting = True
        task = asyncio.create_task(self._handle_reconnect())
        self._reconnect_tasks.add(task)
        task.add_done_callback(self._reconnect_tasks.discard)

    async def _process_messages(self) -> None:
        """Process incoming messages from the WebSocket."""
        assert self.ws is not None

        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_message(data)
                    except json.JSONDecodeError as e:
                        self.ten_env.log_warn(
                            f"Invalid JSON received from WebSocket: {e}",
                            category=LOG_CATEGORY_VENDOR,
                        )
                        continue

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    error_msg = f"WebSocket error: {self.ws.exception()}"
                    self.ten_env.log_error(
                        error_msg,
                        category=LOG_CATEGORY_VENDOR,
                    )
                    raise RuntimeError(error_msg)

            # aiohttp raises StopAsyncIteration on CLOSE/CLOSING/CLOSED,
            # so a normal loop exit IS the close event — close frames are
            # never yielded into the loop body.
            self.connected = False
            await self.on_disconnected()
            if not self.stopped and not self._server_ended:
                self.ten_env.log_warn(
                    "WebSocket closed unexpectedly",
                    category=LOG_CATEGORY_VENDOR,
                )
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message="WebSocket closed unexpectedly",
                    ),
                )
                self._schedule_reconnect()

        except Exception as e:
            self.connected = False
            await self.on_disconnected()
            self.ten_env.log_error(
                f"Error in message processing loop: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            if not self.stopped:
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message=(
                            "WebSocket error, attempting reconnection: "
                            f"{str(e)}"
                        ),
                    ),
                )
                self._schedule_reconnect()

    async def _handle_message(self, data: dict) -> None:
        """Dispatch one JSON frame from the router."""
        msg_type = data.get("type")
        if not msg_type:
            self.ten_env.log_warn(
                "Received message without type field",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        if msg_type == MSG_TYPE_TRANSCRIPT:
            await self._handle_transcript(data)
        elif msg_type == MSG_TYPE_READY:
            self._serving_provider = data.get("provider", "")
            self.ten_env.log_info(
                f"KEYPOINT router dialed provider: {self._serving_provider}",
                category=LOG_CATEGORY_KEY_POINT,
            )
        elif msg_type == MSG_TYPE_ERROR:
            await self._handle_error_message(data)
        elif msg_type == MSG_TYPE_END:
            # The router flushes remaining finals and closes the session
            # after an end frame (sent by finalize). Close the send gate
            # before any await so no PCM lands on a finished socket, mark
            # the coming close as expected, then complete the finalize
            # handshake and reconnect for the next turn.
            self.ten_env.log_info(
                "Router session ended",
                category=LOG_CATEGORY_VENDOR,
            )
            self.connected = False
            self._server_ended = True
            await self._finalize_end()
            if not self.stopped:
                self._schedule_reconnect()
        else:
            self.ten_env.log_debug(
                f"Unknown message type: {msg_type}",
                category=LOG_CATEGORY_VENDOR,
            )

    async def _handle_transcript(self, data: dict) -> None:
        """Handle a transcript frame."""
        assert self.config is not None

        # Reset the retry budget only once the router delivers results —
        # resetting right after the handshake would let an
        # accept-then-close failure reconnect forever.
        if self.reconnect_manager:
            self.reconnect_manager.mark_connection_successful()

        transcript_text = data.get("text", "")
        is_final = bool(data.get("isFinal", False))

        if not transcript_text:
            # An empty final arrives when finalize is requested over
            # silence — the finalize handshake must still complete.
            if is_final:
                await self._finalize_end()
            self.ten_env.log_debug(
                "Received empty transcript",
                category=LOG_CATEGORY_VENDOR,
            )
            return

        # Offset of the current router session within the whole
        # user-audio timeline (audio sent before the last reconnect).
        session_offset_ms = self.sent_user_audio_duration_ms_before_last_reset

        # The router does not carry word timings on the socket, so an
        # utterance is bounded on the audio timeline: it starts where
        # the previous final ended and extends to the audio position of
        # the transcript in hand (clamped positive — a transcript
        # implies audio was heard).
        total_audio_sent_ms = (
            self.audio_timeline.get_total_user_audio_duration()
            + session_offset_ms
        )
        start_ms = self._utterance_start_ms
        duration_ms = max(1, total_audio_sent_ms - start_ms)

        asr_result = ASRResult(
            text=transcript_text,
            final=is_final,
            start_ms=start_ms,
            duration_ms=duration_ms,
            language=self.config.report_language(data.get("language")),
            words=None,
        )

        await self.send_asr_result(asr_result)
        if is_final:
            self._utterance_start_ms = total_audio_sent_ms
            await self._finalize_end()

    async def _handle_error_message(self, data: dict) -> None:
        """Handle an error frame from the router."""
        error_code = str(data.get("code", "unknown"))
        error_info = data.get("message", "Unknown error")

        self.ten_env.log_error(
            f"Router error received: {error_info} (code: {error_code})",
            category=LOG_CATEGORY_VENDOR,
        )

        is_fatal = error_code in FATAL_ERROR_CODES
        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=(
                    ModuleErrorCode.FATAL_ERROR.value
                    if is_fatal
                    else ModuleErrorCode.NON_FATAL_ERROR.value
                ),
                message=str(error_info),
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=error_code,
                message=str(error_info),
            ),
        )

        if is_fatal and self.ws is not None:
            # A fatal code means retrying with the same config cannot
            # succeed — stop feeding the socket and let it close without
            # scheduling a reconnect. (Closing here ends the message
            # loop; _server_ended suppresses the unexpected-close path.)
            self.connected = False
            self._server_ended = True
            await self.ws.close()

    async def _handle_reconnect(self):
        """Run the reconnection chain via the ReconnectManager.

        The whole chain lives in this one task (guarded by
        `_reconnecting`): a failed attempt loops to the next backoff
        step here rather than scheduling a fresh task from inside
        `start_connection`, whose schedule calls are absorbed by the
        in-flight guard while the chain runs.
        """
        try:
            await self._handle_reconnect_inner()
        finally:
            self._reconnecting = False

    async def _handle_reconnect_inner(self):
        if not self.reconnect_manager:
            self.ten_env.log_error("ReconnectManager not initialized")
            return

        while not self.stopped and not self._safe_is_connected():
            if not self.reconnect_manager.can_retry():
                self.ten_env.log_warn("No more reconnection attempts allowed")
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.FATAL_ERROR.value,
                        message="No more reconnection attempts allowed",
                    )
                )
                return

            success = await self.reconnect_manager.handle_reconnect(
                connection_func=self.start_connection,
                error_handler=self.send_asr_error,
            )

            if success and self._safe_is_connected():
                self.ten_env.log_debug("Reconnection succeeded")
                return

            info = self.reconnect_manager.get_attempts_info()
            self.ten_env.log_debug(
                f"Reconnection attempt failed. Status: {info}"
            )

    @override
    async def finalize(self, session_id: str | None) -> None:
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        self.ten_env.log_info(
            f"vendor_cmd: finalize start at {self.last_finalize_timestamp}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._send_finalize()

    async def _finalize_end(self) -> None:
        """Complete the finalize handshake if one is pending."""
        if self.last_finalize_timestamp != 0:
            timestamp = int(datetime.now().timestamp() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_debug(
                f"KEYPOINT finalize end at {timestamp}, latency: {latency}"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def _send_finalize(self) -> None:
        """Flush pending audio through the router.

        The router has no flush-in-place frame: an end frame makes it
        drain the provider, emit remaining finals, send its own end
        frame, and close the session. The end handler then completes
        the finalize handshake and reconnects for the next turn;
        buffered audio is retained client-side meanwhile (Keep mode).
        """
        if not self.is_connected() or self.ws is None:
            # No router session to flush, so complete the handshake
            # locally — otherwise asr_finalize_end is never emitted and
            # the turn stalls.
            self.ten_env.log_warn(
                "speko finalize requested while disconnected",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._finalize_end()
            return
        try:
            await self.ws.send_str(json.dumps({"type": MSG_TYPE_END}))
            self.ten_env.log_debug("speko finalize (end frame) sent")
        except Exception as e:
            self.ten_env.log_error(f"Error sending speko finalize: {e}")
            await self._finalize_end()
            if not self.stopped:
                self._schedule_reconnect()

    async def stop_connection(self) -> None:
        """Stop the router connection."""
        self.connected = False
        try:
            if self._message_task and not self._message_task.done():
                self._message_task.cancel()
                try:
                    await self._message_task
                except asyncio.CancelledError:
                    pass

            if self.ws and not self.ws.closed:
                await self.ws.close()
                self.ws = None

            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

            self.ten_env.log_info("speko connection stopped")
        except Exception as e:
            self.ten_env.log_error(f"Error stopping speko connection: {e}")

    @override
    def is_connected(self) -> bool:
        return self.connected and self.ws is not None and not self.ws.closed

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return self.config.sample_rate

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        assert self.config is not None

        # Guard the send instead of asserting the socket exists: after a
        # failed reconnect `self.ws` can be None, and an assert would
        # raise (or be stripped under -O) instead of failing gracefully.
        if not self.is_connected() or self.ws is None:
            self.ten_env.log_error("Speko router connection not established")
            return False

        buf = frame.lock_buf()
        try:
            audio_data = bytes(buf)

            if self.audio_dumper:
                await self.audio_dumper.push_bytes(audio_data)

            self.audio_timeline.add_user_audio(
                int(len(buf) / (self.config.sample_rate / 1000 * 2))
            )

            # The router forwards caller bytes untouched: bare s16le PCM
            # binary frames, no WAV header (a header would be transcribed
            # as noise — byte rate comes from the config frame).
            await self.ws.send_bytes(audio_data)
            return True

        except Exception as e:
            self.ten_env.log_error(f"Error sending audio: {e}")
            if not self.stopped:
                self._schedule_reconnect()
            return False
        finally:
            frame.unlock_buf(buf)
