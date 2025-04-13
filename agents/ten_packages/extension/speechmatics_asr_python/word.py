#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

from dataclasses import dataclass
from typing import List
from .config import SpeechmaticsASRConfig
from .language_utils import is_space_separated_language


@dataclass
class SpeechmaticsASRWord:
    word: str = ""
    start_ms: int = 0
    duration_ms: int = 0
    is_punctuation: bool = False


def convert_words_to_sentence(
    words: List[SpeechmaticsASRWord], config: SpeechmaticsASRConfig
) -> str:
    if is_space_separated_language(config.language):
        return " ".join([word.word for word in words])
    else:
        return "".join([word.word for word in words])


def get_sentence_start_ms(words: List[SpeechmaticsASRWord]) -> int:
    return words[0].start_ms


def get_sentence_duration_ms(words: List[SpeechmaticsASRWord]) -> int:
    return sum([word.duration_ms for word in words])
