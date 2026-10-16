#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import copy
import json
import time
from pathlib import Path
from typing import Any

from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeDiscard,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import (
    ModuleConnectionStatus,
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_ai_base.struct import ASRWord
from ten_runtime import AsyncTenEnv, AudioFrame, Data
from typing_extensions import override

from .client import SpekoASRClient, SpekoRouterError
from .config import SpekoASRConfig, safe_error, safe_url


class SpekoASRExtension(AsyncASRBaseExtension):
    RECONNECT_DELAYS = (0.5, 1.0, 2.0, 4.0, 4.0)

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: SpekoASRConfig | None = None
        self.client: SpekoASRClient | None = None
        self.audio_dumper: Dumper | None = None
        self._init_failed = False
        self._connect_started_at = 0.0
        self._total_audio_bytes = 0
        self._sent_audio_bytes = 0
        self._dropped_audio_bytes = 0
        self._final_cursor_ms = 0
        self._provider_origin_ms = 0
        self._vendor_last_end_ms = 0
        self._commit_boundary_ms: int | None = None
        self._permanent_error: SpekoRouterError | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._commit_task: asyncio.Task[None] | None = None
        self._reconnect_attempts = 0
        self._connection_epoch = 0
        self._retired_clients: list[SpekoASRClient] = []
        self._route: dict[str, Any] = {}
        # Base _connection_lock -> swap -> I/O. Callbacks never acquire these
        # locks: connect/close/commit may themselves be awaiting a callback.
        self._swap_lock = asyncio.Lock()
        self._io_lock = asyncio.Lock()
        # Serialize ingress metadata with finalize, but allow transcript
        # callbacks while finalize is awaiting the vendor acknowledgement.
        self._input_lock = asyncio.Lock()
        self._metadata_lock = asyncio.Lock()
        self._ingress_lock = asyncio.Lock()
        self._audio_queue_drained = asyncio.Event()
        self._audio_queue_drained.set()
        self._finalize_context: dict[str, Any] | None = None

    @override
    def vendor(self) -> str:
        return "speko"

    @override
    def vendor_metadata(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        metadata: dict[str, Any] = {
            "key": self.config.api_key,
            "language": self.config.language,
            "base_url": safe_url(self.config.base_url),
            "routing": self.config.routing,
        }
        if self._route:
            metadata["route"] = self._route
            metadata["model"] = self._route.get("model", "")
        return {key: value for key, value in metadata.items() if value}

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        try:
            config_json, error = await ten_env.get_property_to_json("")
            if error:
                raise ValueError("Failed to read configuration")
            self.config = SpekoASRConfig.model_validate_json(config_json)
            self.config.update_params()
            ten_env.log_info(
                f"config: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self._start_dumper()
        except Exception as error:
            self._init_failed = True
            self.config = None
            message = safe_error(error)
            ten_env.log_error(
                f"invalid property: {message}", category=LOG_CATEGORY_KEY_POINT
            )
            await self.send_asr_error(
                ModuleError(
                    module="asr",
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=message,
                )
            )

    async def _ensure_connection(self) -> None:
        # Guard before the base's start_connection wrapper emits connecting.
        if self.stopped or self._init_failed or self._permanent_error:
            return
        await super()._ensure_connection()

    @override
    async def start_connection(self) -> None:
        async with self._swap_lock:
            if self.stopped or self._init_failed or self._permanent_error:
                await self.on_disconnected(
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message="Speko ASR connection is disabled",
                )
                return
            if self.config is None:
                self._init_failed = True
                await self.on_disconnected(
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message="Speko ASR is not configured",
                )
                return
            # Detach before waiting for sends/close. A retired listener cannot
            # change state or report results belonging to a newer generation.
            self._detach_client()
            await self._close_retired_clients()
            self._provider_origin_ms = self._vendor_audio_duration()
            self._vendor_last_end_ms = 0
            self._commit_boundary_ms = None
            self._final_cursor_ms = (
                self.audio_timeline.get_total_user_audio_duration()
            )
            self._connect_started_at = time.monotonic()
            epoch = self._connection_epoch

            async def on_event(event: dict[str, Any]) -> None:
                if epoch == self._connection_epoch and not self.stopped:
                    await self._on_router_event(event)

            async def on_disconnect(error: SpekoRouterError | None) -> None:
                if epoch == self._connection_epoch and not self.stopped:
                    await self._on_router_disconnect(error)

            client = SpekoASRClient(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                configure=self._configure_frame(),
                ready_timeout_sec=self.config.ready_timeout_sec,
                finalize_timeout_sec=self.config.finalize_timeout_sec,
                on_event=on_event,
                on_disconnect=on_disconnect,
            )
            self.client = client
            try:
                await client.connect()
            except asyncio.CancelledError:
                self._detach_client()
                await self._close_retired_clients()
                raise
            except Exception as error:
                await self._reset_connection(self._router_error(error), epoch)

    def _detach_client(self) -> None:
        self._connection_epoch += 1
        client, self.client = self.client, None
        if client is not None:
            self._retired_clients.append(client)

    async def _close_retired_clients(self, *, drain: bool = False) -> None:
        # Caller owns swap. Waiting for an active send/finalize here is safe;
        # failure reporting never asks for swap while holding the I/O lock.
        async with self._io_lock:
            while self._retired_clients:
                client = self._retired_clients.pop(0)
                try:
                    await client.close(drain=drain)
                    if (
                        drain
                        and isinstance(client.usage, dict)
                        and client.usage
                    ):
                        await self.send_vendor_metrics({"usage": client.usage})
                except asyncio.CancelledError:
                    # Shutdown takes over cancelled recovery and must finish
                    # closing this client before dropping its ownership.
                    self._retired_clients.insert(0, client)
                    raise
                except Exception as error:
                    self.ten_env.log_debug(
                        f"Retired Speko session cleanup: {safe_error(error)}"
                    )

    @override
    def is_connected(self) -> bool:
        return (
            not self.stopped
            and self.client is not None
            and self.client.is_ready
        )

    @override
    async def stop_connection(self) -> None:
        if self._commit_task is not None:
            self._commit_task.cancel()
        task, self._reconnect_task = self._reconnect_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._commit_task is not None:
            self._commit_task.cancel()
        self._detach_client()
        async with self._swap_lock:
            await self._close_retired_clients(drain=True)

    @override
    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        self.stopped = True
        self._audio_queue_drained.set()
        try:
            await super().on_stop(ten_env)
        finally:
            await self._stop_dumper()

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        self.stopped = True
        self._audio_queue_drained.set()
        try:
            await self.stop_connection()
        finally:
            await self._stop_dumper()
            await super().on_deinit(ten_env)

    async def _stop_dumper(self) -> None:
        dumper, self.audio_dumper = self.audio_dumper, None
        if dumper is not None:
            await dumper.stop()

    @override
    def input_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 16000

    @override
    def input_audio_channels(self) -> int:
        return self.config.channels if self.config else 1

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        if self.config is None or self.config.buffer_duration_ms == 0:
            return ASRBufferConfigModeDiscard()
        return ASRBufferConfigModeKeep(
            byte_limit=(
                self.input_audio_sample_rate()
                * self.input_audio_channels()
                * self.input_audio_sample_width()
                * self.config.buffer_duration_ms
                // 1000
            )
        )

    @override
    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, frame: AudioFrame
    ) -> None:
        async with self._ingress_lock:
            await self._enqueue_audio_frame(ten_env, frame)

    async def _enqueue_audio_frame(
        self, ten_env: AsyncTenEnv, frame: AudioFrame
    ) -> None:
        if self.stopped:
            return
        # Dump original ingress once, including buffered/dropped input. Replaying
        # the base queue must not duplicate bytes in this raw-input dump.
        if self.audio_dumper is not None:
            await self.audio_dumper.push_bytes(bytes(frame.get_buf()))
        if (
            not self.is_connected()
            and self.connection_status != ModuleConnectionStatus.CONNECTING
            and (self.auto_connect or self._connection_requested)
        ):
            self._schedule_reconnect()
        self._audio_queue_drained.clear()
        await super().on_audio_frame(ten_env, frame)

    async def _handle_audio_frame(
        self, ten_env: AsyncTenEnv, frame: AudioFrame
    ) -> None:
        try:
            await self._consume_audio_frame(ten_env, frame)
        finally:
            if self.audio_frames_queue.empty():
                self._audio_queue_drained.set()

    async def _consume_audio_frame(
        self, ten_env: AsyncTenEnv, frame: AudioFrame
    ) -> None:
        # Coupled to TEN's serialized consumer so metadata cannot change during
        # a finalize handshake. Keep all base buffering/TTFW accounting intact.
        async with self._input_lock:
            async with self._metadata_lock:
                if self.stopped:
                    return
                if not self.is_connected():
                    size = len(frame.get_buf())
                    policy = self.buffer_strategy()
                    if isinstance(policy, ASRBufferConfigModeDiscard):
                        self._record_dropped_audio(size)
                        return
                    if size > policy.byte_limit:
                        self._record_dropped_audio(size)
                        return
                    while self.buffered_frames_size + size > policy.byte_limit:
                        if self.buffered_frames.empty():
                            break
                        dropped = self.buffered_frames.get_nowait()
                        dropped_size = len(dropped.get_buf())
                        self.buffered_frames_size -= dropped_size
                        self._record_dropped_audio(dropped_size)
                await super()._handle_audio_frame(ten_env, frame)

    def _record_dropped_audio(self, size: int) -> None:
        before = self._audio_duration_ms(self._dropped_audio_bytes)
        self._dropped_audio_bytes += size
        self.audio_timeline.add_dropped_audio(
            self._audio_duration_ms(self._dropped_audio_bytes) - before
        )

    def _schedule_reconnect(self) -> None:
        if self.stopped or self._init_failed:
            return
        if self._permanent_error and not self._retired_clients:
            return
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        while self._reconnect_attempts < len(self.RECONNECT_DELAYS):
            delay = self.RECONNECT_DELAYS[self._reconnect_attempts]
            async with self._swap_lock:
                await self._close_retired_clients()
            if self.stopped or self._init_failed or self._permanent_error:
                return
            if self.is_connected():
                return
            await asyncio.sleep(delay)
            self._reconnect_attempts += 1
            await self._ensure_connection()
            if self.is_connected():
                return
        async with self._swap_lock:
            await self._close_retired_clients()
        if not self.stopped and self._permanent_error is None:
            self._permanent_error = SpekoRouterError(
                "retry_exhausted", "Speko ASR reconnect attempts exhausted"
            )
            await self._report_router_error(self._permanent_error)

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        del session_id
        error = None
        epoch = self._connection_epoch
        buffer = frame.lock_buf()
        try:
            audio = bytes(buffer)
            async with self._io_lock:
                if not self.is_connected():
                    return False
                client = self.client
                assert client is not None
                await client.send_audio(audio)
                if epoch != self._connection_epoch:
                    return False
                # Compute each increment from cumulative bytes, not separately
                # rounded frame durations (notably for 44.1 kHz input).
                before_ms = self._audio_duration_ms(self._sent_audio_bytes)
                self._sent_audio_bytes += len(audio)
                self._total_audio_bytes += len(audio)
                self.audio_timeline.add_user_audio(
                    self._audio_duration_ms(self._sent_audio_bytes) - before_ms
                )
                return True
        except Exception as caught:
            error = self._router_error(caught)
        finally:
            frame.unlock_buf(buffer)
        if error is not None:
            await self._reset_connection(error, epoch)
        return False

    @override
    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        if data.get_name() != "asr_finalize":
            await super().on_data(ten_env, data)
            return
        raw, _ = data.get_property_to_json("metadata")
        context = json.loads(raw) if raw else {}
        if not isinstance(context, dict):
            context = {}
        # Hold later ingress while previously accepted audio drains through the
        # base consumer. A finalize during the initial handshake must commit
        # that buffered audio after ready, rather than acknowledge it early.
        async with self._ingress_lock:
            if self.connection_status == ModuleConnectionStatus.CONNECTING:
                async with self._connection_lock:
                    pass  # Join the existing owner; do not start another retry.
            while not self.stopped and not self.audio_frames_queue.empty():
                self._audio_queue_drained.clear()
                await self._audio_queue_drained.wait()
            if self.stopped:
                return
            # Lock before the base writes finalize_id/last_finalize_time, also
            # waiting for the consumer's last in-flight send to finish.
            async with self._input_lock:
                self._finalize_context = copy.deepcopy(context)
                try:
                    await super().on_data(ten_env, data)
                finally:
                    self._finalize_context = None
                    self.last_finalize_time = None

    @override
    async def finalize(self, session_id: str | None) -> None:
        del session_id
        error = None
        epoch = self._connection_epoch
        try:
            async with self._io_lock:
                if not self.is_connected():
                    return
                client = self.client
                assert client is not None
                self._commit_task = asyncio.create_task(client.commit())
                try:
                    await self._commit_task
                finally:
                    self._commit_task = None
                if epoch == self._connection_epoch:
                    self._commit_boundary_ms = self._vendor_audio_duration()
                    self._total_audio_bytes = 0
                    self._final_cursor_ms = max(
                        self._final_cursor_ms,
                        self.audio_timeline.get_total_user_audio_duration(),
                    )
        except asyncio.CancelledError:
            if not self.stopped:
                raise
        except Exception as caught:
            error = self._router_error(caught)
        finally:
            if error is not None:
                await self._reset_connection(error, epoch)
            if not self.stopped:
                # send_asr_finalize_end reads mutable base metadata. Snapshot
                # only while reporting, after commit releases its I/O lock.
                async with self._metadata_lock:
                    previous = self.metadata
                    if self._finalize_context is not None:
                        self.metadata = self._finalize_context
                    try:
                        await self.send_asr_finalize_end()
                    finally:
                        self.metadata = previous

    async def _reset_connection(
        self, error: SpekoRouterError, epoch: int | None = None
    ) -> None:
        if self.stopped or (
            epoch is not None and epoch != self._connection_epoch
        ):
            return
        # Invalidate before the first await. Error + close callbacks for the
        # same generation now have exactly one owner and one error report.
        self._detach_client()
        if self._module_error_code(error) == ModuleErrorCode.FATAL_ERROR:
            self._permanent_error = error
        await self._report_router_error(error)
        await self.on_disconnected(
            code=self._module_error_code(error).value,
            message=safe_error(error),
            vendor_info=self._vendor_info(error),
        )
        self._schedule_reconnect()

    async def _on_router_disconnect(
        self, error: SpekoRouterError | None
    ) -> None:
        await self._reset_connection(
            error
            or SpekoRouterError(
                "relay_error", "Speko ASR connection closed", retryable=True
            ),
            self._connection_epoch,
        )

    async def _on_router_event(self, event: dict[str, Any]) -> None:
        epoch = self._connection_epoch
        event_type = event.get("type")
        if event_type == "session.ready":
            self._route = dict(event.get("route", {}))
            self._reconnect_attempts = 0
            # Requeue in order through the base consumer, which reads metadata
            # per frame. No new ingress is needed to release buffered audio.
            if not self.buffered_frames.empty():
                pending = []
                while not self.buffered_frames.empty():
                    pending.append(self.buffered_frames.get_nowait())
                while not self.audio_frames_queue.empty():
                    pending.append(self.audio_frames_queue.get_nowait())
                self.buffered_frames_size = 0
                self._audio_queue_drained.clear()
                for frame in pending:
                    self.audio_frames_queue.put_nowait(frame)
            await self.on_connected()
            if self.stopped or epoch != self._connection_epoch:
                return
            await self.send_connect_delay_metrics(
                int((time.monotonic() - self._connect_started_at) * 1000)
            )
        elif event_type in {"transcript.delta", "transcript.final"}:
            await self._send_transcript(
                event, final=event_type == "transcript.final"
            )
        elif event_type in {"usage.updated", "session.closed"}:
            await self.send_vendor_metrics(
                {"usage": dict(event.get("usage", {}))}
            )

    async def _send_transcript(
        self, event: dict[str, Any], *, final: bool
    ) -> None:
        epoch = self._connection_epoch
        text = str(event.get("text", ""))
        if not text.strip():
            return
        segments = []
        for segment in event.get("segments") or []:
            try:
                start, end = int(segment["start_ms"]), int(segment["end_ms"])
                if 0 <= start <= end:
                    segments.append((start, end, str(segment.get("text", ""))))
            except (KeyError, TypeError, ValueError):
                continue
        words: list[ASRWord] = []
        if segments:
            first = min(start for start, _, _ in segments)
            # Most providers keep a stream clock. Only rebase a reset clock
            # after a completed commit, never on ordinary interim/final events.
            if (
                self._commit_boundary_ms is not None
                and first < self._vendor_last_end_ms
            ):
                self._provider_origin_ms = self._commit_boundary_ms
                self._vendor_last_end_ms = 0
            self._commit_boundary_ms = None
            for start, end, word in segments:
                mapped_start = (
                    self.audio_timeline.get_audio_duration_before_time(
                        self._provider_origin_ms + start
                    )
                )
                mapped_end = self.audio_timeline.get_audio_duration_before_time(
                    self._provider_origin_ms + end
                )
                words.append(
                    ASRWord(
                        word=word,
                        start_ms=mapped_start,
                        duration_ms=max(0, mapped_end - mapped_start),
                        stable=final,
                    )
                )
            start_ms = min(word.start_ms for word in words)
            end_ms = max(word.start_ms + word.duration_ms for word in words)
            if final:
                self._vendor_last_end_ms = max(end for _, end, _ in segments)
        else:
            start_ms = self._final_cursor_ms
            end_ms = self.audio_timeline.get_total_user_audio_duration()
        async with self._metadata_lock:
            if self.stopped or epoch != self._connection_epoch:
                return
            previous = self.metadata
            metadata = copy.deepcopy(previous or {})
            info = metadata.setdefault("asr_info", {})
            if not isinstance(info, dict):
                info = metadata["asr_info"] = {}
            info.update(vendor=self.vendor(), locked=False)
            if event.get("speaker") is not None:
                info["speaker"] = event["speaker"]
            self.metadata = metadata
            try:
                await self.send_asr_result(
                    ASRResult(
                        text=text,
                        final=final,
                        start_ms=start_ms,
                        duration_ms=max(0, end_ms - start_ms),
                        language=(
                            self.config.language if self.config else "en-US"
                        ),
                        words=words,
                        metadata=copy.deepcopy(metadata),
                    )
                )
            finally:
                self.metadata = previous
        if final:
            self._final_cursor_ms = max(self._final_cursor_ms, end_ms)

    async def _report_router_error(self, error: SpekoRouterError) -> None:
        self.ten_env.log_error(
            f"vendor_error: code={error.code}, message={safe_error(error)}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self.send_asr_error(
            ModuleError(
                module="asr",
                code=self._module_error_code(error).value,
                message=safe_error(error),
                vendor_info=self._vendor_info(error),
            )
        )

    def _configure_frame(self) -> dict[str, Any]:
        assert self.config is not None
        frame: dict[str, Any] = {
            "type": "session.configure",
            "audio": {
                "encoding": "pcm_s16le",
                "sample_rate_hz": self.config.sample_rate,
                "channels": self.config.channels,
            },
        }
        if self.config.routing:
            frame["routing"] = self.config.routing
        if self.config.language:
            frame["language"] = self.config.language
        if self.config.options:
            frame["options"] = self.config.options
        return frame

    async def _start_dumper(self) -> None:
        if (
            self.config is None
            or not self.config.dump
            or self.audio_dumper is not None
        ):
            return
        dump_path = Path(self.config.dump_path)
        if dump_path.suffix != ".pcm":
            dump_path = dump_path / "speko_asr_in.pcm"
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        self.audio_dumper = Dumper(str(dump_path))
        await self.audio_dumper.start()

    def _audio_duration_ms(self, byte_count: int) -> int:
        return (
            byte_count
            * 1000
            // (
                self.input_audio_sample_rate()
                * self.input_audio_channels()
                * self.input_audio_sample_width()
            )
        )

    def _vendor_audio_duration(self) -> int:
        return (
            self.audio_timeline.total_user_audio_duration
            + self.audio_timeline.total_silence_audio_duration
        )

    @staticmethod
    def _module_error_code(error: SpekoRouterError) -> ModuleErrorCode:
        if error.code in {
            "authentication_failed",
            "insufficient_credit",
            "route_not_found",
            "capability_unsupported",
            "retry_exhausted",
        }:
            return ModuleErrorCode.FATAL_ERROR
        return ModuleErrorCode.NON_FATAL_ERROR

    @staticmethod
    def _router_error(error: Exception) -> SpekoRouterError:
        if isinstance(error, SpekoRouterError):
            return error
        return SpekoRouterError(
            "relay_error", safe_error(error), retryable=True
        )

    def _vendor_info(self, error: SpekoRouterError) -> ModuleErrorVendorInfo:
        return ModuleErrorVendorInfo(
            vendor=self.vendor(), code=error.code, message=safe_error(error)
        )
