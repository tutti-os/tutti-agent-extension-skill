---
name: tutti-agent-extension
description: "Design, implement, release, review, or debug a declarative third-party Agent Extension for Tutti. Use whenever a task mentions adding an external ACP Agent to Tutti, creating a tutti.agent.json package, open provider IDs, agent_extension Targets, runtime discovery, ACP models or permission modes, Agent Extension signing/catalog publication, S3/CloudFront rollout, or an extension that is visible but stuck on Coming soon, Loading, silent errors, or stale processing state. Do not use for agent-enabled workspace apps; use the Tutti Agent Workspace App skill for those."
---

# Tutti Agent Extension

Use this Skill to connect an independently released Agent runtime to Tutti
through a declarative package and the standard Agent Client Protocol (ACP).
Keep the solution provider-independent: an extension can describe a provider,
but Tutti must not gain a provider-name branch for it.

## Choose the task path

- For a new external Agent repository, follow **Extension repository**.
- For Tutti main-repository support, follow **Host integration**.
- For publishing or CDN visibility, follow **Release and rollout**.
- For a broken integration, start at **Debug from observed state**.
- For a design review, apply **Architecture gates** before editing code.

Read only the references needed for the selected path:

- `references/architecture-and-trust.md`: ownership, security, identity, and
  invariants. Read for design reviews and host changes.
- `references/package-contract.md`: manifest and profile shapes. Read for an
  extension repository or schema work.
- `references/host-integration.md`: Tutti daemon, Target, composer, activity,
  persistence, and GUI integration. Read before Tutti code changes.
- `references/release-and-rollout.md`: build, signing, reusable workflow,
  S3/CloudFront, source configuration, and activation.
- `references/troubleshooting.md`: symptom-to-layer diagnosis and required
  evidence. Read for debugging.
- `references/implementation-map.md`: current Tutti paths and validation
  commands. Read when working in the Tutti monorepo.

## Architecture gates

Confirm these before implementation:

1. The Agent executes out of process and speaks standard ACP. Extension files
   are declarative metadata, assets, and locales only.
2. `agentTargetId` is the product identity. `provider` is open execution
   metadata and never authorizes a launch by itself.
3. The daemon resolves a signed, fixed `agent_extension` Target before it
   accepts an open provider ID.
4. Runtime discovery prefers a compatible user-local binary. Project runtime
   installation requires an explicit user-confirmed host API.
5. Raw ACP output becomes canonical Agent Activity before persistence. React
   code does not infer tools, diffs, errors, or lifecycle by provider name.
6. Model and permission catalogs come from ACP session state or declarative
   semantic mappings, not a hardcoded Agent catalog in Tutti.
7. Published ZIPs are immutable and signed; mutable indexes use conditional
   updates. Private signing keys never enter source control or logs.

If any gate fails, stop and redesign the boundary instead of adding a fallback
or provider-specific patch.

## Extension repository

1. Inspect the Agent's official executable, version command, ACP launch
   command, session/new response, model state, permission modes, and auth/error
   behavior. Do not infer protocol fields from marketing documentation.
2. Scaffold a repository when useful:

   ```sh
   python3 scripts/scaffold_agent_extension.py \
     --output /path/to/repo \
     --agent-key example \
     --display-name "Example CLI" \
     --provider acp:example \
     --extension-version 1.0.0 \
     --runtime-package @vendor/example-cli@1.2.3 \
     --binary example \
     --version-constraint '>=1.2.3 <2.0.0' \
     --signing-key-id tutti-example-release-v1 \
     --release-assets-base-url https://cdn.example/tutti-agent-releases
   ```

3. Edit `extension/tutti.agent.json` and referenced profiles. Keep install
   packages exactly pinned and use only the constrained `${installRoot}`
   placeholder.
4. Add localized display copy in the extension package. Tutti renderer copy
   still uses Tutti's i18n layer.
5. Package into a clean directory and validate it:

   ```sh
   python3 scripts/validate_agent_extension.py build/tutti-agent/package
   ```

6. Verify the actual Agent locally with `--version` and an ACP initialize plus
   session/new probe. Avoid sending a paid prompt when protocol negotiation is
   enough.

Use the existing `tutti-os/agent-extension-gemini` repository as a concrete
example, not as a source of Gemini-specific host behavior.

## Host integration

1. Read the closest `AGENTS.md`, architecture docs, API conventions, and
   generated-contract rules before editing Tutti.
2. Change OpenAPI first for daemon HTTP contracts. Preserve open provider IDs
   across generated clients, desktop contracts, workbench state, and Agent GUI.
3. Add the trusted source to runtime defaults with key, release index URL,
   signing key ID, and a disabled-by-default gate. Document its env override.
4. Reconcile the release index in the daemon: select compatibility, verify
   signature/digest/size, extract safely to staging, validate the package, and
   atomically activate it. Preserve the last verified installation offline.
5. Register a system Agent Target whose launch reference fixes the extension
   installation version. Use the cached signed icon and localized metadata.
6. Resolve the executable through the declarative discovery profile and the
   shared command resolver. Start the generic standard ACP adapter; never add
   a provider-specific adapter for a standard ACP Agent.
7. Project ACP session state:
   - normalize standard `models` and legacy `configOptions` into the shared
     composer model descriptor;
   - map ACP runtime permission mode IDs to Tutti semantic permission tiers;
   - use a daemon-managed discovery CWD for no-project composer probes;
   - preserve target-authorized model selections through launch validation.
8. Normalize ACP content, tool calls, diffs, notices, visible errors, and
   interactions into canonical activity events.
9. Stamp standard ACP turn transitions with sequenced adapter-origin lifecycle
   snapshots. A terminal failure must atomically settle the turn, clear
   `activeTurnId`, persist the error, and unblock submission.
10. Keep environment management ownership clear: extension readiness belongs
    to the Agent Target lifecycle. Do not show the built-in managed-environment
    wizard for extension Targets.
11. Add focused tests at each boundary, then run the validation lanes listed in
    `references/implementation-map.md`.

## Release and rollout

1. Build the package locally and reject scripts, executables, symlinks, unsafe
   paths, undeclared files that affect runtime, and unpinned install packages.
2. Use `@tutti-os/agent-extension-release-tools` and the reusable workflow at
   `tutti-os/tutti/.github/workflows/publish-tutti-agent-extension.yml`.
3. Configure GitHub OIDC/AWS variables and the repository secret
   `TUTTI_AGENT_EXTENSION_SIGNING_PRIVATE_KEY`. Never copy the private key into
   Tutti defaults.
4. Publish immutable version objects before mutable indexes. Protect
   `latest.json`, `versions.json`, and `catalog.json` with ETag preconditions.
5. Verify the public CDN bytes: index, release metadata, ZIP digest, size, and
   Ed25519 signature.
6. Enable the Tutti source only after the CDN path and compatible runtime are
   both verified. Use a staged rollout when the source changes default UI.

## Debug from observed state

Trace one Target/session end to end instead of changing UI symptoms:

```text
source reconcile -> installed package -> Agent Target -> composer options
-> runtime start -> ACP session/new -> ACP session/prompt -> canonical events
-> persisted session/timeline -> desktop state -> Agent GUI
```

Use the same log prefix for one investigation and JSON-serialize diagnostic
payloads. Log open provider, Target ID, extension installation, CWD, runtime
path/version, ACP method, session/turn IDs, emitted event types, and lifecycle
phase without logging credentials or full environment values.

Before fixing, prove the first broken boundary. Common examples:

- **Coming soon**: Target availability or renderer catalog gating is stale.
- **Models Loading/empty**: target-scoped composer request, discovery CWD, or
  ACP `models` normalization is broken.
- **Environment unsupported**: the built-in environment wizard is being shown
  for a Target-owned extension lifecycle.
- **Silent send**: open provider identity was rejected while creating activity
  event context.
- **Error plus endless processing**: the terminal event did not carry or
  persist a settled authoritative lifecycle snapshot.
- **Uploaded but CDN 403**: CloudFront routing or S3 origin policy is wrong;
  upload success is insufficient.

Read `references/troubleshooting.md` before implementing a diagnosis.

## Completion report

Report:

- the first broken boundary and root cause;
- extension and Tutti files changed;
- package/runtime/release checks run;
- real endpoint or public CDN evidence obtained without browser automation;
- remaining rollout, quota, auth, or compatibility limits;
- durable documentation updated, or why no documentation impact exists.
