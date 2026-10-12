#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Select a fresh hook without importing unselected vendor implementations."""

from contextlib import contextmanager
from importlib import import_module

HOOK_FACTORIES = {
    "minimax_tts_websocket_duplex": (
        ".minimax_duplex",
        "MiniMaxTimingHook",
    ),
}


@contextmanager
def install_timing_hook(extension_name, config, monkeypatch):
    spec = HOOK_FACTORIES.get(extension_name)
    if spec is None:
        yield None
        return
    module = import_module(spec[0], package=__package__)
    hook = getattr(module, spec[1])()
    with monkeypatch.context() as scoped_patch:
        hook.install(scoped_patch, config)
        yield hook
