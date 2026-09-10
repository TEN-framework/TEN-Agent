from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ten_ai_base import utils


class DeepdubTTSConfig(BaseModel):
    api_key: str = ""
    url: str = ""
    model: str = "dd-etts-3.2"
    locale: str = "en-US"
    voice_prompt_id: str = ""
    sample_rate: int = 48000
    channels: int = 1
    # PCM in network byte order, signed 16-bit LE — matches TEN's audio_frame expectations.
    format: str = "s16le"
    accept_emojis: bool = False
    temperature: Optional[float] = None
    variance: Optional[float] = None
    tempo: Optional[float] = None
    prompt_boost: Optional[bool] = None
    keepalive_interval_seconds: float = 20.0
    dump: bool = False
    dump_path: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    black_list_params: List[str] = Field(default_factory=list)

    def update_params(self) -> None:
        p = self.params
        for k in (
            "api_key",
            "url",
            "model",
            "locale",
            "voice_prompt_id",
            "sample_rate",
            "channels",
            "format",
            "accept_emojis",
            "temperature",
            "variance",
            "tempo",
            "prompt_boost",
            "keepalive_interval_seconds",
        ):
            if k in p:
                setattr(self, k, p[k])
                del p[k]

    def validate_params(self) -> None:
        missing = [
            n
            for n in ("api_key", "url", "voice_prompt_id")
            if not getattr(self, n)
        ]
        if missing:
            raise ValueError(
                f"required fields are missing or empty: params.{', params.'.join(missing)}"
            )
        if self.sample_rate not in (8000, 16000, 22050, 24000, 44100, 48000):
            raise ValueError(f"unsupported sample_rate: {self.sample_rate}")
        if self.format not in ("s16le", "wav", "mp3", "opus", "mulaw"):
            raise ValueError(f"unsupported format: {self.format}")

    def to_str(self, sensitive_handling: bool = False) -> str:
        if not sensitive_handling:
            return f"{self}"
        c = self.copy(deep=True)
        if c.api_key:
            c.api_key = utils.encrypt(c.api_key)
        return f"{c}"
