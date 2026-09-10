#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#

from typing import Dict, Any
from pydantic import BaseModel, Field
from ten_ai_base.utils import encrypt


class FunASRConfig(BaseModel):
    """FunASR ASR Configuration"""

    # Debugging and dumping
    dump: bool = False
    dump_path: str = "/tmp"

    # Finalize mode: "disconnect" or "silence"
    finalize_mode: str = "disconnect"
    silence_duration_ms: int = 1000

    # Vendor parameters (pass-through design)
    params: Dict[str, Any] = Field(default_factory=dict)

    def update(self, params: Dict[str, Any]) -> None:
        """Update configuration with additional parameters."""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_json(self, sensitive_handling: bool = False) -> str:
        """Convert config to JSON string with optional sensitive data handling."""
        config_dict = self.model_dump()
        if sensitive_handling and config_dict.get("params"):
            # Mask sensitive keys
            for key in ["api_key", "key", "token", "secret"]:
                if key in config_dict["params"] and config_dict["params"][key]:
                    config_dict["params"][key] = encrypt(
                        config_dict["params"][key]
                    )
        return str(config_dict)

    def normalize_language(self, detected_language: str = "") -> str:
        """Convert configured or detected language to a BCP-47-ish tag."""
        language_map = {
            "zh": "zh-CN",
            "en": "en-US",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "yue": "yue-CN",
            "de": "de-DE",
            "fr": "fr-FR",
            "ru": "ru-RU",
            "es": "es-ES",
            "pt": "pt-PT",
            "it": "it-IT",
            "hi": "hi-IN",
            "ar": "ar-AE",
        }
        params_dict = self.params or {}
        configured_language = params_dict.get("language", "") or ""
        language_code = (
            detected_language
            if configured_language in {"", "auto"} and detected_language
            else configured_language
        )
        return language_map.get(language_code, language_code)

    @property
    def normalized_language(self) -> str:
        """Convert the configured language code to a BCP-47-ish tag."""
        return self.normalize_language()
