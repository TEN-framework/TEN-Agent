from typing import Any, Literal, get_args
import copy
from ten_ai_base import utils
from pydantic import BaseModel, Field


FlushMode = Literal["off", "first_chunk", "every_sentence"]
FLUSH_MODES: tuple[str, ...] = get_args(FlushMode)
DEFAULT_FLUSH_MODE = "first_chunk"


class FishAudioTTSConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    sample_rate: int = 16000
    dump: bool = False
    dump_path: str = "/tmp"
    backend: str = "speech-1.5"
    flush_mode: str = DEFAULT_FLUSH_MODE
    flush_mode_warning: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    def update_params(self) -> None:
        if "api_key" in self.params:
            self.api_key = self.params["api_key"]
            del self.params["api_key"]

        if "base_url" in self.params:
            self.base_url = self.params["base_url"]
            del self.params["base_url"]

        if "sample_rate" in self.params:
            self.sample_rate = int(self.params["sample_rate"])
        else:
            self.params["sample_rate"] = self.sample_rate

        if "format" not in self.params:
            self.params["format"] = "pcm"

        if "references" in self.params:
            del self.params["references"]

        if "mp3_bitrate" in self.params:
            del self.params["mp3_bitrate"]

        if "opus_bitrate" in self.params:
            del self.params["opus_bitrate"]

        if "backend" in self.params:
            self.backend = self.params["backend"]
            del self.params["backend"]

        if "flush_mode" in self.params:
            # Drop it from params so it never reaches the vendor payload.
            self.flush_mode = str(self.params["flush_mode"])
            del self.params["flush_mode"]

        # An invalid value must not abort initialization: keep running with the
        # default and let the extension surface the problem as an error log.
        if self.flush_mode not in FLUSH_MODES:
            self.flush_mode_warning = (
                f"Invalid flush_mode {self.flush_mode!r}; allowed values are "
                f"{', '.join(FLUSH_MODES)}; falling back to "
                f"{DEFAULT_FLUSH_MODE!r}"
            )
            self.flush_mode = DEFAULT_FLUSH_MODE
        else:
            self.flush_mode_warning = None

        if "text" in self.params:
            del self.params["text"]

    def to_str(self, sensitive_handling: bool = True) -> str:
        """
        Convert the configuration to a string representation, masking sensitive data.
        """

        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)

        # Encrypt sensitive fields
        if config.api_key:
            config.api_key = utils.encrypt(config.api_key)
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])

        return f"{config}"
