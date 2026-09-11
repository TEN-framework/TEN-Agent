import json
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1]


def test_manifest_defaults_and_registration():
    manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text())
    defaults = json.loads((PACKAGE_ROOT / "property.json").read_text())
    properties = manifest["api"]["property"]["properties"]
    assert manifest["name"] == PACKAGE_ROOT.name
    assert f'"{PACKAGE_ROOT.name}"' in (PACKAGE_ROOT / "addon.py").read_text()
    assert set(defaults) <= set(properties)
    assert set(defaults["params"]) <= set(properties["params"]["properties"])
    interface = "asr" if "asr" in PACKAGE_ROOT.name else "tts"
    assert manifest["api"]["interface"][0]["import_uri"].endswith(
        f"/{interface}-interface.json"
    )


@pytest.mark.parametrize(
    "config_path",
    sorted((PACKAGE_ROOT / "tests/configs").glob("*.json")),
    ids=lambda p: p.name,
)
def test_guarder_config_properties_are_declared(config_path):
    config = json.loads(config_path.read_text())
    manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text())
    properties = manifest["api"]["property"]["properties"]
    assert set(config) <= set(properties)
    assert "params" in config
    assert set(config["params"]) <= set(properties["params"]["properties"])
