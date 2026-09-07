import json
import re
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1]


def test_package_versions_match() -> None:
    manifest = json.loads(
        (PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = re.search(
        r"^\[project\]\s*$\n(?P<body>.*?)(?=^\[|\Z)",
        pyproject,
        re.MULTILINE | re.DOTALL,
    )

    assert project is not None, "pyproject.toml is missing [project]"
    pyproject_version = re.search(
        r'^version\s*=\s*"([^"]+)"',
        project.group("body"),
        re.MULTILINE,
    )

    assert pyproject_version is not None, "[project] is missing a version"
    version = manifest["version"]
    assert version == pyproject_version.group(1)

    production_readiness = (
        PACKAGE_ROOT / "docs" / "PRODUCTION_READINESS.md"
    ).read_text(encoding="utf-8")
    changelog = (PACKAGE_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"version `{version}`." in production_readiness
    assert re.search(
        rf"^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$",
        changelog,
        re.MULTILINE,
    )


def test_default_properties_are_declared_in_manifest() -> None:
    manifest = json.loads(
        (PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    defaults = json.loads(
        (PACKAGE_ROOT / "property.json").read_text(encoding="utf-8")
    )
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
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert set(config) <= {"params", "dump", "dump_path"}
    assert "params" in config
