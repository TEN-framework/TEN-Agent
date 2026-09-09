from typing import Any, Dict, List
from pydantic import BaseModel, Field
from ten_ai_base.utils import encrypt

# The Speko router accepts BCP-47 language tags and strips the region
# itself before dialing a provider. TEN asr_result consumers expect
# full BCP-47 tags, so bare ISO 639-1 codes are normalized on report.
# The set below covers the languages the router currently enables.
LANGUAGE_TAG_MAP = {
    "en": "en-US",
    "ar": "ar-AE",
    "de": "de-DE",
    "es": "es-ES",
    "fr": "fr-FR",
    "hi": "hi-IN",
    "nb": "nb-NO",
    "ta": "ta-IN",
    "te": "te-IN",
    "ru": "ru-RU",
}

# Routing objectives understood by the router.
VALID_OBJECTIVES = {"latency", "quality", "cost", "balanced"}


class SpekoASRConfig(BaseModel):
    """Configuration for the Speko router streaming transcription socket.

    The router benchmarks STT providers per language and dials the best
    one for this session, so there is no per-vendor model knob here.
    Routing preferences travel as `X-Speko-*` headers on the WebSocket
    handshake; stream behavior travels in the first config frame.
    """

    api_key: str = ""
    url: str = "wss://api.speko.ai/v1/transcribe/stream"
    language: str = "en"  # BCP-47 tag or bare ISO 639-1 code
    sample_rate: int = 16000
    interim_results: bool = True

    # Routing preferences (all optional; the API key's routing policy
    # applies when they are left empty).
    objective: str = ""  # latency | quality | cost | balanced
    allow: str = ""  # CSV of provider or provider:model ids
    deny: str = ""  # CSV of provider or provider:model ids
    max_price: str = ""  # USD per minute ceiling, e.g. "0.5"

    # Forwarded verbatim as the config frame's providerOptions field,
    # keyed by provider (e.g. {"deepgram": {"endpointing": 1200}}).
    provider_options: Dict[str, Any] = Field(default_factory=dict)

    dump: bool = False
    dump_path: str = "/tmp"
    params: Dict[str, Any] = Field(default_factory=dict)
    black_list_params: List[str] = Field(
        default_factory=lambda: [
            "api_key",
            "url",
            "language",
            "sample_rate",
            "interim_results",
            "objective",
            "allow",
            "deny",
            "max_price",
            "provider_options",
            "dump",
            "dump_path",
        ]
    )

    def is_black_list_params(self, key: str) -> bool:
        return key in self.black_list_params

    def update(self, params: Dict[str, Any]) -> None:
        """Update configuration with additional parameters."""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_json(self, sensitive_handling: bool = False) -> str:
        """Convert config to JSON string, optionally masking secrets."""
        config_dict = self.model_dump()
        if sensitive_handling and self.api_key:
            config_dict["api_key"] = encrypt(config_dict["api_key"])
        if config_dict["params"]:
            for key, value in config_dict["params"].items():
                if key == "api_key":
                    config_dict["params"][key] = encrypt(value)
        return str(config_dict)

    def validate_config(self) -> None:
        """Reject values the router would refuse at the handshake."""
        if self.objective and self.objective not in VALID_OBJECTIVES:
            raise ValueError(
                f"objective must be one of {sorted(VALID_OBJECTIVES)}, "
                f"got {self.objective!r}"
            )
        if not 8000 <= self.sample_rate <= 48000:
            raise ValueError(
                f"sample_rate must be within 8000..48000, "
                f"got {self.sample_rate}"
            )

    def config_frame(self) -> Dict[str, Any]:
        """First text frame on the socket. The router rejects unknown
        fields, so only documented fields are ever included."""
        frame: Dict[str, Any] = {
            "type": "config",
            "language": self.language,
            "interimResults": bool(self.interim_results),
            "sampleRate": int(self.sample_rate),
        }
        if self.provider_options:
            frame["providerOptions"] = self.provider_options
        return frame

    def routing_headers(self) -> Dict[str, str]:
        """Optional X-Speko-* headers for the WebSocket handshake."""
        headers: Dict[str, str] = {}
        if self.objective:
            headers["X-Speko-Objective"] = self.objective
        if self.allow:
            headers["X-Speko-Allow"] = self.allow
        if self.deny:
            headers["X-Speko-Deny"] = self.deny
        if self.max_price:
            headers["X-Speko-Max-Price"] = str(self.max_price)
        return headers

    def report_language(self, vendor_language: str | None = None) -> str:
        """Language tag reported in asr_result: BCP-47.

        A configured full tag (e.g. en-IN) wins — the caller asked for
        it explicitly. Otherwise the router's per-frame detected
        language (when present) or the configured bare code is
        normalized via LANGUAGE_TAG_MAP.
        """
        if "-" in self.language:
            return self.language
        code = (vendor_language or self.language).split("-")[0].lower()
        return LANGUAGE_TAG_MAP.get(code, code)
