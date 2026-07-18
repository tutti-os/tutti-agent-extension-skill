# Troubleshooting Agent Extensions

## Evidence discipline

Start from the visible symptom, then prove the first broken boundary in this
chain:

```text
trusted source -> release reconcile -> verified installation -> Agent Target
-> setup/install/auth -> runtime discovery -> ACP session/new -> composer/session state
-> ACP session/prompt -> normalized activity -> persisted lifecycle -> GUI
```

Use one stable prefix for all logs added for the investigation. JSON-serialize
every payload. Include IDs and phase transitions, but redact credentials,
authorization headers, complete environment maps, and user content unrelated
to the fault.

Suggested evidence fields:

```json
{
  "provider": "acp:example",
  "agentTargetId": "extension:example",
  "extensionVersion": "1.0.0",
  "cwd": "/managed/discovery/cwd",
  "runtimeSource": "path",
  "runtimeVersion": "1.2.3",
  "acpMethod": "session/new",
  "sessionId": "...",
  "turnId": "...",
  "eventType": "turn.failed",
  "lifecyclePhase": "settled"
}
```

## Symptom matrix

### Still shows Coming soon

Prove, in order:

1. the source is enabled in the effective runtime configuration;
2. reconcile installed and activated a verified compatible package;
3. a system `agent_extension` Target was registered;
4. the desktop Target query includes that Target;
5. renderer availability is driven by the Target, not a static provider list.

Do not remove the Coming soon UI until the Target is actually runnable.

### Models stay Loading or disappear

Inspect the target-scoped composer request, resolved Target ref, runtime path,
discovery CWD, and complete `session/new` response. Standard ACP may report
models through the `models` field rather than legacy `configOptions`. Normalize
both into the shared composer descriptor and settle the request on success or
error.

A no-project probe still needs a real daemon-managed working directory. An
empty or deleted CWD can make the runtime exit before reporting models.

### Environment detection says unsupported

Determine who owns installation and readiness. The desktop managed-environment
wizard is for built-in providers managed by that feature. An Agent Extension is
owned by its Target lifecycle and discovery profile. Gate the wizard by Target
kind, not by provider-name exceptions.

If the UI shows extension setup but actions disappear after refresh, inspect the
daemon setup store and DTO projection before changing React state. Runtime
install/auth/setup actions should be durable daemon facts keyed by workspace,
Target, and fixed extension installation. Runtime files use a project-neutral
runtime identity and may be reused across workspaces; setup must never depend
on or mutate the selected project.

### Colored square or blank conversation-row icon

Inspect the signed package and presentation projection separately. Package
`icon` must be a transparent mask-safe glyph. Optional `sidebarIcon` is the
colored primary identity. When both exist, desktop projection exposes the
colored asset as primary `iconUrl` and the package glyph as `maskIconUrl`.

Trace `maskIconUrl` through Target mapping, desktop contracts, window intent,
Agent GUI normalization, presentation context, and memo/cache keys. A unit test
that injects `maskIconUrl` directly into context does not prove production
plumbing. Missing projection may silently feed colored artwork into a CSS mask.

### Typing `/` shows no commands or Skills

Inspect the installed package before changing the palette. The signed
`profiles/composer.json` must declare validated Skill roots and the capability
profile must advertise `skills: true`. Then inspect the newest persisted
session runtime context: `availableCommands` proves the ACP runtime advertised
commands even if the renderer missed the startup event.

If commands exist in persisted context but the palette is empty, confirm the
GUI does not require a built-in slash policy before accepting provider command
catalogs. Open extension providers normally have no built-in descriptor. Keep
their advertised commands provider-native and use composer options to rehydrate
the catalog after restarts.

### Sending creates a session but no response or loading state

Trace activity context creation before runtime execution. If provider
normalization uses a closed built-in allowlist, an open extension provider may
fail before `turn.started` is emitted. Accept the open provider only after the
signed fixed Target is authorized, and preserve event-context validation for
unsafe aliases.

### Error is visible but Planning next moves never stops

An error activity and a settled turn are different facts. Inspect the terminal
adapter event and persisted session patch. `turn.failed` must carry the
authoritative sequenced lifecycle snapshot, clear `activeTurnId`, set phase to
settled, record a failed outcome, and unblock submission atomically.

Do not hide the row with a renderer timeout. Fix the lifecycle source and its
persistence path.

### Upload succeeded but CDN returns 403 or stale indexes

Compare S3 object existence with the exact public CloudFront path. Inspect
origin path, origin access policy, behavior routing, cache key, and invalidation
of mutable JSON. Verify public bytes and signature. Do not treat AWS CLI upload
success as release completion.

### Quota or authentication error

Keep provider error text visible through canonical error activity and settle
the turn. Classify quota/rate-limit/auth failures without converting them into
transport success. Authentication setup remains runtime-owned unless the
extension contract explicitly adds a supported, reviewed host flow.

## Fix acceptance

A root-cause fix must include focused regression coverage at the broken
boundary and an end-to-end state assertion. Remove temporary alternate paths
or obsolete provider-specific logic introduced by earlier attempts. Capture a
reusable failure mode in Tutti's troubleshooting docs when the issue can recur.
