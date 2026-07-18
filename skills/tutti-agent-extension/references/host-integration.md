# Tutti host integration

## Configuration and contracts

Add only trusted source data to Tutti defaults:

```json
{
  "key": "example",
  "releaseIndexUrl": "https://cdn.example/agents/example/versions.json",
  "signingKeyId": "tutti-example-release-v1",
  "enabled": false
}
```

Document the matching runtime/env override. Change the daemon OpenAPI document
before request/response implementations, regenerate clients, and preserve open
provider strings throughout desktop contracts and GUI state.

## Reconciliation and Target registration

At daemon startup or refresh:

1. Fetch `versions.json` when the source is enabled.
2. Select a compatible active version.
3. Download and verify immutable release metadata and ZIP.
4. Extract safely to staging and validate the installed package.
5. Atomically switch `active.json`.
6. Register a system Target such as `extension:example` with an
   `agent_extension` launch ref fixed to the verified installation.
7. Cache signed `icon`, optional `maskIcon`, and optional `heroImage` as safe
   data URLs. Project `icon` directly as primary `iconUrl` and `maskIcon` as
   `maskIconUrl` for conversation rows. Carry both through desktop contracts, window
   intents, GUI normalization, presentation contexts, and memo keys. Every
   surface resolves by `agentTargetId`; provider catalogs remain legacy-only.

Disabled sources make no network request and remove their system Target.
Failed refreshes retain a previously verified active installation.

In development only, a generic
`TUTTI_AGENT_EXTENSION_<KEY>_PACKAGE_DIR` override may select an unpacked
package. Apply normal package validation, copy it into immutable daemon state,
and assign a content-addressed synthetic version. Never execute from the
mutable source directory, and ignore the override in production.

## Runtime resolution

The controller passes provider, Target ID, CWD, and Target ref to the dynamic
runtime resolver. The resolver:

- verifies the fixed extension installation;
- reads only signed declarative profiles;
- finds a compatible executable with shared discovery infrastructure;
- creates the generic standard ACP adapter;
- records the runtime source, version, path/fingerprint, and profile identity.

Sessions persist `agentTargetId`; resume re-derives the same fixed extension.

## Setup lifecycle

Extension setup is Target-owned daemon state. Expose Target-scoped setup read,
install, and authenticate APIs. Install submission contains only the
daemon-issued plan digest plus an idempotent client action ID; renderer input
cannot replace runner, argv, package, executable, root, or platform.

Model setup state explicitly:

- a runtime identity derived from Agent key, platform, exact package,
  install/launch argv, executable, and discovery profile;
- a stable user-local runtime root shared across workspaces, while setup action
  records stay scoped to workspace, Target, and fixed extension installation;
- idempotent action requests with visible success/failure state;
- local-first discovery, safe staging, version plus ACP probes, atomic
  activation, executable fingerprinting, and explicit reinstall on integrity
  failure;
- runtime-advertised authentication methods and durable non-secret outcomes;
- DTO projection from daemon state to desktop settings and Agent GUI setup
  gates;
- no provider-name shortcuts and no renderer-only readiness flags.

Use the built-in managed-environment service only for built-in providers it
owns. For extension Targets, show setup controls from the Target lifecycle and
the signed package contract. Setup never requires or modifies a project.

## Composer projection

Composer options are Target-scoped. After authoritative Target resolution,
open provider normalization must remain open. Direct provider-only requests
remain on the closed built-in path.

For standard ACP:

- `session/new.models.availableModels` becomes the shared model config option;
- `models.currentModelId` becomes current/default selection;
- legacy session `configOptions` continues to work;
- signed `configOptions.model|permission|reasoning.acpOptionId` references map
  provider-native option IDs to shared typed controls;
- `session/set_model` applies model changes when the models API is present;
- ACP modes map through signed semantic permission mappings;
- hidden discovery sessions use a daemon-managed CWD.
- provider-advertised commands are persisted in detailed runtime context and
  restored through composer options when a transient engine event was missed;
- signed `slashCommands` may narrow the runtime catalog and attach shared
  effects such as submit, status, goal, or plan-mode actions;
- signed extension Skill roots drive discovery for open providers.

The selected extension model must survive service validation, runtime
preparation, and start. Built-in model catalogs must not erase or validate an
authoritative extension model.

An open extension normally has no built-in slash-command policy. Treat the ACP
command catalog as a runtime capability: keep it visible and provider-native
instead of discarding it when policy metadata is absent.

## Activity and lifecycle

Normalize every ACP payload at the daemon boundary:

- assistant/thinking chunks and final text;
- tool calls and updates;
- file diffs and locations;
- permission and interactive requests;
- visible notices and errors;
- config/model/mode updates.

Open provider IDs must be valid event metadata. Preserve registered aliases
that are intentionally excluded from event projection; accepting extensions
must not reopen unsafe legacy aliases.

Standard ACP turn events carry sequenced adapter-origin lifecycle snapshots:

```text
turn.started -> activeTurnId=<id>, phase=running
turn.failed  -> activeTurnId=null, phase=settled, outcome=failed
```

This makes runtime memory, reporter patches, persisted session state, event
stream, and GUI agree. An error card without a settled snapshot leaves the
composer blocked and the processing row visible.

## GUI ownership

Agent GUI consumes Targets, composer contracts, and canonical activity. It may
render signed Target presentation but does not add provider-specific product
logic. The built-in managed-environment wizard is visible only for built-in
desktop-managed providers; extension readiness belongs to Target lifecycle.
Target selection does not auto-open setup. Initial checking is non-modal,
non-ready state exposes an inline affordance, and only explicit user action
opens the controlled dialog. Keep the dialog mounted through close and ready
transitions so overlay locks clean up.
