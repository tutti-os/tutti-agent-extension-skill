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
PROBE = SKILL_ROOT / "scripts/probe_acp_runtime.py"
AWS_TEMPLATE = SKILL_ROOT / "assets/aws/agent-extension-release-infrastructure.yaml"
REPOSITORY_ASSETS = SKILL_ROOT / "assets/repository"


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
        AWS_TEMPLATE,
        REPOSITORY_ASSETS / "LICENSE",
        REPOSITORY_ASSETS / "CONTRIBUTING.md",
        REPOSITORY_ASSETS / "SECURITY.md",
        REPOSITORY_ASSETS / ".github/CODEOWNERS",
    )
    for path in required:
        if not path.is_file():
            fail(f"missing release template asset: {path.relative_to(ROOT)}")
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    if "tutti-os/tutti/.github/workflows" in workflow:
        fail(
            "release workflow must not depend on implementation from the Tutti repository"
        )
    for token in (
        "__AGENT_KEY__",
        "__EXTENSION_VERSION__",
        "__SIGNING_KEY_ID__",
        "__RELEASE_ASSETS_BASE_URL__",
    ):
        if token not in workflow:
            fail(f"release workflow template is missing {token}")
    for legacy in (
        "TUTTI_APP_RELEASES_AWS_REGION",
        "TUTTI_APP_RELEASES_AWS_ROLE_ARN",
        "TUTTI_APP_RELEASES_S3_BUCKET",
    ):
        if legacy in workflow:
            fail(f"release workflow still uses legacy variable {legacy}")
    for current in (
        "TUTTI_AGENT_RELEASES_AWS_REGION",
        "TUTTI_AGENT_RELEASES_AWS_ROLE_ARN",
        "TUTTI_AGENT_RELEASES_S3_BUCKET",
    ):
        if current not in workflow:
            fail(f"release workflow is missing {current}")
    if "validate_agent_extension.py" not in workflow:
        fail("release workflow does not validate the packaged extension")

    infrastructure = AWS_TEMPLATE.read_text(encoding="utf-8")
    for token in (
        "AWS::S3::Bucket",
        "AWS::CloudFront::Distribution",
        "AWS::IAM::Role",
        "token.actions.githubusercontent.com:sub",
        "repo:${GitHubOwner}/${GitHubRepository}:ref:refs/heads/main",
    ):
        if token not in infrastructure:
            fail(f"AWS bootstrap template is missing {token}")


def run_validator(package: Path, *, succeeds: bool, message: str) -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(package)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if (result.returncode == 0) != succeeds:
        fail(message)


def scaffold_repository(
    temporary: Path,
    hero_image: Path,
    *,
    runner: str,
    runtime_package: str,
) -> Path:
    output = temporary / f"{runner}-extension"
    subprocess.run(
        [
            sys.executable,
            str(SCAFFOLD),
            "--output",
            str(output),
            "--agent-key",
            runner,
            "--display-name",
            f"{runner.title()} CLI",
            "--provider",
            f"acp:{runner}",
            "--extension-version",
            "1.0.0",
            "--runtime-package",
            runtime_package,
            "--runtime-runner",
            runner,
            "--binary",
            runner,
            "--version-constraint",
            ">=1.4.2 <2.0.0",
            "--hero-image",
            str(hero_image),
            "--signing-key-id",
            f"tutti-{runner}-release-v1",
            "--release-assets-base-url",
            f"https://cdn.example/tutti-agent-releases/{runner}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return output


def validate_scaffolded_repository(output: Path) -> None:
    package = output / "extension"
    subprocess.run([sys.executable, str(VALIDATOR), str(package)], check=True)
    manifest = json.loads((package / "tutti.agent.json").read_text(encoding="utf-8"))
    hero_reference = manifest.get("heroImage", {}).get("src")
    if (
        hero_reference != "assets/hero-image.svg"
        or not (package / hero_reference).is_file()
    ):
        fail("scaffold did not package and reference the required hero image")
    for relative in (
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".github/CODEOWNERS",
        "scripts/validate_agent_extension.py",
        "scripts/probe_acp_runtime.py",
        "infra/aws/agent-extension-release-infrastructure.yaml",
        "scripts/release/lib/release.mjs",
    ):
        if not (output / relative).is_file():
            fail(f"scaffold did not include {relative}")
    workflow = (output / ".github/workflows/release.yml").read_text(encoding="utf-8")
    if "tutti-os/tutti/.github/workflows" in workflow or "__" in workflow:
        fail("scaffolded release workflow is not self-contained")
    package_json = json.loads((output / "package.json").read_text(encoding="utf-8"))
    if package_json.get("dependencies", {}).get("semver") != "7.8.0":
        fail("scaffold did not pin the release-tool dependency")


def validate_negative_cases(output: Path) -> None:
    package = output / "extension"
    manifest_path = package / "tutti.agent.json"
    original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_without_hero = dict(original_manifest)
    manifest_without_hero.pop("heroImage", None)
    manifest_path.write_text(json.dumps(manifest_without_hero), encoding="utf-8")
    run_validator(
        package,
        succeeds=False,
        message="validator accepted a package without heroImage",
    )
    manifest_path.write_text(json.dumps(original_manifest), encoding="utf-8")

    manifest = json.loads(json.dumps(original_manifest))
    manifest["runtime"]["install"]["args"][-1] = "@example/cli@latest"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    run_validator(
        package,
        succeeds=False,
        message="validator accepted an unpinned runtime package",
    )
    manifest_path.write_text(json.dumps(original_manifest), encoding="utf-8")

    discovery_path = package / "profiles/discovery.json"
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    discovery_path.write_text(
        json.dumps({**discovery, "candidates": []}), encoding="utf-8"
    )
    run_validator(
        package, succeeds=False, message="validator accepted empty discovery candidates"
    )
    discovery_path.write_text(json.dumps(discovery), encoding="utf-8")

    composer_path = package / "profiles/composer.json"
    composer = json.loads(composer_path.read_text(encoding="utf-8"))
    composer["skills"] = {
        "invocation": "textTrigger",
        "triggerPrefix": "/",
        "roots": [{"scope": "workspace", "path": ".agents/skills"}],
    }
    composer_path.write_text(json.dumps(composer), encoding="utf-8")
    run_validator(
        package,
        succeeds=False,
        message="validator accepted composer Skills without matching capability",
    )


def validate_probe(temporary: Path) -> None:
    fake_runtime = temporary / "fake_acp.py"
    fake_runtime.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    if request['method'] == 'initialize':\n"
        "        result = {'protocolVersion': 1, 'agentCapabilities': {}}\n"
        "    elif request['method'] == 'session/new':\n"
        "        result = {'sessionId': 'probe-session', 'models': {'availableModels': []}}\n"
        "    else:\n"
        "        continue\n"
        "    print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}), flush=True)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(PROBE),
            "--cwd",
            str(temporary),
            "--",
            sys.executable,
            str(fake_runtime),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if payload.get("sessionNew", {}).get("sessionId") != "probe-session":
        fail("ACP probe did not complete initialize and session/new")


def run_scripts() -> None:
    for script in (SCAFFOLD, VALIDATOR, PROBE, Path(__file__)):
        py_compile.compile(str(script), doraise=True)
    subprocess.run(
        [sys.executable, str(SCAFFOLD), "--help"], check=True, stdout=subprocess.DEVNULL
    )
    subprocess.run(
        [sys.executable, str(VALIDATOR), "--help"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [sys.executable, str(PROBE), "--help"], check=True, stdout=subprocess.DEVNULL
    )
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        hero_image = temporary_path / "example-agent-poster.svg"
        hero_image.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 960">'
            '<rect width="720" height="960" fill="#181818"/>'
            '<circle cx="360" cy="480" r="180" fill="#7c5cff"/>'
            "</svg>\n",
            encoding="utf-8",
        )
        repositories = {
            runner: scaffold_repository(
                temporary_path,
                hero_image,
                runner=runner,
                runtime_package=package,
            )
            for runner, package in {
                "npm": "@example/cli@1.4.2",
                "pnpm": "example-cli@1.4.2",
                "uv": "example-cli==1.4.2",
            }.items()
        }
        for output in repositories.values():
            validate_scaffolded_repository(output)
        validate_negative_cases(repositories["npm"])
        validate_probe(temporary_path)


def main() -> int:
    validate_skill()
    validate_evals()
    validate_release_assets()
    run_scripts()
    print(json.dumps({"status": "ok", "repository": str(ROOT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
