# Architecture and trust boundaries

## Ownership model

An Agent Extension is a signed declarative adapter package between Tutti and an
independent ACP runtime.

```text
Agent repository
  -> declarative extension package
  -> signed immutable release
  -> trusted source configuration in Tutti
  -> daemon installation and fixed Agent Target
  -> generic standard ACP adapter
  -> canonical Agent Activity
  -> Agent GUI
```

The Agent repository owns runtime behavior and ACP compatibility. The extension
repository owns discovery and semantic declarations. Tutti owns installation,
trust, process execution, canonical activity, durable state, and UI.

## Identity

- `agentKey`: stable release namespace, such as `gemini`.
- `agentTargetId`: stable product/UI identity, normally
  `extension:<agentKey>`.
- `provider`: open runtime metadata, normally `acp:<agentKey>`.
- extension installation ID: fixed package version, normally
  `agent-extension:<agentKey>@<version>`.
- runtime binding: the discovered or explicitly installed executable plus its
  fingerprint.

Never use an open provider string as launch authority. A request may preserve
the provider only after the daemon resolves the fixed Agent Target and verifies
that its signed extension declares the same identity.

## Code and data boundary

Allowed extension content:

- JSON manifests and profiles;
- localized JSON resources;
- non-executable image assets;
- package-local documentation.

Forbidden extension content:

- JavaScript or native plugins loaded into Tutti;
- renderer components or arbitrary HTML;
- executable scripts, Agent binaries, symlinks, WASM normalizers;
- arbitrary discovery or installation shell commands.

The runtime remains a separate subprocess. Third-party packages may select only
the public standard ACP strategy, never trusted Codex app-server, Claude SDK,
or other built-in strategies.

## Installation invariants

- Select a release compatible with the current Tutti version and host
  capabilities.
- Verify key ID, Ed25519 signature, SHA-256, size, manifest identity, and every
  referenced path before activation.
- Extract into a new staging directory with path traversal, symlink, and file
  mode checks.
- Activate atomically. Do not overwrite files used by a live session.
- Preserve a previously verified active installation when the remote index is
  temporarily unavailable.
- Treat missing extension versions on resume as a read-only session condition;
  never silently resume using another provider or package version.
- Persist installation and setup action state in daemon-owned durable storage.
  Renderer state may observe or request actions, but it must not become the
  authoritative source for installed packages, pending setup, auth status, or
  lifecycle phase.

## Runtime invariants

- Prefer a compatible local executable discovered through the shared command
  resolver.
- Do not silently install into the user's project. Project-scoped installation
  requires a host API, explicit confirmation, and a daemon-recorded setup
  action result.
- Bind adapter caches to workspace, project root, Target, extension/profile
  version, runtime source, and runtime fingerprint. Provider alone is not a
  safe cache key.
- Use a real, daemon-owned CWD for hidden/no-project ACP probes.

## Canonical activity invariant

Persist canonical events, not provider-specific raw payloads. Historical
rendering must not depend on the currently installed extension version.
Resume-time event normalization may use the session-pinned extension profile,
but old activity is never reinterpreted through a newer profile.
