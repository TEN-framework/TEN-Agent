import json
from typing import Annotated, Any

from pydantic import BaseModel, Field

from .const import DEFAULT_URL, SAMPLE_RATE
from .recognition import validate_endpoint


class OrukRealtimeASRConfig(BaseModel):
    """Configuration for the Oruk realtime (streaming WebSocket) ASR extension.

    Credentials come from ``params.api_key`` / ``params.key`` (typically wired
    from ``${env:ORUK_API_KEY}``) and are sent only in the WebSocket upgrade's
    Authorization header, never in the URL.
    """

    dump: bool = False
    dump_path: str = "."

    params: Annotated[dict[str, Any], Field(default_factory=dict)]

    @property
    def api_key(self) -> str:
        for name in ("api_key", "key"):
            value = self.params.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @property
    def url(self) -> str:
        value = self.params.get("url")
        return value if isinstance(value, str) and value else DEFAULT_URL

    @property
    def sample_rate(self) -> int:
        return int(self.params.get("sample_rate", SAMPLE_RATE))

    @property
    def language(self) -> str:
        value = self.params.get("language")
        return value if isinstance(value, str) and value else "auto"

    @property
    def phrase_emotions(self) -> bool:
        return bool(self.params.get("phrase_emotions", True))

    @property
    def diarize(self) -> bool:
        return bool(self.params.get("diarize", False))

    @property
    def asr_result_language(self) -> str:
        """Language code stamped on results when the server does not supply one."""
        value = self.params.get("result_language_default")
        if isinstance(value, str) and value:
            return value
        # Use the BCP 47 undetermined tag when no output locale is known.
        return "und" if self.language == "auto" else self.language

    def validate_config(self) -> None:
        validate_endpoint(self.url)
        if not self.api_key:
            raise ValueError(
                "oruk_realtime_asr_python requires an Oruk API key "
                "(params.api_key / params.key, e.g. ${env:ORUK_API_KEY})."
            )
        if any(c.isspace() for c in self.api_key):
            raise ValueError("Oruk API key must not contain whitespace.")
        if self.sample_rate != SAMPLE_RATE:
            raise ValueError(
                "oruk_realtime_asr_python requires a 16 kHz mono PCM16 input pipeline."
            )

    def to_json(self, sensitive_handling: bool = False) -> str:
        data = self.model_dump()
        if sensitive_handling:
            params = dict(data.get("params", {}))
            for name in ("api_key", "key"):
                if params.get(name):
                    value = str(params[name])
                    params[name] = (
                        value[:2] + "***" + value[-2:]
                        if len(value) > 6
                        else "***"
                    )
            data["params"] = params
        return json.dumps(data)
