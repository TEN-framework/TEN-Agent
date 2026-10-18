#
# Copyright © 2025 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
import subprocess
import json
import os
import re

try:
    from jinja2 import Template
except ModuleNotFoundError:
    class Template:
        """Fallback when jinja2 is not installed.

        Supports {{ VARIABLE }} replacement used by version templates.
        """

        def __init__(self, content: str):
            self.content = content

        def render(self, **kwargs) -> str:
            result = self.content
            for key, val in kwargs.items():
                result = re.sub(
                    rf"\{{\{{\s*{re.escape(key)}\s*\}}\}}", str(val), result
                )
            return result


class PkgInfo:
    def __init__(self, pkg_type, pkg_name):
        self.pkg_type = pkg_type
        self.pkg_name = pkg_name

    def __eq__(self, value):
        return (
            self.pkg_type == value.pkg_type and self.pkg_name == value.pkg_name
        )

    def __hash__(self):
        return hash((self.pkg_type, self.pkg_name))


def touch(path):
    with open(path, "a", encoding="utf-8"):
        try:
            os.utime(path, follow_symlinks=False)
        except Exception:
            try:
                # If follow_symlinks parameter is not supported, fall back to
                # default behavior
                os.utime(path)
            except Exception:
                exit(1)


def get_latest_git_tag() -> str:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "--always"],
        capture_output=True,
        text=True,
        check=True,
    )

    if result.returncode != 0:
        raise subprocess.SubprocessError("Failed to execute git command")

    return result.stdout.strip()


def update_c_preserved_metadata_version(
    year: str,
    year_month: str,
    version: str,
    src_path: str,
    template_path: str,
) -> None:
    with open(template_path, "r", encoding="utf-8") as file:
        template_content = file.read()

    template = Template(template_content)
    rendered_content = template.render(
        VERSION=version, YEAR=year, YEAR_MONTH=year_month
    )

    with open(src_path, "w", encoding="utf-8") as file:
        file.write(rendered_content)


def update_version_in_manifest_json_file_for_pkgs(
    log_level: int,
    version: str,
    src_path: str,
    pkg_infos: list[PkgInfo],
) -> None:
    if log_level > 0:
        print(f"Checking {src_path} for updates...")

    if not os.path.exists(src_path):
        touch(src_path)

    with open(src_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    pkg_info = PkgInfo(data.get("type"), data.get("name"))
    if pkg_info in pkg_infos and data.get("version") != version:
        if log_level > 0:
            print(f"Updating version in {src_path}.")

        # Update the version in the JSON data.
        data["version"] = version
        with open(src_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            # Notify that the content of the src_path has changed.
            touch(src_path)


# {
#   "type": "<type-in-main-manifest>",
#   "name": "<name-in-main-manifest>",
#   "version": "...", <- update here
#   ...
# }
def update_version_in_manifest_json_file(
    log_level: int,
    version: str,
    src_path: str,
) -> None:
    if log_level > 0:
        print(f"Checking {src_path} for updates...")

    if not os.path.exists(src_path):
        touch(src_path)

    with open(src_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if data.get("version") != version:
        if log_level > 0:
            print(f"Updating version in {src_path}.")

        # Update the version in the JSON data.
        data["version"] = version

        with open(src_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

            # Notify that the content of the src_path has changed.
            touch(src_path)
    else:
        if log_level > 0:
            print(f"No update needed for {src_path}; versions match.")


# {
#   ...
#   "dependencies": [
#     {
#       "type": "<type-in-main-manifest>",
#       "name": "<name-in-main-manifest>",
#       "version": "...", <- update here
#     }
#   }
#   ...
# }
def update_dependency_version_in_manifest_json_file(
    log_level: int,
    version: str,
    src_path: str,
    pkgs: list[PkgInfo],
) -> None:
    if log_level > 0:
        print(f"Checking {src_path} for updates...")

    if not os.path.exists(src_path):
        touch(src_path)

    with open(src_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    updated = False
    for dependency in data.get("dependencies", []):
        dependent_pkg = PkgInfo(dependency.get("type"), dependency.get("name"))

        if dependent_pkg in pkgs and dependency.get("version") != version:
            dependency["version"] = version
            updated = True

    for dev_dependency in data.get("dev_dependencies", []):
        dependent_pkg = PkgInfo(
            dev_dependency.get("type"), dev_dependency.get("name")
        )

        if dependent_pkg in pkgs and dev_dependency.get("version") != version:
            dev_dependency["version"] = version
            updated = True

    if updated:
        if log_level > 0:
            print(f"Updating version in {src_path}.")

        with open(src_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

            # Notify that the content of the src_path has changed.
            touch(src_path)
    else:
        if log_level > 0:
            print(f"No update needed for {src_path}; versions match.")


def update_version_source_file_of_tman(
    log_level: int,
    year: str,
    year_month: str,
    version: str,
    src_path: str,
    template_path: str,
) -> None:
    update_needed = False

    if os.path.exists(src_path):
        with open(src_path, "r", encoding="utf-8") as file:
            content = file.read()

        if f'VERSION: &str = "{version}"' not in content:
            update_needed = True
            if log_level > 0:
                print(
                    f"Version mismatch found. Updating version in {src_path}."
                )
    else:
        update_needed = True

    if update_needed:
        with open(template_path, "r", encoding="utf-8") as file:
            template_content = file.read()

        template = Template(template_content)

        rendered_content = template.render(
            VERSION=version, YEAR=year, YEAR_MONTH=year_month
        )

        with open(src_path, "w", encoding="utf-8") as file:
            file.write(rendered_content)
    else:
        if log_level > 0:
            print(f"No update needed for {src_path}; versions match.")
