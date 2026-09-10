#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""TEN framework config for Blaze realtime TTS (WebSocket)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from pydantic import Field
from ten_ai_base import utils
from ten_ai_base.tts2_http import AsyncTTS2HttpConfig

DEFAULT_API_URL = "https://api.blaze.vn"
DEFAULT_SPEAKER_ID = "HN-Nu-CSKH-HuongGiang"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_LANGUAGE = "vi"
# Public realtime alias; HTTP client maps this to v2.0_flash backend
DEFAULT_MODEL = "2.0-realtime"


class BlazeTTSConfig(AsyncTTS2HttpConfig):
    """Blaze realtime TTS configuration."""

    dump: bool = Field(default=False, description="Dump synthesized audio")
    dump_path: str = Field(
        default_factory=lambda: str(Path(__file__).parent / "blaze_tts_in.pcm"),
        description="Dump path for synthesized audio",
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Blaze TTS params"
    )

    def update_params(self) -> None:
        self.params.setdefault("api_url", DEFAULT_API_URL)
        self.params.setdefault("language", DEFAULT_LANGUAGE)
        self.params.setdefault("speaker_id", DEFAULT_SPEAKER_ID)
        self.params.setdefault("audio_speed", 1.0)
        self.params.setdefault("audio_quality", 64)
        self.params.setdefault("model", DEFAULT_MODEL)
        self.params.setdefault("sample_rate", DEFAULT_SAMPLE_RATE)
        # pcm for TEN pcm_frame (docs also allow mp3/wav/opus)
        self.params.setdefault("audio_format", "pcm")
        # Official API value is "request" (not internal name request_base)
        self.params.setdefault("strategy", "request")
        self.params.setdefault("normalization", "basic")
        # docs use string speed
        if "audio_speed" in self.params:
            self.params["audio_speed"] = str(self.params["audio_speed"])

        if self.params.get("speaker_id") == "":
            self.params["speaker_id"] = DEFAULT_SPEAKER_ID

    def to_str(self, sensitive_handling: bool = True) -> str:
        if not sensitive_handling:
            return f"{self}"
        config = copy.deepcopy(self)
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])
        return f"{config}"

    def validate(self) -> None:
        if not self.params.get("api_key"):
            raise ValueError("API key is required for Blaze TTS")
        if not self.params.get("speaker_id"):
            raise ValueError("speaker_id is required for Blaze TTS")
        if not self.params.get("api_url"):
            raise ValueError("api_url is required for Blaze TTS")

    def ws_url(self) -> str:
        base = str(self.params.get("api_url", DEFAULT_API_URL)).rstrip("/")
        if base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://") :]

        # Session defaults as query params
        from urllib.parse import urlencode

        q = {
            "speaker_id": self.params.get("speaker_id", DEFAULT_SPEAKER_ID),
            "language": self.params.get("language", DEFAULT_LANGUAGE),
            "model": self.params.get("model", DEFAULT_MODEL),
            "sample_rate": str(
                self.params.get("sample_rate", DEFAULT_SAMPLE_RATE)
            ),
            "audio_format": self.params.get("audio_format", "pcm"),
            "audio_speed": str(self.params.get("audio_speed", 1.0)),
            "audio_quality": str(self.params.get("audio_quality", 64)),
        }
        return f"{base}/v1/tts/realtime?{urlencode(q)}"
