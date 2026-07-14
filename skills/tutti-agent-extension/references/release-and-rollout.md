# Release and rollout

## Repository release contract

The extension repository owns source metadata and calls Tutti's reusable
release workflow. Keep the caller minimal so signing, archive validation, index
updates, and publication rules remain centralized.

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      version:
        description: Immutable extension version
        required: true

permissions:
  contents: read
  id-token: write

jobs:
  publish:
    uses: tutti-os/tutti/.github/workflows/publish-tutti-agent-extension.yml@main
    with:
      agent_key: example
      version: ${{ inputs.version }}
      min_tutti_version: "0.0.0"
      package_command: pnpm package:tutti-agent
      package_dir: build/tutti-agent/package
      signing_key_id: tutti-example-release-v1
      aws_region: ${{ vars.TUTTI_APP_RELEASES_AWS_REGION }}
      aws_role_arn: ${{ vars.TUTTI_APP_RELEASES_AWS_ROLE_ARN }}
      s3_bucket: ${{ vars.TUTTI_APP_RELEASES_S3_BUCKET }}
      s3_prefix: tutti-agent-releases
      release_assets_base_url: https://cdn.example/tutti-agent-releases
      cloudfront_distribution_id: ${{ vars.TUTTI_AGENT_RELEASES_CLOUDFRONT_DISTRIBUTION_ID }}
    secrets:
      signing_private_key: ${{ secrets.TUTTI_AGENT_EXTENSION_SIGNING_PRIVATE_KEY }}
```

The package command must build a clean directory; never publish a
repository-root ZIP. The reusable workflow owns the centralized release tools.

## Required GitHub and AWS configuration

Use GitHub OIDC for AWS access. Configure the variables expected by Tutti's
reusable workflow, including the AWS role, region, release bucket, CloudFront
distribution, and public release base URL. Store only the Ed25519 private key
in the repository secret `TUTTI_AGENT_EXTENSION_SIGNING_PRIVATE_KEY`.

The public key and `signingKeyId` belong in Tutti's trusted-source defaults.
Private keys must not appear in source, workflow input, artifacts, shell trace,
or logs.

## Publication ordering

Publish in this order:

1. Build and validate the declarative package.
2. Create the deterministic ZIP, digest, byte size, and signed release record.
3. Upload versioned immutable objects.
4. Conditionally update `latest.json` and `versions.json` with the observed
   ETag.
5. Conditionally update the global `catalog.json` entry.
6. Invalidate only mutable CloudFront paths when required.

Never overwrite an existing version object. Mutable index writers must fail on
an ETag conflict and retry from freshly read state instead of discarding a
concurrent release.

## Public verification

Verify the public CDN, not only S3:

```sh
curl -fsS https://cdn.example/agents/example/versions.json
curl -fsS https://cdn.example/agents/example/1.0.0/release.json
curl -fsSLo /tmp/example-1.0.0.zip \
  https://cdn.example/agents/example/1.0.0/package.zip
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

Enable by defaults/configuration only after those checks. Preserve the last
verified active installation so transient network failure does not remove an
already working Agent.
