from typing import Any
import copy
from ten_ai_base import utils
from pydantic import BaseModel, Field


class FishAudioTTSConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    sample_rate: int = 16000
    dump: bool = False
    dump_path: str = "/tmp"
    backend: str = "speech-1.5"
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
