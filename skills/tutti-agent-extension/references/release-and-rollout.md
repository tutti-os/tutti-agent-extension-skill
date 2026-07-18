# Release and rollout

## Ownership boundary

Each concrete Agent Extension repository owns its complete release
implementation:

```text
agent-extension-example/
  extension/
  scripts/package.mjs
  scripts/release/bin/
  scripts/release/lib/
  scripts/release/schemas/
  scripts/release/test/
  .github/workflows/release.yml
```

Do not call or check out release scripts from the Tutti repository. Tutti owns
host-side schemas, trusted source configuration, installation, and verification
of published bytes. It does not build or upload third-party Agent releases.

Use `scripts/scaffold_agent_extension.py` to create the self-contained layout.
For an existing Agent repository, copy this Skill's
`assets/release-tools/` directory to `scripts/release/` and adapt the bundled
workflow template. Keep release code versioned with the manifest it publishes.

## Repository release contract

The repository workflow must:

1. Check out only the concrete Agent repository.
2. Install its pinned dependencies with a frozen lockfile.
3. Build a clean declarative package directory.
4. Run the repository-owned release builder.
5. Upload immutable version objects with `If-None-Match: *`.
6. Update mutable indexes using the previously observed ETag.
7. Invalidate only mutable CDN paths.

Never publish a repository-root ZIP. The artifact may contain only the
manifest, profiles, locales, documentation, and image assets accepted by the
package validator. Runtime binaries, executable files, scripts, symlinks, and
dynamically loaded renderer code are forbidden.

Inspect the packaged manifest and archive before signing: `icon.src`, optional
`sidebarIcon.src`, and `heroImage.src` must resolve to intended local assets.
Keep `icon` mask-safe and use `sidebarIcon` for colored identity artwork. A
release that omits referenced bytes can produce a broken conversation mask,
generic identity, or stale home poster even when publication succeeds.

The bundled workflow expects these GitHub repository variables:

- `TUTTI_AGENT_RELEASES_AWS_REGION`
- `TUTTI_AGENT_RELEASES_AWS_ROLE_ARN`
- `TUTTI_AGENT_RELEASES_S3_BUCKET`
- `TUTTI_AGENT_RELEASES_CLOUDFRONT_DISTRIBUTION_ID` when invalidation is used

Store the Ed25519 private key only in the repository secret
`TUTTI_AGENT_EXTENSION_SIGNING_PRIVATE_KEY`. Use GitHub OIDC for AWS access.
Never commit signing private keys, AWS credentials, or access tokens.

For a new repository, follow `aws-bootstrap.md`. The scaffold includes a
CloudFormation template that creates a private, versioned release bucket,
CloudFront origin access control, and a GitHub OIDC role restricted to the
repository's `main` branch. If the account already has the GitHub OIDC provider,
pass its ARN instead of attempting to create a duplicate provider.

The corresponding public key and `signingKeyId` belong in Tutti's trusted
source configuration. Private keys must not appear in Tutti defaults, workflow
inputs, artifacts, shell traces, or logs.

## Publication ordering

Publish in this order:

1. Validate the declarative package.
2. Create the reproducible ZIP, digest, byte size, and signed release record.
3. Upload versioned immutable objects.
4. Conditionally update `versions.json` from the observed ETag.
5. Update `latest.json` from the active record.
6. Invalidate only mutable CloudFront paths when required.

Never overwrite an existing version object. Mutable index writers must fail on
an ETag conflict and retry from freshly read state instead of discarding a
concurrent release.

## Local release verification

Before using AWS, generate an ephemeral Ed25519 key pair and run the repository
release tests. Build a local signed release with a test key and verify the
artifact, digest, size, manifest identity, and signature. Do not reuse the
production private key for local tests.

After publication, verify the public CDN rather than only S3:

```sh
curl -fsS https://cdn.example/agents/example/versions.json
curl -fsS https://cdn.example/agents/example/1.0.0/release.json
curl -fsSLo /tmp/example-1.0.0.zip \
  https://cdn.example/agents/example/1.0.0/example-1.0.0.zip
shasum -a 256 /tmp/example-1.0.0.zip
```

Compare the downloaded byte size and SHA-256 digest with `release.json`, then
verify its Ed25519 signature using the trusted public key. A successful upload
does not prove CloudFront origin routing, cache behavior, or public access.

## Activation sequence

Keep a new source disabled until:

- public index and package verification succeeds;
- the current Tutti build accepts the manifest/profile schemas;
- the declared runtime version exists and passes discovery plus ACP initialize;
- Target registration and composer discovery pass locally;
- rollout limitations, authentication, and quota behavior are documented.

Enable the source only after those checks. Preserve the last verified active
installation so transient network failure does not remove a working Agent.
