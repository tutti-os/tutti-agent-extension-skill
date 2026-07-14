#!/usr/bin/env python3
"""Run deterministic, offline validation for this skill repository."""

from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/tutti-agent-extension/SKILL.md"
SKILL_ROOT = SKILL.parent
SCAFFOLD = SKILL_ROOT / "scripts/scaffold_agent_extension.py"
VALIDATOR = SKILL_ROOT / "scripts/validate_agent_extension.py"
RELEASE_ASSETS = SKILL_ROOT / "assets/release-tools"
RELEASE_WORKFLOW = SKILL_ROOT / "assets/workflows/release.yml"


def fail(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


def validate_skill() -> None:
    content = SKILL.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.DOTALL)
    if not match:
        fail("SKILL.md must start with YAML frontmatter")
    frontmatter = match.group(1)
    if "name: tutti-agent-extension" not in frontmatter:
        fail("frontmatter has the wrong skill name")
    if not re.search(r'^description: ".+"$', frontmatter, flags=re.MULTILINE):
        fail("frontmatter needs a quoted one-line description")
    if len(content.splitlines()) > 500:
        fail("SKILL.md exceeds 500 lines")
    for relative in re.findall(r"`(references/[^`]+\.md)`", content):
        if not (SKILL_ROOT / relative).is_file():
            fail(f"missing referenced file: {relative}")


def validate_evals() -> None:
    path = SKILL_ROOT / "evals/evals.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("skill_name") != "tutti-agent-extension":
        fail("eval skill_name mismatch")
    evals = data.get("evals")
    if not isinstance(evals, list) or len(evals) < 3:
        fail("at least three evaluation scenarios are required")
    for item in evals:
        if not all(item.get(key) for key in ("id", "prompt", "expected_output")):
            fail("each evaluation needs id, prompt, and expected_output")


def validate_release_assets() -> None:
    required = (
        RELEASE_ASSETS / "bin/build-tutti-agent-extension-release.mjs",
        RELEASE_ASSETS / "bin/build-tutti-agent-extension-versions.mjs",
        RELEASE_ASSETS / "lib/release.mjs",
        RELEASE_ASSETS / "lib/verify.mjs",
        RELEASE_ASSETS / "test/release.test.mjs",
        RELEASE_WORKFLOW,
    )
    for path in required:
        if not path.is_file():
            fail(f"missing release template asset: {path.relative_to(ROOT)}")
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    if "tutti-os/tutti/.github/workflows" in workflow:
        fail("release workflow must not depend on implementation from the Tutti repository")
    for token in (
        "__AGENT_KEY__",
        "__EXTENSION_VERSION__",
        "__SIGNING_KEY_ID__",
        "__RELEASE_ASSETS_BASE_URL__",
    ):
        if token not in workflow:
            fail(f"release workflow template is missing {token}")


def run_scripts() -> None:
    for script in (SCAFFOLD, VALIDATOR, Path(__file__)):
        py_compile.compile(str(script), doraise=True)
    subprocess.run([sys.executable, str(SCAFFOLD), "--help"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(VALIDATOR), "--help"], check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "example-extension"
        hero_image = Path(temporary) / "example-agent-poster.svg"
        hero_image.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 960">'
            '<rect width="720" height="960" fill="#181818"/>'
            '<circle cx="360" cy="480" r="180" fill="#7c5cff"/>'
            "</svg>\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                sys.executable,
                str(SCAFFOLD),
                "--output",
                str(output),
                "--agent-key",
                "example",
                "--display-name",
                "Example CLI",
                "--provider",
                "acp:example",
                "--extension-version",
                "1.0.0",
                "--runtime-package",
                "@example/cli@1.4.2",
                "--binary",
                "example",
                "--version-constraint",
                ">=1.4.2 <2.0.0",
                "--hero-image",
                str(hero_image),
                "--signing-key-id",
                "tutti-example-release-v1",
                "--release-assets-base-url",
                "https://cdn.example/tutti-agent-releases",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        package = output / "extension"
        subprocess.run([sys.executable, str(VALIDATOR), str(package)], check=True)
        manifest_path = package / "tutti.agent.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hero_reference = manifest.get("heroImage", {}).get("src")
        if hero_reference != "assets/hero-image.svg" or not (
            package / hero_reference
        ).is_file():
            fail("scaffold did not package and reference the required hero image")
        manifest_without_hero = dict(manifest)
        manifest_without_hero.pop("heroImage", None)
        manifest_path.write_text(json.dumps(manifest_without_hero), encoding="utf-8")
        missing_hero = subprocess.run(
            [sys.executable, str(VALIDATOR), str(package)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if missing_hero.returncode == 0:
            fail("validator accepted a package without the required hero image")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest["runtime"]["install"]["args"][-1] = "@example/cli@latest"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(package)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            fail("validator accepted an unpinned npm runtime package")
        workflow = (output / ".github/workflows/release.yml").read_text(encoding="utf-8")
        if "tutti-os/tutti/.github/workflows" in workflow or "__" in workflow:
            fail("scaffolded release workflow is not self-contained")
        if not (output / "scripts/release/lib/release.mjs").is_file():
            fail("scaffold did not include repository-owned release tools")
        package_json = json.loads((output / "package.json").read_text(encoding="utf-8"))
        if package_json.get("dependencies", {}).get("semver") != "7.8.0":
            fail("scaffold did not pin the release-tool dependency")


def main() -> int:
    validate_skill()
    validate_evals()
    validate_release_assets()
    run_scripts()
    print(json.dumps({"status": "ok", "repository": str(ROOT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
