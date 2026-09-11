from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ten_ai_base.utils import encrypt


class BytedanceMLLMConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    params: dict[str, Any] = Field(default_factory=dict)
    dump: bool = False
    dump_path: str = ""

    def _params(self) -> dict[str, Any]:
        params = getattr(self, "params", {})
        if isinstance(params, dict):
            return params
        return {}

    def _param(self, key: str, default: Any = None) -> Any:
        return self._params().get(key, default)

    @model_validator(mode="after")
    def validate_params(self) -> "BytedanceMLLMConfig":
        required = {
            "app_id": self.app_id,
            "access_key": self.access_key,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(
                f"Missing required params fields: {', '.join(missing)}"
            )
        if self.input_sample_rate <= 0:
            raise ValueError("input_sample_rate must be greater than 0")
        if self.output_sample_rate <= 0:
            raise ValueError("output_sample_rate must be greater than 0")
        return self

    @property
    def api_url(self) -> str:
        return self._param(
            "api_url",
            "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
        )

    @property
    def app_id(self) -> str:
        return self._param("app_id", "")

    @property
    def access_key(self) -> str:
        return self._param("access_key", "")

    @property
    def resource_id(self) -> str:
        return self._param("resource_id", "volc.speech.dialog")

    @property
    def app_key(self) -> str:
        return self._param("app_key", "PlgvMymc7f3tQnJ6")

    @property
    def model(self) -> str:
        return self._param("model", "1.2.1.1")

    @property
    def speaker(self) -> str:
        return self._param("speaker", "zh_female_vv_jupiter_bigtts")

    @property
    def bot_name(self) -> str:
        return self._param("bot_name", "豆包")

    @property
    def prompt(self) -> str:
        return self._param("prompt", "")

    @property
    def speaking_style(self) -> str:
        return self._param("speaking_style", "")

    @property
    def dialog_id(self) -> str:
        return self._param("dialog_id", "")

    @property
    def input_sample_rate(self) -> int:
        return int(self._param("input_sample_rate", 16000))

    @property
    def output_sample_rate(self) -> int:
        return int(self._param("output_sample_rate", 24000))

    @property
    def output_audio_format(self) -> str:
        return self._param("output_audio_format", "pcm_s16le")

    @property
    def verbose(self) -> bool:
        return bool(self._param("verbose", False))

    def start_session_payload(
        self, message_context: list[Any] | None = None
    ) -> dict[str, Any]:
        asr = copy.deepcopy(self._param("asr", {}))
        tts = copy.deepcopy(self._param("tts", {}))
        dialog = copy.deepcopy(self._param("dialog", {}))

        asr.setdefault("audio_info", {})
        asr["audio_info"].setdefault("format", "pcm_s16le")
        asr["audio_info"].setdefault("sample_rate", self.input_sample_rate)
        asr["audio_info"].setdefault("channel", 1)
        asr.setdefault("extra", {})

        tts.setdefault("speaker", self.speaker)
        tts.setdefault("audio_config", {})
        tts["audio_config"].setdefault("channel", 1)
        tts["audio_config"].setdefault("format", self.output_audio_format)
        tts["audio_config"].setdefault("sample_rate", self.output_sample_rate)
        tts.setdefault("extra", {})

        dialog.setdefault("bot_name", self.bot_name)
        dialog.setdefault("dialog_id", self.dialog_id)
        dialog.setdefault("extra", {})
        dialog["extra"].setdefault("model", self.model)
        if self.prompt and "system_role" not in dialog:
            dialog["system_role"] = self.prompt
        if self.speaking_style and "speaking_style" not in dialog:
            dialog["speaking_style"] = self.speaking_style

        if message_context and "dialog_context" not in dialog:
            dialog["dialog_context"] = [
                {"role": item.role, "text": item.content}
                for item in message_context
                if item.role in ("user", "assistant")
            ]

        return {
            "asr": asr,
            "tts": tts,
            "dialog": dialog,
        }

    def to_str(self, sensitive_handling: bool = True) -> str:
        if not sensitive_handling:
            return f"{self}"

        config = self.model_copy(deep=True)
        params = getattr(config, "params", {})
        if not isinstance(params, dict):
            return f"{config}"

        redacted_params: dict[str, Any] = dict(params)
        for key in ("app_id", "access_key", "api_key"):
            value = redacted_params.get(key)
            if isinstance(value, str) and value:
                redacted_params[key] = encrypt(value)
        config.params = redacted_params
        return f"{config}"
