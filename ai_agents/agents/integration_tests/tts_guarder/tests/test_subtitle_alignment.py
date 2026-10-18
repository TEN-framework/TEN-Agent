#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Validate request PCM clocks and preserve the provider's word offsets."""

import asyncio
import json
import os
from contextlib import suppress
from typing import Any

import pytest
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    AudioFrame,
    Data,
    TenError,
    TenErrorCode,
)

from .subtitle_timing import (
    AudioFrameTiming,
    validate_audio_clock,
    validate_provider_reference,
    validate_subtitle_bounds,
)
from .timing_hooks import install_timing_hook

TTS_SUBTITLE_CONFIG_FILE = "property_subtitle_alignment.json"
SUPPORTED_TTS_EXTENSIONS = {"cartesia_tts", "minimax_tts_websocket_duplex"}
REQUEST_IDS = ["subtitle_alignment_first", "subtitle_alignment_second"]


class SubtitleAlignmentTester(AsyncExtensionTester):
    """Observe two sequential requests at public TEN output boundaries.

    A first word may follow leading silence. Generic checks validate ranges
    against the cumulative PCM sample clock. An optional vendor hook provides
    an independent reference for original provider word times.
    """

    def __init__(self, session_id="subtitle_alignment", reference_source=None):
        super().__init__()
        self.session_id = session_id
        self.reference_source = reference_source
        self.request_index = 0
        self.timeout_task = None
        self.text_results: list[dict[str, Any]] = []
        self.audio_frames: list[AudioFrameTiming] = []
        self.audio_start_received = False
        self.audio_end_received = False
        self.terminal_received = False
        self.validating = False

    def _reset_capture(self):
        self.text_results = []
        self.audio_frames = []
        self.audio_start_received = False
        self.audio_end_received = False
        self.terminal_received = False
        self.validating = False

    @property
    def request_id(self):
        return REQUEST_IDS[self.request_index]

    async def on_start(self, ten_env: AsyncTenEnvTester):
        self.timeout_task = asyncio.create_task(self._timeout(ten_env))
        await self._send_input(ten_env)

    async def _timeout(self, ten_env):
        await asyncio.sleep(30)
        self._fail(ten_env, "Subtitle alignment request did not complete")

    async def _send_input(self, ten_env):
        texts = [
            (
                "The castle's shadow stretched across the moat like a skeletal hand, "
                "its turrets piercing the stormy sky where lightning flickered."
            ),
            (
                "A second request preserves its own word offsets. "
                "Audio fractions must stay on the same sample clock."
            ),
        ]
        data = Data.create("tts_text_input")
        data.set_property_string("text", texts[self.request_index])
        data.set_property_string("request_id", self.request_id)
        data.set_property_bool("text_input_end", True)
        data.set_property_from_json(
            "metadata",
            json.dumps(
                {
                    "session_id": self.session_id,
                    "turn_id": self.request_index + 1,
                }
            ),
        )
        if self.reference_source:
            self.reference_source.begin_request(self.request_id)
        await ten_env.send_data(data)

    def _fail(self, ten_env, message):
        ten_env.stop_test(
            TenError.create(TenErrorCode.ErrorCodeGeneric, message)
        )

    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data):
        name = data.get_name()
        if name not in {
            "error",
            "tts_text_result",
            "tts_audio_start",
            "tts_audio_end",
        }:
            return
        payload, error = data.get_property_to_json("")
        if error:
            self._fail(ten_env, "Cannot read TTS output")
            return
        result = json.loads(payload)
        if name == "error":
            self._fail(ten_env, f"Provider error code={result.get('code')}")
            return
        if result.get("request_id") != self.request_id:
            self._fail(ten_env, "TTS output belongs to another request")
            return
        if name == "tts_audio_start":
            self.audio_start_received = True
        elif name == "tts_text_result":
            self.text_results.append(result)
            if result.get("text_result_end"):
                self.terminal_received = True
        elif name == "tts_audio_end":
            self.audio_end_received = True
        await self._complete_if_ready(ten_env)

    async def on_audio_frame(
        self, ten_env: AsyncTenEnvTester, frame: AudioFrame
    ):
        metadata_json, error = frame.get_property_to_json("metadata")
        if error or not self.audio_start_received:
            self._fail(ten_env, "Audio arrived without its request start")
            return
        metadata = json.loads(metadata_json)
        if metadata.get("turn_id") != self.request_index + 1:
            self._fail(ten_env, "Audio belongs to another request")
            return
        self.audio_frames.append(
            AudioFrameTiming(
                frame.get_timestamp(),
                frame.get_samples_per_channel(),
                frame.get_sample_rate(),
                frame.get_number_of_channels(),
            )
        )

    async def _complete_if_ready(self, ten_env):
        if (
            not self.audio_end_received
            or not self.terminal_received
            or self.validating
        ):
            return
        self.validating = True
        checks = [
            validate_audio_clock(self.audio_frames),
            validate_subtitle_bounds(self.text_results, self.audio_frames),
            self._validate_sequence(),
        ]
        if self.reference_source:
            checks.append(
                validate_provider_reference(
                    self.request_id,
                    self.text_results,
                    self.audio_frames,
                    self.reference_source.reference(self.request_id),
                )
            )
        for valid, message in checks:
            if not valid:
                self._fail(ten_env, message)
                return
            ten_env.log_info(f"{self.request_id}: {message}")
        if self.request_index + 1 == len(REQUEST_IDS):
            ten_env.stop_test()
            return
        self.request_index += 1
        self._reset_capture()
        await self._send_input(ten_env)

    def _validate_sequence(self):
        if not self.text_results:
            return False, "No subtitle results received"
        previous_sequence = None
        for result in self.text_results:
            metadata = result.get("metadata", {})
            if (
                metadata.get("turn_id") != self.request_index + 1
                or metadata.get("session_id") != self.session_id
            ):
                return False, "Subtitle metadata belongs to another request"
            sequence = metadata.get("turn_seq_id")
            if sequence is not None:
                if (
                    previous_sequence is not None
                    and sequence < previous_sequence
                ):
                    return False, "Subtitle sequence moved backwards"
                previous_sequence = sequence
        terminal = self.text_results[-1]
        if not terminal.get("text_result_end") or terminal.get(
            "metadata", {}
        ).get("turn_status") not in (1, 2):
            return False, "Missing terminal subtitle result"
        return True, "Request metadata and terminal subtitle are valid"

    async def on_stop(self, _ten_env: AsyncTenEnvTester):
        if self.timeout_task:
            self.timeout_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.timeout_task


def run_subtitle_alignment(extension_name, config, monkeypatch):
    """Observe live TTS output with an optional case-scoped vendor hook."""
    with install_timing_hook(
        extension_name, config, monkeypatch
    ) as reference_source:
        tester = SubtitleAlignmentTester(reference_source=reference_source)
        tester.set_test_mode_single(extension_name, json.dumps(config))
        return tester.run()


def test_subtitle_alignment(
    extension_name, config_dir, enable_subtitle_alignment, monkeypatch
):
    if not enable_subtitle_alignment:
        pytest.skip(
            "Pass --enable_subtitle_alignment=True to run alignment checks"
        )
    if extension_name not in SUPPORTED_TTS_EXTENSIONS:
        pytest.skip(f"Word alignment is unsupported for {extension_name}")
    path = os.path.join(config_dir, TTS_SUBTITLE_CONFIG_FILE)
    if not os.path.exists(path):
        pytest.skip(f"Word alignment configuration is missing: {path}")
    with open(path, encoding="utf-8") as source:
        config = json.load(source)
    error = run_subtitle_alignment(
        extension_name,
        config,
        monkeypatch,
    )
    assert (
        error is None
    ), f"Subtitle alignment failed: {error.error_message() if error else ''}"
