from typing import Any
import copy

from ten_ai_base import utils
from ten_ai_base.tts2_http import AsyncTTS2HttpConfig

from pydantic import Field

# The router normalizes every provider's output to signed 16-bit mono
# 24 kHz little-endian PCM at its edge, so failover cannot change the
# audio format mid-request. This is not configurable.
SPEKO_OUTPUT_SAMPLE_RATE = 24000

DEFAULT_BASE_URL = "https://api.speko.ai"

# Routing objectives understood by the router.
VALID_OBJECTIVES = {"latency", "quality", "cost", "balanced"}

# Keys consumed by this extension rather than forwarded to the API.
NON_PAYLOAD_KEYS = [
    "api_key",
    "base_url",
    "objective",
    "allow",
    "deny",
    "max_price",
    "text",
    "input",
    "sample_rate",
    "response_format",
]


class SpekoTTSConfig(AsyncTTS2HttpConfig):
    """Configuration for TTS through the Speko model router.

    The router benchmarks TTS providers per language and dials the best
    one per request (`model: "auto"`), failing over between providers
    before the first byte. Pinning a `voice` id restricts routing to
    the provider that owns the voice.
    """

    dump: bool = Field(default=False, description="Speko TTS dump")
    dump_path: str = Field(
        default="/tmp",
        description="Speko TTS dump path",
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Speko TTS params"
    )

    def update_params(self) -> None:
        """Normalize params before use."""
        # The base URL is consumed by the client, never forwarded.
        if "base_url" in self.params:
            base_url = str(self.params["base_url"]).rstrip("/")
        else:
            base_url = DEFAULT_BASE_URL
        self.params["base_url"] = base_url

        # Benchmark-led routing unless a caller pins a model.
        if "model" not in self.params:
            self.params["model"] = "auto"

        # The router only streams raw PCM on this route; the sample
        # rate is fixed at the router edge.
        if "response_format" in self.params:
            del self.params["response_format"]
        if "sample_rate" in self.params:
            del self.params["sample_rate"]

    def to_str(self, sensitive_handling: bool = True) -> str:
        """Convert config to string with optional secret masking."""
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])
        return f"{config}"

    def validate(self) -> None:
        """Reject values the router would refuse."""
        if "api_key" not in self.params or not self.params["api_key"]:
            raise ValueError("API key is required for Speko TTS")
        objective = (
            self.params["objective"] if "objective" in self.params else ""
        )
        if objective and objective not in VALID_OBJECTIVES:
            raise ValueError(
                f"objective must be one of {sorted(VALID_OBJECTIVES)}, "
                f"got {objective!r}"
            )
