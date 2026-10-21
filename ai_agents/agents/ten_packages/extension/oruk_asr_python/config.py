import json
from typing import Annotated, Any

from pydantic import BaseModel, Field

from .const import DEFAULT_SAMPLE_RATE, ORUKEET_MODEL


class OrukASRConfig(BaseModel):
    """Configuration for the local Orukeet ASR extension.

    Orukeet runs fully on CPU via onnx-asr. It needs no API key and uploads no
    audio, so there are no secrets to redact. The model is fixed to Orukeet with
    automatic language detection; only a handful of runtime knobs are accepted.
    """

    # Framework-level options (declared as first-class properties, not in params).
    dump: bool = False
    dump_path: str = "."

    params: Annotated[dict[str, Any], Field(default_factory=dict)]

    @property
    def sample_rate(self) -> int:
        return int(self.params.get("sample_rate", DEFAULT_SAMPLE_RATE))

    @property
    def cache_dir(self) -> str | None:
        value = self.params.get("cache_dir")
        return value if isinstance(value, str) and value else None

    @property
    def local_files_only(self) -> bool:
        return bool(self.params.get("local_files_only", False))

    @property
    def asr_result_language(self) -> str:
        """The language code reported on results.

        Orukeet detects language automatically and does not return a code, so
        callers may pin a default to stamp on every result (e.g. "en-US").
        """
        value = self.params.get("result_language_default")
        return str(value) if isinstance(value, str) and value else "und"

    def validate_config(self) -> None:
        if self.sample_rate != DEFAULT_SAMPLE_RATE:
            raise ValueError(
                "oruk_asr_python (Orukeet) requires a 16 kHz mono PCM16 input pipeline."
            )
        model = self.params.get("model")
        if model not in (None, "", ORUKEET_MODEL, "oruk/orukeet"):
            raise ValueError(
                f"oruk_asr_python uses the fixed '{ORUKEET_MODEL}' model; got {model!r}."
            )
        language = self.params.get("language")
        if language not in (None, "", "auto"):
            raise ValueError(
                "Orukeet uses automatic language detection; set language to 'auto'."
            )

    def to_json(self, sensitive_handling: bool = False) -> str:
        # Local config has no credentials; sensitive_handling is a no-op kept for
        # parity with the streaming extensions' config interface.
        _ = sensitive_handling
        return json.dumps(self.model_dump())
