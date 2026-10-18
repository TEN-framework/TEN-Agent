from __future__ import annotations

from typing import Any, Optional

from ten_ai_base import utils

from pydantic import BaseModel, Field


def _clamp(
    value: Optional[float], lower: float, upper: float
) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(lower, min(upper, numeric))


class CartesiaSSMLConfig(BaseModel):
    enabled: bool = False
    speed_ratio: float | None = None
    volume_ratio: float | None = None
    emotion: str | None = None
    pre_break_time: str | None = None
    post_break_time: str | None = None
    spell_words: list[str] = Field(default_factory=list)

    def normalize(self) -> None:
        self.speed_ratio = _clamp(self.speed_ratio, 0.6, 1.5)
        self.volume_ratio = _clamp(self.volume_ratio, 0.5, 2.0)

        if isinstance(self.emotion, str):
            emotion = self.emotion.strip()
            self.emotion = emotion or None
        else:
            self.emotion = None

        def _clean_break(value: Any) -> str | None:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        self.pre_break_time = _clean_break(self.pre_break_time)
        self.post_break_time = _clean_break(self.post_break_time)

        cleaned: list[str] = []
        for word in self.spell_words:
            if not isinstance(word, str):
                continue
            candidate = word.strip()
            if candidate and candidate not in cleaned:
                cleaned.append(candidate)
        self.spell_words = cleaned

    def merge(self, override: "CartesiaSSMLConfig") -> "CartesiaSSMLConfig":
        data = self.model_dump()
        incoming = override.model_dump()
        for key, value in incoming.items():
            if value is None:
                continue
            if key == "spell_words":
                base_words = data.get(key, []) or []
                combined: list[str] = []
                for word in [*base_words, *value]:
                    if not isinstance(word, str):
                        continue
                    candidate = word.strip()
                    if candidate and candidate not in combined:
                        combined.append(candidate)
                data[key] = combined
            else:
                data[key] = value
        return CartesiaSSMLConfig(**data)


class CartesiaTTSConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""

    sample_rate: int = 16000
    enable_words: bool = False
    dump: bool = False
    dump_path: str = "/tmp"
    params: dict[str, Any] = Field(default_factory=dict)
    ssml: CartesiaSSMLConfig = Field(default_factory=CartesiaSSMLConfig)

    def update_params(self) -> None:
        params = self._ensure_dict(self.params)
        self.params = params

        # Remove params that are not used
        for key in ("transcript", "context_id", "stream", "add_timestamps"):
            if key in params:
                del params[key]

        if "api_key" in params:
            self.api_key = params["api_key"]
            del params["api_key"]

        if "base_url" in params:
            self.base_url = params["base_url"]
            del params["base_url"]

        # Use default sample rate value
        if "sample_rate" in params:
            self.sample_rate = params["sample_rate"]
            # Remove sample_rate from params to avoid parameter error
            del params["sample_rate"]

        output_format = self._ensure_dict(
            params.setdefault("output_format", {})
        )
        params["output_format"] = output_format

        # Use custom sample rate value
        if "sample_rate" in output_format:
            self.sample_rate = output_format["sample_rate"]
        else:
            output_format["sample_rate"] = self.sample_rate

        ##### use fixed value #####
        output_format["container"] = "raw"
        output_format["encoding"] = "pcm_s16le"

        generation_config = self._ensure_dict(
            params.setdefault("generation_config", {})
        )
        params["generation_config"] = generation_config
        generation_config.setdefault("speed", 1.0)
        generation_config.setdefault("volume", 1.0)

        if "ssml" in params:
            ssml_config = params["ssml"]
            if isinstance(ssml_config, dict):
                self.ssml = self.ssml.merge(CartesiaSSMLConfig(**ssml_config))
            del params["ssml"]

        self.ssml.normalize()

    def merge_updates(self, updates: dict[str, Any]) -> "CartesiaTTSConfig":
        """Create a new config by deep-merging *updates* into the current one."""
        current = self.model_dump()

        def _deep_merge(base: dict, patch: dict) -> dict:
            out = dict(base)
            for k, v in patch.items():
                if (
                    k in out
                    and isinstance(out[k], dict)
                    and isinstance(v, dict)
                ):
                    out[k] = _deep_merge(out[k], v)
                else:
                    out[k] = v
            return out

        merged = _deep_merge(current, updates)
        new_config = CartesiaTTSConfig.model_validate(merged)
        new_config.update_params()
        return new_config

    def to_str(self, sensitive_handling: bool = True) -> str:
        """
        Convert the configuration to a string representation, masking sensitive data.
        """
        if not sensitive_handling:
            return f"{self}"

        return str(
            utils.redact_json(
                self.model_dump(),
            ),
        )

    @staticmethod
    def _ensure_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return dict(value)
