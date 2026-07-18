#!/usr/bin/env python3
"""Create a minimal, provider-independent Tutti Agent Extension repository."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

KEY = re.compile(r"^[a-z][a-z0-9-]*$")
BINARY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
EXACT_NPM = re.compile(
    r"^@[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*@"
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"
)
EXACT_UV = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*=="
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[A-Za-z0-9._+-]*)?$"
)
ASSETS = Path(__file__).resolve().parents[1] / "assets"
PRESENTATION_ASSET_SUFFIXES = {".jpeg", ".jpg", ".png", ".svg", ".webp"}
PRESENTATION_ASSET_LIMIT = 256 << 10


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def hero_image_asset_path(args: argparse.Namespace) -> str:
    return f"assets/hero-image{args.hero_image.suffix.lower()}"


def sidebar_icon_asset_path(args: argparse.Namespace) -> str:
    return f"assets/sidebar-icon{args.sidebar_icon.suffix.lower()}"


def runtime_install_args(args: argparse.Namespace) -> list[str]:
    if args.runtime_runner == "npm":
        return ["install", "--prefix", "${installRoot}", args.runtime_package]
    if args.runtime_runner == "pnpm":
        return ["add", "--dir", "${installRoot}", args.runtime_package]
    return ["pip", "install", "--target", "${installRoot}", args.runtime_package]


def runtime_executable(args: argparse.Namespace) -> str:
    if args.runtime_executable:
        return args.runtime_executable
    if args.runtime_runner in {"npm", "pnpm"}:
        return f"${{installRoot}}/node_modules/.bin/{args.binary}"
    return f"${{installRoot}}/bin/{args.binary}"


def validate_args(args: argparse.Namespace) -> None:
    if not KEY.fullmatch(args.agent_key):
        raise SystemExit("--agent-key must match ^[a-z][a-z0-9-]*$")
    if not args.provider.startswith("acp:"):
        raise SystemExit("--provider must use the open acp:<key> form")
    if not KEY.fullmatch(args.provider.removeprefix("acp:")):
        raise SystemExit("--provider must use the open acp:<key> form")
    if not SEMVER.fullmatch(args.extension_version):
        raise SystemExit("--extension-version must be an exact semantic version")
    if args.runtime_runner in {"npm", "pnpm"} and not EXACT_NPM.fullmatch(
        args.runtime_package
    ):
        raise SystemExit("--runtime-package must be an exact npm/pnpm package@version")
    if args.runtime_runner == "uv" and not EXACT_UV.fullmatch(args.runtime_package):
        raise SystemExit("--runtime-package must be an exact Python package==version")
    if not BINARY.fullmatch(args.binary):
        raise SystemExit("--binary must be a binary name without a path")
    executable = runtime_executable(args)
    if not executable.startswith("${installRoot}/") or ".." in Path(executable).parts:
        raise SystemExit("--runtime-executable must stay under ${installRoot}")
    if not BINARY.fullmatch(args.signing_key_id):
        raise SystemExit("--signing-key-id contains unsupported characters")
    if not re.fullmatch(r"https://[^\s]+", args.release_assets_base_url):
        raise SystemExit(
            "--release-assets-base-url must be an HTTPS URL without whitespace"
        )
    if not args.hero_image.is_file():
        raise SystemExit(f"--hero-image must be an existing file: {args.hero_image}")
    if args.hero_image.suffix.lower() not in PRESENTATION_ASSET_SUFFIXES:
        raise SystemExit("--hero-image must be JPEG, PNG, SVG, or WebP")
    if args.hero_image.stat().st_size > PRESENTATION_ASSET_LIMIT:
        raise SystemExit("--hero-image must not exceed 256 KiB")
    if args.sidebar_icon is not None:
        if not args.sidebar_icon.is_file():
            raise SystemExit(
                f"--sidebar-icon must be an existing file: {args.sidebar_icon}"
            )
        if args.sidebar_icon.suffix.lower() not in PRESENTATION_ASSET_SUFFIXES:
            raise SystemExit("--sidebar-icon must be JPEG, PNG, SVG, or WebP")
        if args.sidebar_icon.stat().st_size > PRESENTATION_ASSET_LIMIT:
            raise SystemExit("--sidebar-icon must not exceed 256 KiB")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"output directory is not empty: {args.output}")


def manifest(args: argparse.Namespace) -> dict[str, Any]:
    value = {
        "schemaVersion": "tutti.agent.manifest.v1",
        "agentKey": args.agent_key,
        "version": args.extension_version,
        "name": args.display_name,
        "description": args.description,
        "icon": {"type": "asset", "src": "assets/icon.svg"},
        "heroImage": {"type": "asset", "src": hero_image_asset_path(args)},
        "runtime": {
            "kind": "standard-acp",
            "install": {
                "runner": args.runtime_runner,
                "args": runtime_install_args(args),
            },
            "launch": {
                "executable": runtime_executable(args),
                "args": args.launch_arg,
            },
        },
        "profiles": {
            "discovery": "profiles/discovery.json",
            "tools": "profiles/tools.json",
            "capabilities": "profiles/capabilities.json",
            "composer": "profiles/composer.json",
        },
        "localizationInfo": {
            "defaultLocale": "en",
            "defaultFile": "locales/en.json",
            "additionalLocales": [{"locale": "zh-CN", "file": "locales/zh-CN.json"}],
        },
    }
    if args.sidebar_icon is not None:
        value["sidebarIcon"] = {
            "type": "asset",
            "src": sidebar_icon_asset_path(args),
        }
    return value


def create(args: argparse.Namespace) -> None:
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ASSETS / "repository", root, dirs_exist_ok=True)
    (root / "infra/aws").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ASSETS / "aws/agent-extension-release-infrastructure.yaml",
        root / "infra/aws/agent-extension-release-infrastructure.yaml",
    )
    write(root, ".gitignore", "node_modules/\nbuild/\n.DS_Store\n")
    write(
        root,
        "AGENTS.md",
        "# Agent instructions\n\n"
        "Keep the package declarative and provider-independent. Do not commit secrets, "
        "runtime binaries, generated archives, or node_modules. Validate the built package "
        "before release. Use Conventional Commits with DCO sign-off.\n",
    )
    write(
        root,
        "README.md",
        f"# {args.display_name} Agent Extension for Tutti\n\n"
        f"Declarative Tutti integration for `{args.runtime_package}` through standard ACP.\n\n"
        "## Validate\n\n```sh\npnpm install --frozen-lockfile\npnpm check\n"
        "pnpm package:tutti-agent\n```\n\n"
        "Verify the real ACP runtime without sending a paid prompt:\n\n"
        f"```sh\npython3 scripts/probe_acp_runtime.py --cwd /path/to/project -- {args.binary} "
        f"{' '.join(args.launch_arg)}\n```\n\n"
        "The signed manifest references a transparent conversation-mask glyph through "
        "`icon`, optional colored identity artwork through `sidebarIcon`, and the home "
        "poster through `heroImage`. Tutti promotes the colored identity to selectors, "
        "Message Center, mentions, and rail surfaces while preserving the mask glyph for "
        "conversation rows. Keep each packaged image at or below 256 KiB.\n\n"
        "## Release\n\nThe repository-owned `.github/workflows/release.yml` builds, "
        "signs, and uploads immutable releases using `scripts/release/`. Configure "
        "the documented GitHub OIDC/AWS variables and the "
        "`TUTTI_AGENT_EXTENSION_SIGNING_PRIVATE_KEY` repository secret before dispatch. "
        "For new infrastructure, deploy "
        "`infra/aws/agent-extension-release-infrastructure.yaml`.\n",
    )
    write(
        root,
        "package.json",
        dump(
            {
                "name": f"@tutti-os/agent-extension-{args.agent_key}",
                "version": args.extension_version,
                "private": True,
                "type": "module",
                "engines": {"node": ">=24"},
                "scripts": {
                    "check": (
                        "node scripts/check.mjs && "
                        "python3 scripts/validate_agent_extension.py "
                        "build/tutti-agent/package && "
                        "node --test scripts/release/test/*.test.mjs"
                    ),
                    "package:tutti-agent": "node scripts/package.mjs",
                },
                "dependencies": {"semver": "7.8.0"},
                "packageManager": "pnpm@10.11.0",
            }
        ),
    )
    write(
        root,
        "pnpm-lock.yaml",
        'lockfileVersion: "9.0"\n\nsettings:\n  autoInstallPeers: true\n'
        "  excludeLinksFromLockfile: false\n\nimporters:\n  .:\n"
        "    dependencies:\n      semver:\n        specifier: 7.8.0\n"
        "        version: 7.8.0\n\npackages:\n  semver@7.8.0:\n"
        "    resolution:\n      {\n        integrity: sha512-AcM7dV/5ul4EekoQ29Agm5vri8JNqRyj39o0qpX6vDF2GZrtutZl5RwgD1XnZjiTAfncsJhMI48QQH3sN87YNA==,\n      }\n"
        '    engines: { node: ">=10" }\n    hasBin: true\n\nsnapshots:\n'
        "  semver@7.8.0: {}\n",
    )
    shutil.copy2(
        Path(__file__).resolve().with_name("validate_agent_extension.py"),
        root / "scripts/validate_agent_extension.py",
    )
    shutil.copy2(
        Path(__file__).resolve().with_name("probe_acp_runtime.py"),
        root / "scripts/probe_acp_runtime.py",
    )
    write(root, "extension/tutti.agent.json", dump(manifest(args)))
    write(
        root,
        "extension/profiles/discovery.json",
        dump(
            {
                "schemaVersion": "tutti.agent.discovery.v1",
                "candidates": [
                    {
                        "binaryNames": [args.binary],
                        "version": {
                            "args": ["--version"],
                            "constraint": args.version_constraint,
                        },
                        "launchArgs": args.launch_arg,
                        "probe": {"kind": "acp-initialize", "timeoutMs": 5000},
                    }
                ],
            }
        ),
    )
    write(
        root,
        "extension/profiles/tools.json",
        dump({"schemaVersion": "tutti.agent.tools.v1", "tools": []}),
    )
    write(
        root,
        "extension/profiles/capabilities.json",
        dump(
            {
                "schemaVersion": "tutti.agent.capabilities.v1",
                "declared": {
                    "imageInput": False,
                    "audioInput": False,
                    "embeddedContext": True,
                    "interrupt": True,
                    "resume": True,
                    "permissionModes": True,
                    "modelSelection": True,
                },
            }
        ),
    )
    write(
        root,
        "extension/profiles/composer.json",
        dump(
            {
                "schemaVersion": "tutti.agent.composer.v1",
                "model": {"source": "acp-session-models"},
                "permission": {"source": "acp-session-modes"},
                "permissionModes": [
                    {"runtimeId": "default", "semantic": "ask-before-write"},
                    {"runtimeId": "plan", "semantic": "read-only"},
                ],
            }
        ),
    )
    locale = {
        "agent.name": args.display_name,
        "agent.description": args.description,
        "runtime.install.title": f"Install {args.display_name}",
        "runtime.install.description": "Installs the pinned runtime in Tutti's managed directory.",
        "runtime.authRequired": f"Authenticate {args.display_name} before starting a session.",
    }
    write(root, "extension/locales/en.json", dump(locale))
    write(
        root,
        "extension/locales/zh-CN.json",
        dump(
            {
                "agent.name": args.display_name,
                "agent.description": f"通过标准 ACP 使用 {args.display_name}",
                "runtime.install.title": f"安装 {args.display_name}",
                "runtime.install.description": "将固定版本运行时安装到 Tutti 管理的目录。",
                "runtime.authRequired": f"请先完成 {args.display_name} 的身份认证。",
            }
        ),
    )
    write(
        root,
        "extension/assets/icon.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<path d="M18 32h28M32 18v28" stroke="#242424" stroke-width="6" stroke-linecap="round"/>'
        "</svg>\n",
    )
    hero_target = root / "extension" / hero_image_asset_path(args)
    hero_target.parent.mkdir(parents=True, exist_ok=True)
    hero_target.write_bytes(args.hero_image.read_bytes())
    if args.sidebar_icon is not None:
        sidebar_target = root / "extension" / sidebar_icon_asset_path(args)
        sidebar_target.write_bytes(args.sidebar_icon.read_bytes())
    write(
        root,
        "scripts/check.mjs",
        "import { execFileSync } from 'node:child_process';\n"
        "import { readFile, readdir, stat } from 'node:fs/promises';\n"
        "import path from 'node:path';\n"
        "const root = path.resolve(import.meta.dirname, '..');\n"
        "execFileSync(process.execPath, [path.join(root, 'scripts', 'package.mjs')], { stdio: 'inherit' });\n"
        "const packageDir = path.join(root, 'build', 'tutti-agent', 'package');\n"
        "const manifest = JSON.parse(await readFile(path.join(packageDir, 'tutti.agent.json'), 'utf8'));\n"
        f"if (manifest.schemaVersion !== 'tutti.agent.manifest.v1' || manifest.agentKey !== '{args.agent_key}') throw new Error('invalid manifest identity');\n"
        "await rejectExecutables(packageDir);\n"
        "async function rejectExecutables(directory) {\n"
        "  for (const entry of await readdir(directory, { withFileTypes: true })) {\n"
        "    const item = path.join(directory, entry.name);\n"
        "    if (entry.isSymbolicLink()) throw new Error(`symlink is forbidden: ${item}`);\n"
        "    if (entry.isDirectory()) { await rejectExecutables(item); continue; }\n"
        "    if ((await stat(item)).mode & 0o111) throw new Error(`executable is forbidden: ${item}`);\n"
        "  }\n"
        "}\n",
    )
    write(
        root,
        "scripts/package.mjs",
        "import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';\n"
        "const output = new URL('../build/tutti-agent/package/', import.meta.url);\n"
        "const version = String(process.env.TUTTI_AGENT_EXTENSION_VERSION || '"
        f"{args.extension_version}'"
        ").trim();\n"
        "if (!/^[0-9]+\\.[0-9]+\\.[0-9]+(?:-[0-9A-Za-z.-]+)?$/.test(version)) throw new Error(`invalid version: ${version}`);\n"
        "await rm(new URL('../build/', import.meta.url), { recursive: true, force: true });\n"
        "await mkdir(output, { recursive: true });\n"
        "await cp(new URL('../extension/', import.meta.url), output, { recursive: true });\n"
        "const manifestUrl = new URL('tutti.agent.json', output);\n"
        "const manifest = JSON.parse(await readFile(manifestUrl, 'utf8'));\n"
        "manifest.version = version;\n"
        "await writeFile(manifestUrl, `${JSON.stringify(manifest, null, 2)}\\n`);\n",
    )
    write(
        root,
        ".github/workflows/check.yml",
        "name: Check\non:\n  pull_request:\n  push:\n    branches: [main]\n"
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v6\n      - uses: pnpm/action-setup@v6\n"
        "      - uses: actions/setup-node@v6\n        with:\n          node-version: '24'\n"
        "          cache: pnpm\n      - run: pnpm install --frozen-lockfile\n"
        "      - run: pnpm check\n",
    )
    shutil.copytree(ASSETS / "release-tools", root / "scripts/release")
    release_workflow = (ASSETS / "workflows/release.yml").read_text(encoding="utf-8")
    for token, value in {
        "__AGENT_KEY__": args.agent_key,
        "__EXTENSION_VERSION__": args.extension_version,
        "__SIGNING_KEY_ID__": args.signing_key_id,
        "__RELEASE_ASSETS_BASE_URL__": args.release_assets_base_url,
    }.items():
        release_workflow = release_workflow.replace(token, value)
    write(root, ".github/workflows/release.yml", release_workflow)
    write(
        root,
        "extension/AGENTS.md",
        f"# {args.display_name} package\n\n"
        f"The runtime provider is `{args.provider}` and the signing key ID is "
        f"`{args.signing_key_id}`. Keep all package content declarative.\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--agent-key", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--extension-version", required=True)
    parser.add_argument("--runtime-package", required=True)
    parser.add_argument(
        "--runtime-runner",
        choices=("npm", "pnpm", "uv"),
        default="npm",
    )
    parser.add_argument("--runtime-executable")
    parser.add_argument("--binary", required=True)
    parser.add_argument("--version-constraint", required=True)
    parser.add_argument("--signing-key-id", required=True)
    parser.add_argument("--release-assets-base-url", required=True)
    parser.add_argument("--hero-image", required=True, type=Path)
    parser.add_argument("--sidebar-icon", type=Path)
    parser.add_argument(
        "--description", default="External Agent for Tutti through standard ACP"
    )
    parser.add_argument("--launch-arg", action="append")
    args = parser.parse_args()
    if not args.launch_arg:
        args.launch_arg = ["--acp"]
    validate_args(args)
    create(args)
    print(f"created Tutti Agent Extension repository at {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
