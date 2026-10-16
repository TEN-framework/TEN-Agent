#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
"""Shared tester for the extension-local tests.

``RecordingTester`` drives ``kotoba_tts_python`` inside the TEN runtime,
records every event it emits, and lets a test script text inputs and
flushes. Tests subclass it or pass a ``script`` coroutine.
"""
import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    AudioFrame,
    Data,
    TenError,
    TenErrorCode,
)

EXTENSION_NAME = "kotoba_tts_python"


@dataclass
class Event:
    name: str
    payload: dict
    at: float


@dataclass
class Recording:
    events: list[Event] = field(default_factory=list)
    frames: list[tuple[str, bytes, int]] = field(default_factory=list)

    def named(self, name: str) -> list[Event]:
        return [e for e in self.events if e.name == name]

    def audio_bytes(self, request_id: str | None = None) -> bytes:
        return b"".join(
            data
            for rid, data, _rate in self.frames
            if request_id is None or rid == request_id
        )

    REQUEST_EVENTS = ("tts_audio_start", "pcm_frame", "tts_audio_end", "error")

    def sequence(self, request_id: str | None = None) -> list[str]:
        """Request-scoped event names in arrival order; consecutive frames
        collapse to one ``pcm_frame`` entry. Base-class bookkeeping events
        (provide_features, metrics, connection status) are left out."""
        out: list[str] = []
        for e in self.events:
            if e.name not in self.REQUEST_EVENTS:
                continue
            if request_id is not None and e.payload.get("request_id") not in (
                request_id,
                "",
                None,
            ):
                continue
            if e.name == "pcm_frame" and out and out[-1] == "pcm_frame":
                continue
            out.append(e.name)
        return out


def make_config(base_url: str, **overrides) -> dict:
    params = {
        "key": "test-key",
        "base_url": base_url,
        "sample_rate": 16000,
        "request_timeout_seconds": 5,
    }
    params.update(overrides.pop("params", {}))
    config = {
        "dump": False,
        "dump_path": "./tests/dump_output/",
        "params": params,
    }
    config.update(overrides)
    return config


class RecordingTester(AsyncExtensionTester):
    def __init__(
        self,
        script: Callable[
            ["RecordingTester", AsyncTenEnvTester], Awaitable[None]
        ],
        *,
        timeout_s: float = 20.0,
    ) -> None:
        super().__init__()
        self._script = script
        self._timeout_s = timeout_s
        self.recording = Recording()
        self.failure: str | None = None
        self._waiters: list[
            tuple[Callable[[Recording], bool], asyncio.Future]
        ] = []

    # -- driving -----------------------------------------------------------

    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        asyncio.create_task(self._run_script(ten_env))

    async def _run_script(self, ten_env: AsyncTenEnvTester) -> None:
        try:
            await asyncio.wait_for(self._script(self, ten_env), self._timeout_s)
        except asyncio.TimeoutError:
            self.failure = f"script timed out; sequence so far: {self.recording.sequence()}"
        except AssertionError as exc:
            self.failure = f"assertion failed: {exc}"
        except Exception as exc:
            self.failure = f"{type(exc).__name__}: {exc}"
        if self.failure:
            ten_env.stop_test(
                TenError.create(TenErrorCode.ErrorCodeGeneric, self.failure)
            )
        else:
            ten_env.stop_test()

    async def send_text(
        self,
        ten_env: AsyncTenEnvTester,
        request_id: str,
        text: str,
        *,
        end: bool,
        metadata: dict | None = None,
    ) -> None:
        data = Data.create("tts_text_input")
        data.set_property_string("request_id", request_id)
        data.set_property_string("text", text)
        data.set_property_bool("text_input_end", end)
        if metadata is None:
            # The base class echoes input metadata on every frame and
            # event, which is how frames are attributed to a request.
            metadata = {"session_id": "test-session", "request_id": request_id}
        data.set_property_from_json("metadata", json.dumps(metadata))
        await ten_env.send_data(data)

    async def send_flush(
        self, ten_env: AsyncTenEnvTester, flush_id: str = "flush-1"
    ) -> None:
        data = Data.create("tts_flush")
        data.set_property_string("flush_id", flush_id)
        data.set_property_from_json(
            "metadata", json.dumps({"flush_id": flush_id})
        )
        await ten_env.send_data(data)

    async def wait_for(
        self, predicate: Callable[[Recording], bool], timeout_s: float = 10.0
    ) -> None:
        if predicate(self.recording):
            return
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiters.append((predicate, fut))
        await asyncio.wait_for(fut, timeout_s)

    async def wait_for_event(
        self, name: str, count: int = 1, timeout_s: float = 10.0
    ) -> list[Event]:
        await self.wait_for(lambda r: len(r.named(name)) >= count, timeout_s)
        return self.recording.named(name)

    async def wait_for_audio_end(
        self, request_id: str, timeout_s: float = 10.0
    ) -> Event:
        def done(r: Recording) -> bool:
            return any(
                e.payload.get("request_id") == request_id
                for e in r.named("tts_audio_end")
            )

        await self.wait_for(done, timeout_s)
        return [
            e
            for e in self.recording.named("tts_audio_end")
            if e.payload.get("request_id") == request_id
        ][0]

    # -- recording ---------------------------------------------------------

    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        name = data.get_name()
        raw, _ = data.get_property_to_json(None)
        payload = json.loads(raw) if raw else {}
        self.recording.events.append(Event(name, payload, time.monotonic()))
        self._notify()

    async def on_audio_frame(
        self, ten_env: AsyncTenEnvTester, audio_frame: AudioFrame
    ) -> None:
        buf = audio_frame.lock_buf()
        try:
            data = bytes(buf)
        finally:
            audio_frame.unlock_buf(buf)
        raw, _ = audio_frame.get_property_to_json("metadata")
        request_id = ""
        if raw:
            try:
                request_id = json.loads(raw).get("request_id", "")
            except json.JSONDecodeError:
                request_id = ""
        rate = audio_frame.get_sample_rate()
        self.recording.frames.append((request_id, data, rate))
        self.recording.events.append(
            Event(
                "pcm_frame",
                {"request_id": request_id, "bytes": len(data)},
                time.monotonic(),
            )
        )
        self._notify()

    def _notify(self) -> None:
        remaining = []
        for predicate, fut in self._waiters:
            if fut.done():
                continue
            if predicate(self.recording):
                fut.set_result(None)
            else:
                remaining.append((predicate, fut))
        self._waiters = remaining


def metrics_with(tester, key: str):
    """Metrics events whose payload carries ``key``."""
    return [
        e
        for e in tester.recording.named("metrics")
        if key in e.payload.get("metrics", {})
    ]


def events_after(tester, name: str, after_event) -> list:
    """Events named ``name`` recorded after ``after_event``."""
    return [e for e in tester.recording.named(name) if e.at > after_event.at]


def run_tester(
    script, config: dict, *, timeout_s: float = 20.0
) -> RecordingTester:
    tester = RecordingTester(script, timeout_s=timeout_s)
    tester.set_test_mode_single(EXTENSION_NAME, json.dumps(config))
    error = tester.run()
    assert (
        error is None
    ), f"tester failed: {error.error_message() if error else 'unknown'}"
    assert tester.failure is None, tester.failure
    return tester


def dump_path(dump_dir: str, request_id: str) -> str:
    """Path of the extension's dump file for ``request_id``."""
    import os

    from kotoba_tts_python.extension import dump_file_name

    return os.path.join(dump_dir, dump_file_name(request_id))
