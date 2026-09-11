import json
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1]


def test_default_properties_are_declared_in_manifest() -> None:
    manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text())
    defaults = json.loads((PACKAGE_ROOT / "property.json").read_text())
    properties = manifest["api"]["property"]["properties"]

    assert set(properties) == {"params", "dump", "dump_path"}
    assert set(defaults) <= set(properties)
    assert properties["params"]["type"] == "object"
    assert set(defaults["params"]) <= set(properties["params"]["properties"])


@pytest.mark.parametrize(
    "config_path",
    sorted((PACKAGE_ROOT / "tests" / "configs").glob("*.json")),
    ids=lambda path: path.name,
)
def test_guarder_configs_use_nested_params(config_path: Path) -> None:
    config = json.loads(config_path.read_text())

    assert set(config) <= {"params", "dump", "dump_path"}
    assert "params" in config
