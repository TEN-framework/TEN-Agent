from __future__ import annotations

import copy
from typing import Any, ClassVar

from pydantic import BaseModel, Field
from ten_ai_base import utils


class SonioxTTSConfig(BaseModel):
    api_key: str = ""
    base_url: str = "wss://tts-rt.soniox.com/tts-websocket"
    model: str = "tts-rt-v2"
    language: str = "en"
    voice: str = "Adrian"
    audio_format: str = "pcm_s16le"
    sample_rate: int = 24000
    speed: float = 1.0
    reduce_silence: bool = False
    return_timestamps: bool = False
    client_reference_id: str = ""
    dump: bool = False
    dump_path: str = "/tmp"
    params: dict[str, Any] = Field(default_factory=dict)

    SUPPORTED_SAMPLE_RATES: ClassVar[tuple[int, ...]] = (
        8000,
        16000,
        24000,
        44100,
        48000,
    )

    def update_params(self) -> None:
        params = self.params if isinstance(self.params, dict) else {}
        self.params = params

        for key in (
            "api_key",
            "base_url",
            "model",
            "language",
            "voice",
            "audio_format",
            "sample_rate",
            "speed",
            "reduce_silence",
            "return_timestamps",
            "client_reference_id",
            "dump",
            "dump_path",
        ):
            if key in params:
                setattr(self, key, params.pop(key))

    def validate_params(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.base_url:
            raise ValueError("base_url is required")
        if not self.model:
            raise ValueError("model is required")
        if not self.language:
            raise ValueError("language is required")
        if not self.voice:
            raise ValueError("voice is required")
        if self.audio_format != "pcm_s16le":
            raise ValueError("audio_format must be pcm_s16le")
        if self.sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                "sample_rate must be one of " f"{self.SUPPORTED_SAMPLE_RATES}"
            )
        if not 0.7 <= self.speed <= 1.3:
            raise ValueError("speed must be between 0.7 and 1.3")

    def to_str(self, sensitive_handling: bool = True) -> str:
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)
        if config.api_key:
            config.api_key = utils.encrypt(config.api_key)
        for key, value in config.params.items():
            if (
                key.lower()
                in {
                    "api_key",
                    "authorization",
                    "password",
                    "secret",
                    "token",
                }
                and value
            ):
                config.params[key] = utils.encrypt(str(value))
        return f"{config}"
