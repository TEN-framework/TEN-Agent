#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

LANGUAGE_MAP = {
    "zh-CN": "cmn",
    "en-US": "en",
    "fr-FR": "fr",
    "de-DE": "de",
    "it-IT": "it",
    "ja-JP": "ja",
    "ko-KR": "ko",
    "pt-PT": "pt",
    "ru-RU": "ru",
    "es-ES": "es",
    "ar-AE": "ar",
    "hi-IN": "hi",
}


def get_speechmatics_language(language: str) -> str:
    return LANGUAGE_MAP.get(language, "auto")


def is_space_separated_language(language: str) -> bool:
    return language not in ["zh-CN", "ja-JP", "ko-KR"]
