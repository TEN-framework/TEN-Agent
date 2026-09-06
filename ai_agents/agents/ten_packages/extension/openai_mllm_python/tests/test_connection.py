"""The beta handshake must not come back.

`connection.py` and `extension.py` both import the native `ten_runtime`
module, so these checks read them as source rather than importing them. That
keeps them runnable without a built runtime, which is the point of confining
the wire format to a layer that depends on nothing.
"""

import ast
import functools
from pathlib import Path

EXTENSION_ROOT = Path(__file__).resolve().parent.parent
CONNECTION_PY = EXTENSION_ROOT / "realtime" / "connection.py"
EXTENSION_PY = EXTENSION_ROOT / "extension.py"


@functools.lru_cache(maxsize=None)
def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _assignment(path: Path, name: str) -> str:
    """The value assigned to a module-level constant."""
    for node in _module(path).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path.name}")


def _dataclass_field(path: Path, cls: str, field: str) -> str:
    """The default of an annotated field on a dataclass."""
    for node in ast.walk(_module(path)):
        if not (isinstance(node, ast.ClassDef) and node.name == cls):
            continue
        for stmt in node.body:
            if (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == field
                and stmt.value is not None
            ):
                return ast.literal_eval(stmt.value)
    raise AssertionError(f"{cls}.{field} not found in {path.name}")


@functools.lru_cache(maxsize=None)
def _attribute_accesses(path: Path) -> frozenset:
    """Every `x.y` attribute name referenced in the module.

    Like `_string_literals`, this reads the AST so that comments naming a
    symbol cannot decide the result.
    """
    return frozenset(
        f"{node.value.id}.{node.attr}"
        for node in ast.walk(_module(path))
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    )


@functools.lru_cache(maxsize=None)
def _string_literals(path: Path) -> frozenset:
    """Every string constant in the module.

    Comments are absent from the AST, so prose explaining why the beta header
    is gone cannot make these checks pass or fail.
    """
    return frozenset(
        node.value
        for node in ast.walk(_module(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def test_configured_default_model_is_a_realtime_model() -> None:
    """This is the default deployments actually get.

    `start_connection` always passes `model=self.config.model`, so
    `DEFAULT_VIRTUAL_MODEL` in connection.py is never reached. The defect this
    guards against is `OpenAIRealtimeConfig.model` defaulting to `gpt-4o`,
    which is not a realtime model and cannot connect.
    """
    model = _dataclass_field(EXTENSION_PY, "OpenAIRealtimeConfig", "model")

    assert model.startswith("gpt-realtime")


def test_connection_fallback_model_is_a_realtime_model() -> None:
    assert _assignment(CONNECTION_PY, "DEFAULT_VIRTUAL_MODEL").startswith(
        "gpt-realtime"
    )


def test_beta_header_is_not_sent() -> None:
    literals = _string_literals(CONNECTION_PY)

    assert "OpenAI-Beta" not in literals
    assert "realtime=v1" not in literals


def test_openai_branch_authenticates_with_bearer() -> None:
    """GA documents a Bearer token; aiohttp's BasicAuth sends Basic."""
    assert "aiohttp.BasicAuth" not in _attribute_accesses(CONNECTION_PY)
    assert "Authorization" in _string_literals(CONNECTION_PY)


def test_azure_vendor_still_uses_api_key_header() -> None:
    """The Azure path keeps its own header scheme."""
    assert "api-key" in _string_literals(CONNECTION_PY)


def test_vendor_errors_are_propagated_downstream() -> None:
    """A rejected session.update must not be a silent hang.

    The socket stays open when GA rejects an event, so logging alone leaves
    the graph waiting on mllm_server_session_ready against a connection that
    looks healthy.
    """
    called = {
        node.func.attr
        for node in ast.walk(_module(EXTENSION_PY))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "send_mllm_error" in called


def test_assistant_items_use_the_ga_content_type() -> None:
    """GA renamed assistant content parts to output_text/output_audio.

    Sending the beta `text` type makes the service reject every assistant
    item, which silently halves the replayed context on reconnect.
    """
    accesses = _attribute_accesses(EXTENSION_PY)

    assert "ContentType.OutputText" in accesses
    assert "ContentType.Text" not in accesses
    # Input parts kept their beta names in GA.
    assert "ContentType.InputText" in accesses
