#!/usr/bin/env python3
"""Validate a declarative Tutti Agent Extension package without network access."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_SCHEMA = "tutti.agent.manifest.v1"
PROFILE_SCHEMAS = {
    "discovery": "tutti.agent.discovery.v1",
    "tools": "tutti.agent.tools.v1",
    "capabilities": "tutti.agent.capabilities.v1",
    "composer": "tutti.agent.composer.v1",
}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
EXACT_NPM_PACKAGE = re.compile(
    r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*@"
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"
)


class ValidationError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"expected JSON object: {path}")
    return value


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    return value


def resolve_reference(root: Path, value: Any, field: str) -> Path:
    reference = require_string(value, field)
    pure = PurePosixPath(reference)
    if pure.is_absolute() or ".." in pure.parts or "\\" in reference:
        raise ValidationError(f"{field} must be a safe relative POSIX path")
    resolved = (root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"{field} escapes package root") from exc
    if not resolved.is_file():
        raise ValidationError(f"{field} does not exist: {reference}")
    return resolved


def check_package_tree(root: Path) -> None:
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValidationError(f"symlinks are not allowed: {relative}")
        mode = path.stat().st_mode
        if path.is_file() and mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise ValidationError(f"executable files are not allowed: {relative}")
        if any(part in {".git", "node_modules"} for part in relative.parts):
            raise ValidationError(f"development directory is not allowed: {relative}")


def check_install(runtime: dict[str, Any]) -> None:
    if runtime.get("kind") != "standard-acp":
        raise ValidationError("runtime.kind must be standard-acp")
    install = runtime.get("install")
    launch = runtime.get("launch")
    if not isinstance(install, dict) or not isinstance(launch, dict):
        raise ValidationError("runtime.install and runtime.launch must be objects")
    if install.get("runner") != "npm":
        raise ValidationError("runtime.install.runner must be npm")
    args = install.get("args")
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValidationError("runtime.install.args must be a string array")
    packages = [arg for arg in args if EXACT_NPM_PACKAGE.fullmatch(arg)]
    if len(packages) != 1:
        raise ValidationError("install args must contain exactly one exact npm package@version")
    forbidden = [arg for arg in args if arg in {"--global", "-g"}]
    if forbidden or "${installRoot}" not in args:
        raise ValidationError("npm install must be local to ${installRoot}")
    executable = require_string(launch.get("executable"), "runtime.launch.executable")
    if not executable.startswith("${installRoot}/") or ".." in PurePosixPath(executable).parts:
        raise ValidationError("launch executable must stay under ${installRoot}")
    launch_args = launch.get("args")
    if not isinstance(launch_args, list) or not all(isinstance(arg, str) for arg in launch_args):
        raise ValidationError("runtime.launch.args must be a string array")


def validate(root: Path) -> None:
    root = root.resolve()
    manifest_path = root / "tutti.agent.json"
    if not root.is_dir() or not manifest_path.is_file():
        raise ValidationError(f"package must contain tutti.agent.json: {root}")
    check_package_tree(root)
    manifest = read_json(manifest_path)
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA:
        raise ValidationError(f"schemaVersion must be {MANIFEST_SCHEMA}")
    require_string(manifest.get("agentKey"), "agentKey")
    version = require_string(manifest.get("version"), "version")
    if not SEMVER.fullmatch(version):
        raise ValidationError("version must be semantic versioning without a range")
    require_string(manifest.get("name"), "name")
    require_string(manifest.get("description"), "description")

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise ValidationError("runtime must be an object")
    check_install(runtime)

    icon = manifest.get("icon")
    if not isinstance(icon, dict) or icon.get("type") != "asset":
        raise ValidationError("icon must be an extension asset")
    resolve_reference(root, icon.get("src"), "icon.src")

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        raise ValidationError("profiles must be an object")
    for profile_name, schema in PROFILE_SCHEMAS.items():
        profile_path = resolve_reference(root, profiles.get(profile_name), f"profiles.{profile_name}")
        if read_json(profile_path).get("schemaVersion") != schema:
            raise ValidationError(f"profiles.{profile_name} must use {schema}")

    localization = manifest.get("localizationInfo")
    if not isinstance(localization, dict):
        raise ValidationError("localizationInfo must be an object")
    locale_files = [
        resolve_reference(root, localization.get("defaultFile"), "localizationInfo.defaultFile")
    ]
    additional = localization.get("additionalLocales", [])
    if not isinstance(additional, list):
        raise ValidationError("localizationInfo.additionalLocales must be an array")
    for index, locale in enumerate(additional):
        if not isinstance(locale, dict):
            raise ValidationError(f"additionalLocales[{index}] must be an object")
        require_string(locale.get("locale"), f"additionalLocales[{index}].locale")
        locale_files.append(
            resolve_reference(root, locale.get("file"), f"additionalLocales[{index}].file")
        )
    for locale_file in locale_files:
        locale = read_json(locale_file)
        require_string(locale.get("agent.name"), f"{locale_file.name}.agent.name")
        require_string(locale.get("agent.description"), f"{locale_file.name}.agent.description")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Directory containing tutti.agent.json")
    args = parser.parse_args()
    try:
        validate(args.package)
    except ValidationError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "package": os.fspath(args.package.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
