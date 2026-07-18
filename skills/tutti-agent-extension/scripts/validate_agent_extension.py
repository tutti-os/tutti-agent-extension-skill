#!/usr/bin/env python3
"""Validate a declarative Tutti Agent Extension package without network access."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_SCHEMA = "tutti.agent.manifest.v2"
PROFILE_SCHEMAS = {
    "discovery": "tutti.agent.discovery.v1",
    "tools": "tutti.agent.tools.v1",
    "capabilities": "tutti.agent.capabilities.v1",
    "composer": "tutti.agent.composer.v1",
    "events": "tutti.agent.events.v1",
}
REQUIRED_PROFILES = {"discovery", "tools", "capabilities", "composer"}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
EXACT_NPM_PACKAGE = re.compile(
    r"^@[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*@"
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"
)
EXACT_UV_PACKAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*=="
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[A-Za-z0-9._+-]*)?$"
)
BINARY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
AGENT_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
VERSION_CONSTRAINT_PART = re.compile(
    r"^(?:>=|>|<=|<)[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$"
)
TOOL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CONFIG_OPTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SLASH_COMMAND_NAME = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,63}$")
PRESENTATION_ASSET_LIMIT = 256 << 10
ALLOWED_PACKAGE_SUFFIXES = {".json", ".md", ".svg", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_PACKAGE_DOCS = {"AGENTS.md", "README.md", "LICENSE", "NOTICE"}
ALLOWED_PLACEHOLDERS = {"${projectRoot}", "${installRoot}", "${platform}"}
PERMISSION_SEMANTICS = {
    "read-only",
    "ask-before-write",
    "accept-edits",
    "auto",
    "locked-down",
    "full-access",
}
SLASH_COMMAND_EFFECTS = {
    "submitImmediate",
    "showStatus",
    "activateGoalMode",
    "togglePlanMode",
}


class ValidationError(Exception):
    pass


def reject_unknown_keys(
    value: dict[str, Any], allowed: set[str], field: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValidationError(
            f"{field} contains unsupported fields: {', '.join(unknown)}"
        )


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


def require_string_array(
    value: Any, field: str, *, non_empty: bool = False
) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"{field} must be a string array")
    if non_empty and not value:
        raise ValidationError(f"{field} must not be empty")
    return value


def require_safe_relative_path(value: Any, field: str) -> str:
    path = require_string(value, field)
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path:
        raise ValidationError(f"{field} must be a safe relative POSIX path")
    return path


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


def validate_presentation_asset(root: Path, descriptor: Any, field: str) -> Path:
    if not isinstance(descriptor, dict) or descriptor.get("type") != "asset":
        raise ValidationError(f"{field} must be an extension asset")
    reject_unknown_keys(descriptor, {"type", "src"}, field)
    path = resolve_reference(root, descriptor.get("src"), f"{field}.src")
    if path.stat().st_size > PRESENTATION_ASSET_LIMIT:
        raise ValidationError(f"{field} exceeds the 256 KiB presentation asset limit")
    content_type, _ = mimetypes.guess_type(path.name)
    if not content_type or not content_type.startswith("image/"):
        raise ValidationError(f"{field} must use a supported image file type")
    if path.suffix.lower() == ".svg":
        try:
            lower = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError as exc:
            raise ValidationError(f"{field} SVG must be valid UTF-8") from exc
        active = re.search(
            r"<(?:[a-z_][\w.-]*:)?(?:script|foreignobject|style|set|animate|"
            r"animatemotion|animatetransform|discard|handler|listener|audio|video|"
            r"iframe|object|embed)\b|javascript:|"
            r"\s(?:[a-z_][\w.-]*:)?(?:on[a-z][\w.-]*|style)\s*=|"
            r"\sxml:base\s*=|@import|<!doctype|<!entity|&#|\\",
            lower,
        )
        remote_href = any(
            not match.group(2).strip().startswith("#")
            for match in re.finditer(
                r"(?:xlink:)?href\s*=\s*(['\"])(.*?)\1", lower, re.DOTALL
            )
        )
        remote_url = any(
            not match.group(2).strip().startswith("#")
            for match in re.finditer(
                r"url\s*\(\s*(['\"]?)(.*?)\1\s*\)", lower, re.DOTALL
            )
        )
        if active or remote_href or remote_url:
            raise ValidationError(f"{field} SVG contains active or remote content")
    return path


def check_package_tree(root: Path) -> None:
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        if any(character in relative_text for character in ("\\", "\n", "\r", "\0")):
            raise ValidationError(f"unsafe package path: {relative_text!r}")
        if any(part.startswith(".") for part in relative.parts):
            raise ValidationError(f"hidden package entries are not allowed: {relative}")
        if path.is_symlink():
            raise ValidationError(f"symlinks are not allowed: {relative}")
        mode = path.stat().st_mode
        if path.is_file() and mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise ValidationError(f"executable files are not allowed: {relative}")
        if (
            path.is_file()
            and path.suffix.lower() not in ALLOWED_PACKAGE_SUFFIXES
            and relative_text not in ALLOWED_PACKAGE_DOCS
        ):
            raise ValidationError(f"unsupported package file type: {relative}")
        if any(part in {".git", "node_modules"} for part in relative.parts):
            raise ValidationError(f"development directory is not allowed: {relative}")


def check_declared_files(root: Path, declared: set[Path]) -> None:
    allowed = {path.resolve() for path in declared}
    for document in ALLOWED_PACKAGE_DOCS:
        candidate = root / document
        if candidate.is_file():
            allowed.add(candidate.resolve())
    for path in root.rglob("*"):
        if path.is_file() and path.resolve() not in allowed:
            raise ValidationError(
                f"package contains undeclared file: {path.relative_to(root)}"
            )


def validate_template_argument(value: str, field: str) -> None:
    if any(character in value for character in "|;&`\n\r<>") or "$(" in value:
        raise ValidationError(f"{field} contains forbidden shell syntax")
    for placeholder in re.findall(r"\$\{[^}]+\}", value):
        if placeholder not in ALLOWED_PLACEHOLDERS:
            raise ValidationError(
                f"{field} contains unsupported placeholder {placeholder}"
            )


def check_install(runtime: dict[str, Any]) -> None:
    reject_unknown_keys(runtime, {"kind", "install", "launch"}, "runtime")
    if runtime.get("kind") != "standard-acp":
        raise ValidationError("runtime.kind must be standard-acp")
    install = runtime.get("install")
    launch = runtime.get("launch")
    if not isinstance(install, dict) or not isinstance(launch, dict):
        raise ValidationError("runtime.install and runtime.launch must be objects")
    reject_unknown_keys(install, {"runner", "args"}, "runtime.install")
    reject_unknown_keys(launch, {"executable", "args"}, "runtime.launch")
    runner = install.get("runner")
    if runner not in {"npm", "pnpm", "uv"}:
        raise ValidationError("runtime.install.runner must be npm, pnpm, or uv")
    args = require_string_array(
        install.get("args"), "runtime.install.args", non_empty=True
    )
    for index, argument in enumerate(args):
        validate_template_argument(argument, f"runtime.install.args[{index}]")
        if "${projectRoot}" in argument:
            raise ValidationError("runtime install cannot depend on a project root")
    package_pattern = EXACT_UV_PACKAGE if runner == "uv" else EXACT_NPM_PACKAGE
    expected_prefix = {
        "npm": ["install", "--prefix", "${installRoot}"],
        "pnpm": ["add", "--dir", "${installRoot}"],
        "uv": ["pip", "install", "--target", "${installRoot}"],
    }[runner]
    if (
        len(args) != len(expected_prefix) + 1
        or args[:-1] != expected_prefix
        or not package_pattern.fullmatch(args[-1])
    ):
        syntax = "package==version" if runner == "uv" else "package@version"
        raise ValidationError(
            f"runtime install must use the constrained {runner} form with one exact {syntax}"
        )
    executable = require_string(launch.get("executable"), "runtime.launch.executable")
    validate_template_argument(executable, "runtime.launch.executable")
    if (
        not executable.startswith("${installRoot}/")
        or ".." in PurePosixPath(executable).parts
    ):
        raise ValidationError("launch executable must stay under ${installRoot}")
    launch_args = require_string_array(launch.get("args"), "runtime.launch.args")
    for index, argument in enumerate(launch_args):
        validate_template_argument(argument, f"runtime.launch.args[{index}]")


def validate_discovery_profile(profile: dict[str, Any]) -> None:
    reject_unknown_keys(profile, {"schemaVersion", "candidates"}, "discovery")
    candidates = profile.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValidationError("discovery.candidates must be a non-empty array")
    for index, candidate in enumerate(candidates):
        field = f"discovery.candidates[{index}]"
        if not isinstance(candidate, dict):
            raise ValidationError(f"{field} must be an object")
        reject_unknown_keys(
            candidate, {"binaryNames", "version", "launchArgs", "probe"}, field
        )
        binaries = require_string_array(
            candidate.get("binaryNames"), f"{field}.binaryNames", non_empty=True
        )
        if any(not BINARY_NAME.fullmatch(binary) for binary in binaries):
            raise ValidationError(
                f"{field}.binaryNames contains an invalid binary name"
            )
        version = candidate.get("version")
        if not isinstance(version, dict):
            raise ValidationError(f"{field}.version must be an object")
        reject_unknown_keys(version, {"args", "constraint"}, f"{field}.version")
        version_args = require_string_array(
            version.get("args"), f"{field}.version.args", non_empty=True
        )
        launch_args = require_string_array(
            candidate.get("launchArgs"), f"{field}.launchArgs", non_empty=True
        )
        for index, argument in enumerate(version_args):
            validate_template_argument(argument, f"{field}.version.args[{index}]")
        for index, argument in enumerate(launch_args):
            validate_template_argument(argument, f"{field}.launchArgs[{index}]")
        constraint = require_string(
            version.get("constraint"), f"{field}.version.constraint"
        )
        if any(
            not VERSION_CONSTRAINT_PART.fullmatch(part)
            for part in constraint.split()
        ):
            raise ValidationError(f"{field}.version.constraint is unsupported")
        probe = candidate.get("probe")
        if not isinstance(probe, dict) or probe.get("kind") != "acp-initialize":
            raise ValidationError(f"{field}.probe.kind must be acp-initialize")
        reject_unknown_keys(probe, {"kind", "timeoutMs"}, f"{field}.probe")
        timeout_ms = probe.get("timeoutMs")
        if not isinstance(timeout_ms, int) or not 100 <= timeout_ms <= 30_000:
            raise ValidationError(f"{field}.probe.timeoutMs must be 100..30000")


def validate_tools_profile(profile: dict[str, Any]) -> None:
    reject_unknown_keys(profile, {"schemaVersion", "tools"}, "tools")
    tools = profile.get("tools")
    if not isinstance(tools, list):
        raise ValidationError("tools.tools must be an array")
    seen_ids: set[str] = set()
    for index, tool in enumerate(tools):
        field = f"tools.tools[{index}]"
        if not isinstance(tool, dict):
            raise ValidationError(f"{field} must be an object")
        reject_unknown_keys(
            tool,
            {"match", "canonicalId", "category", "presentation", "fileEffect", "command"},
            field,
        )
        match = tool.get("match")
        if not isinstance(match, dict):
            raise ValidationError(f"{field}.match must be an object")
        reject_unknown_keys(match, {"ids"}, f"{field}.match")
        ids = require_string_array(
            match.get("ids"), f"{field}.match.ids", non_empty=True
        )
        normalized_ids = [item.strip().lower() for item in ids]
        if (
            len(normalized_ids) != len(set(normalized_ids))
            or any(not TOOL_ID.fullmatch(item) for item in ids)
            or seen_ids.intersection(normalized_ids)
        ):
            raise ValidationError(
                f"{field}.match.ids must contain unique safe tool IDs"
            )
        seen_ids.update(normalized_ids)
        require_string(tool.get("canonicalId"), f"{field}.canonicalId")
        if "category" in tool:
            require_string(tool.get("category"), f"{field}.category")
        if "presentation" in tool:
            presentation = tool["presentation"]
            if not isinstance(presentation, dict):
                raise ValidationError(f"{field}.presentation must be an object")
            reject_unknown_keys(
                presentation, {"renderer", "titleKey"}, f"{field}.presentation"
            )
            require_string(
                presentation.get("renderer"), f"{field}.presentation.renderer"
            )
            require_string(
                presentation.get("titleKey"), f"{field}.presentation.titleKey"
            )
        if "fileEffect" in tool:
            if tool["fileEffect"] != {"source": "acp-content-diff"}:
                raise ValidationError(
                    f"{field}.fileEffect must use acp-content-diff"
                )
        if "command" in tool:
            command = tool["command"]
            if not isinstance(command, dict):
                raise ValidationError(f"{field}.command must be an object")
            reject_unknown_keys(command, {"source", "path"}, f"{field}.command")
            if command.get("source") != "input":
                raise ValidationError(f"{field}.command.source must be input")
            require_string(command.get("path"), f"{field}.command.path")


def validate_capabilities_profile(profile: dict[str, Any]) -> dict[str, bool]:
    reject_unknown_keys(profile, {"schemaVersion", "declared"}, "capabilities")
    declared = profile.get("declared")
    if not isinstance(declared, dict):
        raise ValidationError("capabilities.declared must be an object")
    if not all(
        isinstance(key, str) and isinstance(value, bool)
        for key, value in declared.items()
    ):
        raise ValidationError("capabilities.declared values must be booleans")
    return declared


def validate_skill_root(root: Any, index: int) -> None:
    field = f"composer.skills.roots[{index}]"
    if not isinstance(root, dict):
        raise ValidationError(f"{field} must be an object")
    reject_unknown_keys(root, {"scope", "path"}, field)
    if root.get("scope") not in {"workspace", "user"}:
        raise ValidationError(f"{field}.scope must be workspace or user")
    require_safe_relative_path(root.get("path"), f"{field}.path")


def validate_composer_profile(profile: dict[str, Any]) -> bool:
    reject_unknown_keys(
        profile,
        {
            "schemaVersion",
            "model",
            "permission",
            "configOptions",
            "permissionModes",
            "slashCommands",
            "skills",
        },
        "composer",
    )
    model = profile.get("model")
    if model is not None:
        if not isinstance(model, dict) or model.get("source") != "acp-session-models":
            raise ValidationError("composer.model.source must be acp-session-models")
        reject_unknown_keys(model, {"source"}, "composer.model")
    permission = profile.get("permission")
    if permission is not None:
        if (
            not isinstance(permission, dict)
            or permission.get("source") != "acp-session-modes"
        ):
            raise ValidationError("composer.permission.source must be acp-session-modes")
        reject_unknown_keys(permission, {"source"}, "composer.permission")
    config_options = profile.get("configOptions")
    if config_options is not None:
        if not isinstance(config_options, dict):
            raise ValidationError("composer.configOptions must be an object")
        reject_unknown_keys(
            config_options, {"model", "permission", "reasoning"}, "composer.configOptions"
        )
        for name, option in config_options.items():
            field = f"composer.configOptions.{name}"
            if not isinstance(option, dict):
                raise ValidationError(f"{field} must be an object")
            reject_unknown_keys(option, {"acpOptionId"}, field)
            option_id = require_string(option.get("acpOptionId"), f"{field}.acpOptionId")
            if not CONFIG_OPTION_ID.fullmatch(option_id):
                raise ValidationError(f"{field}.acpOptionId is unsupported")
    if model is None and permission is None and config_options is None:
        raise ValidationError(
            "composer must declare legacy model/permission sources or configOptions"
        )
    modes = profile.get("permissionModes")
    if not isinstance(modes, list):
        raise ValidationError("composer.permissionModes must be an array")
    runtime_ids: set[str] = set()
    for index, mode in enumerate(modes):
        field = f"composer.permissionModes[{index}]"
        if not isinstance(mode, dict):
            raise ValidationError(f"{field} must be an object")
        reject_unknown_keys(mode, {"runtimeId", "semantic"}, field)
        runtime_id = require_string(mode.get("runtimeId"), f"{field}.runtimeId").strip()
        if runtime_id in runtime_ids:
            raise ValidationError(f"{field}.runtimeId must be unique")
        runtime_ids.add(runtime_id)
        if mode.get("semantic") not in PERMISSION_SEMANTICS:
            raise ValidationError(f"{field}.semantic is unsupported")
    slash_commands = profile.get("slashCommands")
    if slash_commands is not None:
        if not isinstance(slash_commands, dict):
            raise ValidationError("composer.slashCommands must be an object")
        reject_unknown_keys(
            slash_commands,
            {"commandCatalogAuthoritative", "commands"},
            "composer.slashCommands",
        )
        if not isinstance(slash_commands.get("commandCatalogAuthoritative"), bool):
            raise ValidationError(
                "composer.slashCommands.commandCatalogAuthoritative must be boolean"
            )
        commands = slash_commands.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ValidationError("composer.slashCommands.commands must not be empty")
        names: set[str] = set()
        for index, command in enumerate(commands):
            field = f"composer.slashCommands.commands[{index}]"
            if not isinstance(command, dict):
                raise ValidationError(f"{field} must be an object")
            reject_unknown_keys(command, {"name", "effect"}, field)
            name = require_string(command.get("name"), f"{field}.name").lower()
            if not SLASH_COMMAND_NAME.fullmatch(name) or name in names:
                raise ValidationError(f"{field}.name must be unique and supported")
            names.add(name)
            effect = command.get("effect")
            if effect is not None and effect not in SLASH_COMMAND_EFFECTS:
                raise ValidationError(f"{field}.effect is unsupported")
    skills = profile.get("skills")
    if skills is None:
        return False
    if not isinstance(skills, dict):
        raise ValidationError("composer.skills must be an object")
    reject_unknown_keys(
        skills, {"invocation", "triggerPrefix", "roots"}, "composer.skills"
    )
    if skills.get("invocation") not in {"textTrigger", "promptItem"}:
        raise ValidationError(
            "composer.skills.invocation must be textTrigger or promptItem"
        )
    trigger = require_string(
        skills.get("triggerPrefix"), "composer.skills.triggerPrefix"
    )
    if trigger not in {"/", "$"}:
        raise ValidationError("composer.skills.triggerPrefix must be / or $")
    roots = skills.get("roots")
    if not isinstance(roots, list) or not roots:
        raise ValidationError("composer.skills.roots must be a non-empty array")
    for index, root in enumerate(roots):
        validate_skill_root(root, index)
    return True


def validate_profiles(profile_values: dict[str, dict[str, Any]]) -> None:
    validate_discovery_profile(profile_values["discovery"])
    validate_tools_profile(profile_values["tools"])
    capabilities = validate_capabilities_profile(profile_values["capabilities"])
    composer_has_skills = validate_composer_profile(profile_values["composer"])
    if bool(capabilities.get("skills")) != composer_has_skills:
        raise ValidationError(
            "capabilities.declared.skills must match the composer.skills declaration"
        )


def validate(root: Path) -> None:
    root = root.resolve()
    manifest_path = root / "tutti.agent.json"
    if not root.is_dir() or not manifest_path.is_file():
        raise ValidationError(f"package must contain tutti.agent.json: {root}")
    check_package_tree(root)
    manifest = read_json(manifest_path)
    reject_unknown_keys(
        manifest,
        {
            "schemaVersion",
            "agentKey",
            "version",
            "name",
            "description",
            "icon",
            "maskIcon",
            "heroImage",
            "runtime",
            "profiles",
            "localizationInfo",
        },
        "manifest",
    )
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA:
        raise ValidationError(f"schemaVersion must be {MANIFEST_SCHEMA}")
    agent_key = require_string(manifest.get("agentKey"), "agentKey")
    if not AGENT_KEY.fullmatch(agent_key):
        raise ValidationError("agentKey is unsupported")
    version = require_string(manifest.get("version"), "version")
    if not SEMVER.fullmatch(version):
        raise ValidationError("version must be semantic versioning without a range")
    require_string(manifest.get("name"), "name")
    require_string(manifest.get("description"), "description")

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise ValidationError("runtime must be an object")
    check_install(runtime)

    declared_files = {manifest_path.resolve()}
    declared_files.add(
        validate_presentation_asset(root, manifest.get("icon"), "icon").resolve()
    )
    if manifest.get("maskIcon") is not None:
        declared_files.add(
            validate_presentation_asset(
                root, manifest.get("maskIcon"), "maskIcon"
            ).resolve()
        )
    declared_files.add(
        validate_presentation_asset(
            root, manifest.get("heroImage"), "heroImage"
        ).resolve()
    )

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        raise ValidationError("profiles must be an object")
    reject_unknown_keys(profiles, set(PROFILE_SCHEMAS), "profiles")
    profile_values: dict[str, dict[str, Any]] = {}
    missing_profiles = sorted(REQUIRED_PROFILES - set(profiles))
    if missing_profiles:
        raise ValidationError(
            f"profiles is missing required entries: {', '.join(missing_profiles)}"
        )
    for profile_name, profile_reference in profiles.items():
        schema = PROFILE_SCHEMAS[profile_name]
        profile_path = resolve_reference(
            root, profile_reference, f"profiles.{profile_name}"
        )
        profile = read_json(profile_path)
        if profile.get("schemaVersion") != schema:
            raise ValidationError(f"profiles.{profile_name} must use {schema}")
        profile_values[profile_name] = profile
        declared_files.add(profile_path.resolve())
    validate_profiles(profile_values)

    localization = manifest.get("localizationInfo")
    if not isinstance(localization, dict):
        raise ValidationError("localizationInfo must be an object")
    reject_unknown_keys(
        localization,
        {"defaultLocale", "defaultFile", "additionalLocales"},
        "localizationInfo",
    )
    locale_files = [
        resolve_reference(
            root, localization.get("defaultFile"), "localizationInfo.defaultFile"
        )
    ]
    additional = localization.get("additionalLocales", [])
    if not isinstance(additional, list):
        raise ValidationError("localizationInfo.additionalLocales must be an array")
    for index, locale in enumerate(additional):
        if not isinstance(locale, dict):
            raise ValidationError(f"additionalLocales[{index}] must be an object")
        reject_unknown_keys(
            locale, {"locale", "file"}, f"additionalLocales[{index}]"
        )
        require_string(locale.get("locale"), f"additionalLocales[{index}].locale")
        locale_files.append(
            resolve_reference(
                root, locale.get("file"), f"additionalLocales[{index}].file"
            )
        )
    for locale_file in locale_files:
        declared_files.add(locale_file.resolve())
        locale = read_json(locale_file)
        require_string(locale.get("agent.name"), f"{locale_file.name}.agent.name")
        require_string(
            locale.get("agent.description"), f"{locale_file.name}.agent.description"
        )
    check_declared_files(root, declared_files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package", type=Path, help="Directory containing tutti.agent.json"
    )
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
