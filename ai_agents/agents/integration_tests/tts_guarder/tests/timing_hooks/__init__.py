#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Optional vendor observers for the subtitle alignment test."""

from .registry import install_timing_hook

__all__ = ["install_timing_hook"]
