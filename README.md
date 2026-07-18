# Tutti Agent Extension Skill

A reusable agent skill for designing, implementing, releasing, and debugging
declarative third-party Agent Extensions for
[Tutti](https://github.com/tutti-os/tutti).

The Skill captures the complete workflow validated by the Gemini CLI
integration while keeping the architecture provider-independent. It covers:

- reviewing the Agent Extension trust and ownership boundaries;
- scaffolding an independent extension repository with governance files and
  npm, pnpm, or uv runtime installation;
- declaring runtime discovery, capabilities, tools, composer models, and
  permission semantics;
- projecting mask-safe and colored Agent identity artwork without
  provider-specific renderer catalogs;
- installing project-neutral Target-managed runtimes with durable setup and
  authentication actions;
- integrating open provider identities and fixed Agent Targets in Tutti;
- normalizing standard ACP models, events, errors, and lifecycle snapshots;
- probing real ACP `initialize` and `session/new` negotiation;
- building reproducible signed releases with repository-owned tooling;
- bootstrapping repository-scoped GitHub OIDC, private S3, and CloudFront;
- publishing to S3/CloudFront and diagnosing catalog or runtime failures.

## Install

Install directly with the skills CLI:

```sh
npx --yes skills add tutti-os/tutti-agent-extension-skill
```

List the available Skill before installing:

```sh
npx --yes skills add tutti-os/tutti-agent-extension-skill --list
```

Install from a local checkout:

```sh
npx --yes skills add ./skills/tutti-agent-extension --skill tutti-agent-extension
```

## Validate

```sh
python3 scripts/validate_repository.py
```

## Scope

This repository describes Tutti Agent Extension packages, which connect an
existing out-of-process ACP runtime to Tutti. It does not implement or
redistribute the Agent runtime itself.

See [README.zh-CN.md](./README.zh-CN.md) for Chinese documentation.
