#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from typing import List
from dataclasses import dataclass, field
import copy
from ten_ai_base.config import BaseConfig


@dataclass
class SpeechmaticsASRConfig(BaseConfig):
    key: str = ""
    chunk_ms: int = 160  # 160ms per chunk
    language: str = "en-US"
    sample_rate: int = 16000
    uri: str = "wss://eu2.rt.speechmatics.com/v2"
    max_delay_mode: str = "flexible"  # "flexible" or "fixed"
    max_delay: float = 2.0  # 0.7 - 4.0
    encoding: str = "pcm_s16le"
    enable_partials: bool = True
    operating_point: str = "enhanced"
    hotwords: List[str] = field(default_factory=list)

    # True: streaming output final words, False: streaming output final sentences
    enable_word_final_mode: bool = False

    drain_mode: str = "mute_pkg"  # "disconnect" or "mute_pkg"
    mute_pkg_duration_ms: int = 1500

    dump: bool = False
    dump_path: str = "."

    def to_str(self, sensitive_handling: bool = False) -> str:
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)
        if config.key:
            config.key = config.key[:4] + "****"
        return f"{config}"
