# Extension package contract

## Repository and package layout

```text
extension/
  tutti.agent.json
  AGENTS.md
  assets/icon.svg
  assets/sidebar-icon.svg
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
- an extension-local non-executable mask-safe `icon` for conversation rows;
- optional colored identity artwork referenced by `sidebarIcon` and promoted
  by the host to Agent selection, Message Center, mentions, and rail surfaces;
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
  "icon": { "type": "asset", "src": "assets/icon.svg" },
  "sidebarIcon": { "type": "asset", "src": "assets/sidebar-icon.svg" },
  "heroImage": { "type": "asset", "src": "assets/hero-image.jpg" },
  "runtime": {
    "kind": "standard-acp",
    "install": {
      "runner": "npm",
      "args": [
        "install",
        "--prefix",
        "${installRoot}",
        "@vendor/example-cli@1.2.3"
      ]
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
    "additionalLocales": [{ "locale": "zh-CN", "file": "locales/zh-CN.json" }]
  }
}
```

The install runner may be `npm`, `pnpm`, or `uv`. npm and pnpm packages use an
exact `package@version`; uv packages use an exact `package==version`. A
generated install must remain under `${installRoot}`, and the launch executable
must also resolve below that root. Examples:

```json
{
  "runner": "pnpm",
  "args": ["add", "--dir", "${installRoot}", "@vendor/example-cli@1.2.3"]
}
```

```json
{
  "runner": "uv",
  "args": ["pip", "install", "--target", "${installRoot}", "example-cli==1.2.3"]
}
```

## Discovery profile

Declare binary names, a version command/constraint, ACP launch args, and a
bounded ACP initialize probe. Do not declare scripts or filesystem crawlers.

```json
{
  "schemaVersion": "tutti.agent.discovery.v1",
  "candidates": [
    {
      "binaryNames": ["example"],
      "version": { "args": ["--version"], "constraint": ">=1.2.3 <2.0.0" },
      "launchArgs": ["--acp"],
      "probe": { "kind": "acp-initialize", "timeoutMs": 5000 }
    }
  ]
}
```

## Composer profile

Prefer runtime-owned catalogs:

```json
{
  "schemaVersion": "tutti.agent.composer.v1",
  "model": { "source": "acp-session-models" },
  "permission": { "source": "acp-session-modes" },
  "permissionModes": [
    { "runtimeId": "default", "semantic": "ask-before-write" },
    { "runtimeId": "auto_edit", "semantic": "accept-edits" },
    { "runtimeId": "yolo", "semantic": "full-access" },
    { "runtimeId": "plan", "semantic": "read-only" }
  ]
}
```

Runtime IDs are Agent-owned. Semantic tiers are Tutti-owned. Do not hardcode a
model list in the extension when ACP can report it.

When the runtime exposes provider-native ACP config option IDs, reference them
declaratively:

```json
{
  "configOptions": {
    "model": { "acpOptionId": "model-choice" },
    "permission": { "acpOptionId": "approval-mode" },
    "reasoning": { "acpOptionId": "thought-level" }
  }
}
```

When the runtime advertises commands that should reuse shared Tutti behavior:

```json
{
  "slashCommands": {
    "commandCatalogAuthoritative": true,
    "commands": [
      { "name": "compact", "effect": "submitImmediate" },
      { "name": "plan", "effect": "togglePlanMode" }
    ]
  }
}
```

When the Agent supports repository or user Skills, declare discovery instead
of adding a provider branch to Tutti:

```json
{
  "skills": {
    "invocation": "textTrigger",
    "triggerPrefix": "/",
    "roots": [
      { "scope": "workspace", "path": ".example/skills" },
      { "scope": "workspace", "path": ".agents/skills" },
      { "scope": "user", "path": ".example/skills" },
      { "scope": "user", "path": ".agents/skills" }
    ]
  }
}
```

Use safe relative paths only. Set the matching capabilities profile `skills`
flag to `true`; otherwise the signed package contradicts its composer profile.

## Presentation assets

The host contract permits absent `sidebarIcon` and `heroImage`, but a
publish-ready Agent should normally provide both. Keep every presentation asset
inside the signed package, at or below 256 KiB, with a supported image
extension. SVG assets must not contain scripts, event handlers,
`foreignObject`, animation, or remote references.

Package `icon` is the transparent mask-safe glyph used by monochrome
conversation rows. Optional package `sidebarIcon` is the colored primary
identity. When both exist, desktop projection promotes `sidebarIcon` to primary
`iconUrl`, preserves package `icon` as `maskIconUrl`, and may retain
`sidebarIconUrl` for rail chrome. Agent selection, conversation identity,
Message Center, and mentions use the colored primary identity; conversation
rows consume `maskIconUrl`. Every surface resolves the Target by
`agentTargetId`; do not add provider-specific catalogs.

Compose the poster so its identity survives the carousel's perspective and
downscaling: use a clear focal subject, strong contrast, and safe margins. Do
not bake mutable CDN URLs into the manifest.

## Tool and capability profiles

Tool profiles match runtime IDs through `match.ids`, map them to a
`canonicalId`, and may add category, presentation, diff, or command extraction
metadata. Capability profiles declare what the extension understands; runtime
negotiation still determines what is available for a session.

Composer profiles may declare `configOptions.model`, `permission`, and
`reasoning` references using each provider-native `acpOptionId`. Keep the older
model/mode source declarations only when they accurately map to the standard
ACP aliases. Permission semantics include `read-only`, `ask-before-write`,
`accept-edits`, `auto`, `locked-down`, and `full-access`.

Signed `slashCommands` may narrow a provider-advertised command catalog and
attach shared effects: `submitImmediate`, `showStatus`, `activateGoalMode`, or
`togglePlanMode`. Do not invent a provider-specific renderer command policy.

Do not make React infer tool categories, file changes, approvals, or diff
semantics from provider names.

## Package safety checks

- All referenced paths stay inside the package root.
- References exist and carry the expected schema versions.
- `icon`, optional `sidebarIcon`, and `heroImage` are supported local image
  assets no larger than 256 KiB; SVG content is passive and self-contained.
- No symlinks, executable non-directory files, hidden runtime scripts, or Agent
  executables.
- Runtime npm/pnpm packages are scoped and exactly pinned; uv packages are
  exactly pinned. Install argv uses the constrained runner form, never a shell,
  project root, or global install.
- Discovery has at least one bounded `acp-initialize` candidate with safe
  binary names and explicit launch/version arguments.
- Tool mappings use `match.ids` plus `canonicalId`; composer config option IDs,
  permission semantics, command effects, and Skill invocation are validated.
  Skill roots are safe relative workspace/user paths and agree with capability
  metadata.
- JSON files parse and locale files contain the required presentation keys.
- The packaged directory is produced from source, not published by zipping the
  repository root.
