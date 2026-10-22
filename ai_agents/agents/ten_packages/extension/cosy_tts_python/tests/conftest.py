from collections.abc import Callable

import pytest

from cosy_tts_python import extension as extension_module


@pytest.fixture
def monotonic_clock(monkeypatch: pytest.MonkeyPatch) -> Callable:
    def install(*values: float) -> None:
        clock = iter(values)
        monkeypatch.setattr(
            extension_module,
            "_monotonic_seconds",
            lambda: next(clock),
        )

    return install
