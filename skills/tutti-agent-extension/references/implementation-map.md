# Tutti implementation map

Paths may move. Use `rg` to locate symbols when a listed file no longer exists,
then update this reference if ownership changed.

## Read first

- `AGENTS.md`
- `docs/architecture/agent-extensions.md`
- `docs/architecture/agent-gui-node.md` for Agent GUI work
- `docs/conventions/agent-extension-release.md`
- `docs/conventions/README.md`
- the closest area `AGENTS.md`

For an active design proposal, also read the matching dated file under
`docs/specs/` and compare it with the durable architecture docs.

## Ownership map

| Concern | Primary location |
| --- | --- |
| Trusted extension source defaults | `config/tutti.defaults.json` |
| Daemon HTTP contracts | `services/tuttid/api/openapi/tuttid.v1.yaml` |
| Extension reconcile, verification, activation | `services/tuttid` |
| Agent Target registration and resolution | `services/tuttid` |
| Standard ACP adapter and activity normalization | `services/tuttid` |
| Desktop daemon client and generated contracts | `packages/clients/*`, `apps/desktop` |
| Agent GUI composer/timeline rendering | `packages/agent/gui` |
| Shared visual primitives and semantic tokens | `packages/ui` / `@tutti-os/ui-system` |
| Release workflow and release tooling | `.github/workflows`, release-tool packages |

Business rules stay in `services/tuttid`; the desktop must not become a second
extension registry or provider-specific runtime controller.

## Useful searches

```sh
rg -n 'agent_extension|agentTargetId|AgentTarget' services apps packages
rg -n 'standard-acp|session/new|availableModels|configOptions' services packages
rg -n 'activeTurnId|turn\.failed|lifecycle|Planning next moves' services packages apps
rg -n 'agentExtension|releaseIndexUrl|signingKeyId' config services docs
rg -n 'heroImage|heroImageUrl|availableCommands|composer.*skills' services packages apps
```

## Validation lanes

Choose checks proportional to changed scope:

```sh
pnpm check:changed
pnpm lint:ts
pnpm typecheck
pnpm --filter @tutti-os/desktop build
pnpm check:renderer-boundaries
pnpm check:i18n
pnpm generate:defaults
pnpm check:defaults-generated
pnpm lint:go
cd services/tuttid && go test ./... && go build ./...
```

Run UI boundary checks when touching UI System exports, CSS, SVG, or icons.
Run i18n checks for all user-visible copy. For daemon/API changes, update
OpenAPI first and run focused Go tests before broader validation.

## Documentation impact

After implementation, decide whether evidence should `discard`, `improve`,
`merge`, or `create` a durable lesson. Update architecture for ownership or data
flow, conventions for repository-wide rules, public docs for contracts, and
troubleshooting for recurring symptom playbooks. Do not record secrets, local
paths, customer data, or one-off identifiers.
