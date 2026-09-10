#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""TEN framework config for Blaze realtime STT (WebSocket)."""

from __future__ import annotations

import copy
from pathlib import Path

from pydantic import BaseModel, Field
from ten_ai_base import utils

DEFAULT_API_URL = "https://api.blaze.vn"
DEFAULT_LANGUAGE = "vi"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_MODEL = "stt-stream-1.5"


class BlazeASRParams(BaseModel):
    """Params nested under property.params."""

    api_key: str = Field(default="", description="Blaze API key (Bearer token)")
    api_url: str = Field(default=DEFAULT_API_URL, description="Blaze base URL")
    language: str = Field(
        default=DEFAULT_LANGUAGE, description="Language code (e.g. vi, en)"
    )
    sample_rate: int = Field(
        default=DEFAULT_SAMPLE_RATE,
        description="Input PCM sample rate from RTC (must be 16000 for stream)",
    )
    model: str = Field(
        default=DEFAULT_MODEL,
        description="Realtime STT model (stt-stream-1.5)",
    )
    # Optional domain adaptation (stt-stream-1.5 only)
    topic: str = Field(default="", description="Optional topic hint")
    context: str = Field(default="", description="Optional free-form context")


class BlazeASRConfig(BaseModel):
    """Top-level extension property."""

    dump: bool = Field(default=False, description="Dump input audio")
    dump_path: str = Field(
        default_factory=lambda: str(Path(__file__).parent / "blaze_stt_in.pcm"),
        description="Dump path for input audio",
    )
    params: BlazeASRParams = Field(default_factory=BlazeASRParams)

    def validate_config(self) -> None:
        if not self.params.api_key:
            raise ValueError("API key is required for Blaze STT")
        if not self.params.api_url:
            raise ValueError("api_url is required for Blaze STT")

    def to_str(self, sensitive_handling: bool = True) -> str:
        if not sensitive_handling:
            return f"{self}"
        config = copy.deepcopy(self)
        if config.params.api_key:
            config.params.api_key = utils.encrypt(config.params.api_key)
        return f"{config}"

    def ws_url(self) -> str:
        base = self.params.api_url.rstrip("/")
        if base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://") :]
        return f"{base}/v1/stt/realtime"
