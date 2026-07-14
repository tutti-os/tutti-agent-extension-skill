# AWS and GitHub release bootstrap

Use this path only when the Agent repository does not already publish through
approved shared Tutti release infrastructure. Prefer a shared bucket,
distribution, and OIDC role when the organization provides them.

## Deploy isolated infrastructure

The scaffold copies `infra/aws/agent-extension-release-infrastructure.yaml`.
Deploy it with the configured administrator profile:

```sh
aws cloudformation deploy \
  --profile AdministratorAccess-250509935467 \
  --stack-name tutti-agent-example-release \
  --template-file infra/aws/agent-extension-release-infrastructure.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    GitHubOwner=tutti-os \
    GitHubRepository=agent-extension-example \
    CreateGitHubOIDCProvider=false \
    ExistingGitHubOIDCProviderArn=arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com
```

Set `CreateGitHubOIDCProvider=true` only when the AWS account does not already
contain the GitHub Actions OIDC provider. IAM OIDC providers are account-wide;
trying to create a duplicate fails the stack.

Read the outputs without opening the AWS console:

```sh
aws cloudformation describe-stacks \
  --profile AdministratorAccess-250509935467 \
  --stack-name tutti-agent-example-release \
  --query 'Stacks[0].Outputs' \
  --output table
```

The template creates a private versioned S3 bucket, CloudFront Origin Access
Control and distribution, a bucket policy restricted to that distribution,
and a repository-scoped GitHub OIDC role. The role can write only under
`tutti-agent-releases/` and invalidate only its generated distribution.

## Configure the GitHub repository

Map stack outputs to repository variables:

```sh
gh variable set TUTTI_AGENT_RELEASES_AWS_REGION --body '<AwsRegion>'
gh variable set TUTTI_AGENT_RELEASES_AWS_ROLE_ARN --body '<RoleArn>'
gh variable set TUTTI_AGENT_RELEASES_S3_BUCKET --body '<BucketName>'
gh variable set TUTTI_AGENT_RELEASES_CLOUDFRONT_DISTRIBUTION_ID --body '<CloudFrontDistributionId>'
gh secret set TUTTI_AGENT_EXTENSION_SIGNING_PRIVATE_KEY < signing-private-key.pem
```

Pass the `ReleaseAssetsBaseUrl` output to the scaffold or update the generated
workflow `RELEASE_ASSETS_BASE_URL`. Do not store the private signing key in
CloudFormation parameters, repository variables, artifacts, or shell history.

## Verify before first publication

```sh
aws cloudformation validate-template \
  --template-body file://infra/aws/agent-extension-release-infrastructure.yaml
gh variable list
gh secret list
```

After workflow publication, fetch `versions.json`, `release.json`, and the ZIP
through the CloudFront URL and verify digest, size, and signature as described
in `release-and-rollout.md`.
