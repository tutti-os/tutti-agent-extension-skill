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
7. Cache the signed icon as a safe data URL; the renderer does not add a new
   icon branch.

Disabled sources make no network request and remove their system Target.
Failed refreshes retain a previously verified active installation.

## Runtime resolution

The controller passes provider, Target ID, CWD, and Target ref to the dynamic
runtime resolver. The resolver:

- verifies the fixed extension installation;
- reads only signed declarative profiles;
- finds a compatible executable with shared discovery infrastructure;
- creates the generic standard ACP adapter;
- records the runtime source, version, path/fingerprint, and profile identity.

Sessions persist `agentTargetId`; resume re-derives the same fixed extension.

## Composer projection

Composer options are Target-scoped. After authoritative Target resolution,
open provider normalization must remain open. Direct provider-only requests
remain on the closed built-in path.

For standard ACP:

- `session/new.models.availableModels` becomes the shared model config option;
- `models.currentModelId` becomes current/default selection;
- legacy session `configOptions` continues to work;
- `session/set_model` applies model changes when the models API is present;
- ACP modes map through signed semantic permission mappings;
- hidden discovery sessions use a daemon-managed CWD.

The selected extension model must survive service validation, runtime
preparation, and start. Built-in model catalogs must not erase or validate an
authoritative extension model.

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
