#!/usr/bin/env python3
"""Create a minimal, provider-independent Tutti Agent Extension repository."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

KEY = re.compile(r"^[a-z][a-z0-9-]*$")
BINARY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
EXACT_NPM = re.compile(
    r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*@"
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"
)


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def validate_args(args: argparse.Namespace) -> None:
    if not KEY.fullmatch(args.agent_key):
        raise SystemExit("--agent-key must match ^[a-z][a-z0-9-]*$")
    if not args.provider.startswith("acp:"):
        raise SystemExit("--provider must use the open acp:<key> form")
    if not KEY.fullmatch(args.provider.removeprefix("acp:")):
        raise SystemExit("--provider must use the open acp:<key> form")
    if not SEMVER.fullmatch(args.extension_version):
        raise SystemExit("--extension-version must be an exact semantic version")
    if not EXACT_NPM.fullmatch(args.runtime_package):
        raise SystemExit("--runtime-package must be an exact npm package@version")
    if not BINARY.fullmatch(args.binary):
        raise SystemExit("--binary must be a binary name without a path")
    if not BINARY.fullmatch(args.signing_key_id):
        raise SystemExit("--signing-key-id contains unsupported characters")
    if not re.fullmatch(r"https://[^\s]+", args.release_assets_base_url):
        raise SystemExit("--release-assets-base-url must be an HTTPS URL without whitespace")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"output directory is not empty: {args.output}")


def manifest(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schemaVersion": "tutti.agent.manifest.v1",
        "agentKey": args.agent_key,
        "version": args.extension_version,
        "name": args.display_name,
        "description": args.description,
        "icon": {"type": "asset", "src": "assets/icon.svg"},
        "runtime": {
            "kind": "standard-acp",
            "install": {
                "runner": "npm",
                "args": ["install", "--prefix", "${installRoot}", args.runtime_package],
            },
            "launch": {
                "executable": f"${{installRoot}}/node_modules/.bin/{args.binary}",
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


def create(args: argparse.Namespace) -> None:
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
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
        "pnpm package:tutti-agent\n```\n",
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
                    "check": "node scripts/check.mjs",
                    "package:tutti-agent": "node scripts/package.mjs",
                },
                "packageManager": "pnpm@10.11.0",
            }
        ),
    )
    write(
        root,
        "pnpm-lock.yaml",
        "lockfileVersion: '9.0'\n\nsettings:\n  autoInstallPeers: true\n"
        "  excludeLinksFromLockfile: false\n\nimporters:\n\n  .: {}\n",
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
                        "version": {"args": ["--version"], "constraint": args.version_constraint},
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
        "runtime.install.title": f"Install {args.display_name} in this project",
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
                "runtime.install.title": f"在当前项目安装 {args.display_name}",
                "runtime.install.description": "将固定版本运行时安装到 Tutti 管理的目录。",
                "runtime.authRequired": f"请先完成 {args.display_name} 的身份认证。",
            }
        ),
    )
    write(
        root,
        "extension/assets/icon.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#242424"/>'
        '<path d="M18 32h28M32 18v28" stroke="#fff" stroke-width="6" stroke-linecap="round"/>'
        "</svg>\n",
    )
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
    write(
        root,
        ".github/workflows/release.yml",
        "name: Publish Agent Extension\non:\n  workflow_dispatch:\n    inputs:\n"
        "      version:\n        description: Immutable extension version\n        required: true\n"
        f"        default: '{args.extension_version}'\npermissions:\n  contents: read\n"
        "  id-token: write\njobs:\n  publish:\n"
        "    uses: tutti-os/tutti/.github/workflows/publish-tutti-agent-extension.yml@main\n"
        "    with:\n"
        f"      agent_key: {args.agent_key}\n"
        "      version: ${{ inputs.version }}\n"
        "      min_tutti_version: '0.0.0'\n"
        "      package_command: pnpm package:tutti-agent\n"
        "      package_dir: build/tutti-agent/package\n"
        f"      signing_key_id: {args.signing_key_id}\n"
        "      aws_region: ${{ vars.TUTTI_APP_RELEASES_AWS_REGION }}\n"
        "      aws_role_arn: ${{ vars.TUTTI_APP_RELEASES_AWS_ROLE_ARN }}\n"
        "      s3_bucket: ${{ vars.TUTTI_APP_RELEASES_S3_BUCKET }}\n"
        "      s3_prefix: tutti-agent-releases\n"
        f"      release_assets_base_url: {args.release_assets_base_url}\n"
        "      cloudfront_distribution_id: ${{ vars.TUTTI_AGENT_RELEASES_CLOUDFRONT_DISTRIBUTION_ID }}\n"
        "    secrets:\n"
        "      signing_private_key: ${{ secrets.TUTTI_AGENT_EXTENSION_SIGNING_PRIVATE_KEY }}\n",
    )
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
    parser.add_argument("--binary", required=True)
    parser.add_argument("--version-constraint", required=True)
    parser.add_argument("--signing-key-id", required=True)
    parser.add_argument("--release-assets-base-url", required=True)
    parser.add_argument("--description", default="External Agent for Tutti through standard ACP")
    parser.add_argument("--launch-arg", action="append", default=["--acp"])
    args = parser.parse_args()
    validate_args(args)
    create(args)
    print(f"created Tutti Agent Extension repository at {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
