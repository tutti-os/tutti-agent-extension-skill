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


def run_scripts() -> None:
    for script in (SCAFFOLD, VALIDATOR, Path(__file__)):
        py_compile.compile(str(script), doraise=True)
    subprocess.run([sys.executable, str(SCAFFOLD), "--help"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(VALIDATOR), "--help"], check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "example-extension"
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
        manifest["runtime"]["install"]["args"][-1] = "@example/cli@latest"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(package)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            fail("validator accepted an unpinned npm runtime package")


def main() -> int:
    validate_skill()
    validate_evals()
    run_scripts()
    print(json.dumps({"status": "ok", "repository": str(ROOT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
