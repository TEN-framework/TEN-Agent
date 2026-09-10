#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Blaze TTS package."""

try:
    from . import addon as addon  # noqa: F401
except Exception:  # pragma: no cover - host unit tests without ten_runtime
    addon = None

from .blaze_tts import BlazeTTSConfig, BlazeTTSExtension

__all__ = ["BlazeTTSExtension", "BlazeTTSConfig"]
