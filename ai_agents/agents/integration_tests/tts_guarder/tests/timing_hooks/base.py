#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Immutable provider references for the common timing checks."""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class ReferenceWord:
    word: str
    start_ms: Fraction
    end_ms: Fraction


@dataclass(frozen=True)
class RequestTimingReference:
    vendor: str
    sample_rate: int
    channels: int
    pcm_bytes: int
    captions: tuple[tuple[ReferenceWord, ...], ...]
    error: str | None = None
