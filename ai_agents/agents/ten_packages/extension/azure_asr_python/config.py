from pydantic import BaseModel, Field
from typing import Any, cast

from .const import DEFAULT_TRANSPORT_RECONNECT_GRACE_SEC, FINALIZE_MODE_MUTE_PKG
from ten_ai_base.utils import encrypt


class AzureASRConfig(BaseModel):
    key: str = ""
    region: str = ""
    language: str = "en-US"
    language_list: list[str] = Field(default_factory=list)
    sample_rate: int = 16000
    params: dict[str, Any] = Field(default_factory=dict)
    advanced_params_json: str = ""
    finalize_mode: str = FINALIZE_MODE_MUTE_PKG  # "disconnect" or "mute_pkg"
    mute_pkg_duration_ms: int = 800
    phrase_list: list[str] = Field(default_factory=list)
    hotwords: list[str] = Field(default_factory=list)
    dump: bool = False
    dump_path: str = "."
    transport_reconnect_grace_sec: float = Field(
        default=DEFAULT_TRANSPORT_RECONNECT_GRACE_SEC,
        gt=0,
        allow_inf_nan=False,
    )

    def update(self, params: dict[str, Any]):
        for key, value in params.items():
            if hasattr(self, key):
                if key == "transport_reconnect_grace_sec":
                    value = (
                        type(self)
                        .model_validate({key: value})
                        .transport_reconnect_grace_sec
                    )
                setattr(self, key, value)

        # If language string is divided by comma, split it and set language_list
        if "," in self.language:
            self.language_list = self.language.split(",")
        else:
            self.language_list = [self.language]

        # If hotwords is not empty, remove the content after | and set phrase_list
        if self.hotwords:
            self.phrase_list = [
                (hotword.split("|")[0] if "|" in hotword else hotword)
                for hotword in self.hotwords
            ]

    def to_json(self, sensitive_handling: bool = False) -> str:
        if not sensitive_handling:
            return self.model_dump_json()

        config = self.model_copy(deep=True)
        if config.key:
            config.key = encrypt(config.key)

        params_dict = cast(dict[str, Any], config.params)
        if params_dict:
            encrypted_params: dict[str, Any] = {}
            for key, value in params_dict.items():
                if key == "key" and isinstance(value, str):
                    encrypted_params[key] = encrypt(value)
                else:
                    encrypted_params[key] = value
            config.params = encrypted_params

        return config.model_dump_json()

    def primary_language(self) -> str:
        return self.language_list[0] if self.language_list else self.language
