#
# Copyright © 2025 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
import json
import os
import shutil
import sys
import tempfile

from .utils import cmd_exec


def run_install(tman_bin: str, config_file: str, app_dir: str) -> None:
    returncode, output_text = cmd_exec.run_cmd_realtime(
        [tman_bin, f"--config-file={config_file}", "--yes", "install"],
        cwd=app_dir,
    )
    if returncode != 0:
        print(output_text)
        assert False, "tman install failed"


def set_dependency_version(app_dir: str, version: str) -> None:
    manifest_path = os.path.join(app_dir, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    manifest["dependencies"][0]["version"] = f"={version}"
    with open(manifest_path, "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)


def test_downgrade_removes_files_that_are_not_in_the_old_version():
    base_path = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.join(base_path, "../../../../")

    if sys.platform == "win32":
        os.environ["PATH"] = (
            os.path.join(root_dir, "ten_manager/lib") + ";" + os.getenv("PATH", "")
        )
        tman_bin = os.path.join(root_dir, "ten_manager/bin/tman.exe")
    else:
        tman_bin = os.path.join(root_dir, "ten_manager/bin/tman")

    config_file = os.path.join(root_dir, "tests/local_registry/config.json")
    source_app_dir = os.path.join(base_path, "test_app")

    with tempfile.TemporaryDirectory() as temp_dir:
        app_dir = os.path.join(temp_dir, "test_app")
        shutil.copytree(source_app_dir, app_dir)

        run_install(tman_bin, config_file, app_dir)

        package_dir = os.path.join(app_dir, "ten_packages", "extension", "ext_h")
        v2_only_file = os.path.join(package_dir, "v2_only.txt")
        assert os.path.isfile(v2_only_file)

        set_dependency_version(app_dir, "1.0.0")
        run_install(tman_bin, config_file, app_dir)

        with open(
            os.path.join(package_dir, "manifest.json"),
            "r",
            encoding="utf-8",
        ) as manifest_file:
            installed_manifest = json.load(manifest_file)

        assert installed_manifest["version"] == "1.0.0"
        assert not os.path.exists(v2_only_file)


if __name__ == "__main__":
    test_downgrade_removes_files_that_are_not_in_the_old_version()
