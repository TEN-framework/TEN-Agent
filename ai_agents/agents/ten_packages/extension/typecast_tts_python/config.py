#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from pathlib import Path
from typing import Any
import copy

from pydantic import Field
from typecast.models import OutputStream
from ten_ai_base import utils
from ten_ai_base.tts2_http import AsyncTTS2HttpConfig


class TypecastTTSConfig(AsyncTTS2HttpConfig):
    """Typecast TTS config."""

    dump: bool = Field(default=False, description="Typecast TTS dump")
    dump_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).parent / "typecast_tts_in.pcm"
        ),
        description="Typecast TTS dump path",
    )
    url: str = Field(
        default="https://api.typecast.ai",
        description="Typecast API URL",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Typecast TTS params",
    )
    chunk_size: int = Field(
        default=8192,
        ge=1,
        description="Maximum bytes read from each Typecast streaming chunk",
    )

    def update_params(self) -> None:
        if "url" in self.params:
            self.url = str(
                self.params.pop("url")  # pylint: disable=no-member
            ).rstrip("/")
        else:
            self.url = self.url.rstrip("/")

        if "model" not in self.params:
            self.params["model"] = "ssfm-v30"

        output = dict(
            self.params.get("output") or {}  # pylint: disable=no-member
        )
        output["audio_format"] = "wav"
        self.params["output"] = output

    def validate(self) -> None:
        if not self.params.get("api_key"):  # pylint: disable=no-member
            raise ValueError("api_key is required for Typecast TTS")
        if not self.params.get("voice_id"):  # pylint: disable=no-member
            raise ValueError("voice_id is required for Typecast TTS")
        if not self.params.get("model"):  # pylint: disable=no-member
            raise ValueError("model is required for Typecast TTS")
        OutputStream.model_validate(
            self.params.get("output") or {}  # pylint: disable=no-member
        )

    def to_str(self, sensitive_handling: bool = True) -> str:
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])
        return f"{config}"
