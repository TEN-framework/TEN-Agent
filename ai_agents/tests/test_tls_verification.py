from __future__ import annotations

import ast
from pathlib import Path

EXTENSIONS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "agents"
    / "ten_packages"
    / "extension"
)


def _attribute_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Attribute):
        return None
    if isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return node.attr


def _find_insecure_tls_settings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _attribute_name(node.func) == "ssl._create_unverified_context":
                violations.append(
                    f"{path.relative_to(EXTENSIONS_ROOT)}:{node.lineno} "
                    "uses an unverified SSL context"
                )

        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if not isinstance(target, ast.Attribute):
                continue
            if target.attr == "check_hostname" and isinstance(
                node.value, ast.Constant
            ):
                if node.value.value is False:
                    violations.append(
                        f"{path.relative_to(EXTENSIONS_ROOT)}:{node.lineno} "
                        "disables hostname verification"
                    )
            if (
                target.attr == "verify_mode"
                and _attribute_name(node.value) == "ssl.CERT_NONE"
            ):
                violations.append(
                    f"{path.relative_to(EXTENSIONS_ROOT)}:{node.lineno} "
                    "disables certificate verification"
                )

    return violations


def test_production_extensions_do_not_disable_tls_verification():
    violations = []
    for path in EXTENSIONS_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        violations.extend(_find_insecure_tls_settings(path))

    assert violations == []
