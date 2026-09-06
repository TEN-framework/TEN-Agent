"""Make `realtime` importable as a top-level package.

`openai_mllm_python/__init__.py` imports `addon`, which pulls in the native
`ten_runtime` extension module. The realtime protocol layer itself depends on
nothing beyond the standard library, so importing it directly keeps these
tests runnable without a built runtime.
"""

import sys
from pathlib import Path

EXTENSION_ROOT = Path(__file__).resolve().parent.parent

if str(EXTENSION_ROOT) not in sys.path:
    sys.path.insert(0, str(EXTENSION_ROOT))
