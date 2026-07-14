# Extension package contract

## Repository and package layout

```text
extension/
  tutti.agent.json
  AGENTS.md
  assets/icon.svg
  assets/hero-image.jpg
  locales/en.json
  locales/zh-CN.json
  profiles/discovery.json
  profiles/tools.json
  profiles/capabilities.json
  profiles/composer.json
```

Only `tutti.agent.json` is inherently meaningful. Optional resources influence
runtime only when referenced by the signed manifest.

## Manifest

Use `tutti.agent.manifest.v1` with:

- stable `agentKey`, semantic `version`, display name and description;
- an extension-local non-executable primary identity icon used across Agent
  selection, conversation rows, Message Center, and mentions;
- an extension-local non-executable home poster referenced by `heroImage`;
- `runtime.kind: standard-acp`;
- an exact runtime package version for the future explicit installation path;
- constrained `${installRoot}` executable resolution and fixed ACP args;
- explicit profile and locale references.

Example:

```json
{
  "schemaVersion": "tutti.agent.manifest.v1",
  "agentKey": "example",
  "version": "1.0.0",
  "name": "Example CLI",
  "description": "Example CLI through the Agent Client Protocol",
  "icon": {"type": "asset", "src": "assets/icon.svg"},
  "heroImage": {"type": "asset", "src": "assets/hero-image.jpg"},
  "runtime": {
    "kind": "standard-acp",
    "install": {
      "runner": "npm",
      "args": ["install", "--prefix", "${installRoot}", "@vendor/example-cli@1.2.3"]
    },
    "launch": {
      "executable": "${installRoot}/node_modules/.bin/example",
      "args": ["--acp"]
    }
  },
  "profiles": {
    "discovery": "profiles/discovery.json",
    "tools": "profiles/tools.json",
    "capabilities": "profiles/capabilities.json",
    "composer": "profiles/composer.json"
  },
  "localizationInfo": {
    "defaultLocale": "en",
    "defaultFile": "locales/en.json",
    "additionalLocales": [{"locale": "zh-CN", "file": "locales/zh-CN.json"}]
  }
}
```

## Discovery profile

Declare binary names, a version command/constraint, ACP launch args, and a
bounded ACP initialize probe. Do not declare scripts or filesystem crawlers.

```json
{
  "schemaVersion": "tutti.agent.discovery.v1",
  "candidates": [{
    "binaryNames": ["example"],
    "version": {"args": ["--version"], "constraint": ">=1.2.3 <2.0.0"},
    "launchArgs": ["--acp"],
    "probe": {"kind": "acp-initialize", "timeoutMs": 5000}
  }]
}
```

## Composer profile

Prefer runtime-owned catalogs:

```json
{
  "schemaVersion": "tutti.agent.composer.v1",
  "model": {"source": "acp-session-models"},
  "permission": {"source": "acp-session-modes"},
  "permissionModes": [
    {"runtimeId": "default", "semantic": "ask-before-write"},
    {"runtimeId": "auto_edit", "semantic": "accept-edits"},
    {"runtimeId": "yolo", "semantic": "full-access"},
    {"runtimeId": "plan", "semantic": "read-only"}
  ]
}
```

Runtime IDs are Agent-owned. Semantic tiers are Tutti-owned. Do not hardcode a
model list in the extension when ACP can report it.

When the Agent supports repository or user Skills, declare discovery instead
of adding a provider branch to Tutti:

```json
{
  "skills": {
    "invocation": "textTrigger",
    "triggerPrefix": "/",
    "roots": [
      {"scope": "workspace", "path": ".example/skills"},
      {"scope": "workspace", "path": ".agents/skills"},
      {"scope": "user", "path": ".example/skills"},
      {"scope": "user", "path": ".agents/skills"}
    ]
  }
}
```

Use safe relative paths only. Set the matching capabilities profile `skills`
flag to `true`; otherwise the signed package contradicts its composer profile.

## Presentation assets

The host contract permits an absent `heroImage`, but a publish-ready Agent
repository should provide one because Tutti's home carousel uses it as the
Agent poster. Keep icon and poster bytes inside the signed package, at or below
256 KiB each, with an image extension understood by the host. SVG assets must
not contain scripts, event handlers, `foreignObject`, or remote references.

The manifest has one canonical `icon` field. Do not add separate session,
message, mention, or provider-rail icon fields: the host projects the verified
asset through the Agent Target `iconUrl`, and each surface resolves it by
`agentTargetId`. Provider-catalog artwork is only for legacy built-in sessions.

Compose the poster so its identity survives the carousel's perspective and
downscaling: use a clear focal subject, strong contrast, and safe margins. Do
not bake mutable CDN URLs into the manifest.

## Tool and capability profiles

Tool profiles map Agent tool names to canonical semantics and may declare safe
aliases. Capability profiles declare what the extension understands; runtime
negotiation still determines what is available for a session.

Do not make React infer tool categories, file changes, approvals, or diff
semantics from provider names.

## Package safety checks

- All referenced paths stay inside the package root.
- References exist and carry the expected schema versions.
- Icon and `heroImage` are supported local image assets no larger than 256 KiB;
  SVG content is passive and self-contained.
- No symlinks, executable non-directory files, hidden runtime scripts, or Agent
  executables.
- Runtime npm package versions are exact, not tags or ranges.
- JSON files parse and locale files contain the required presentation keys.
- The packaged directory is produced from source, not published by zipping the
  repository root.
