# Monorepo template for a PaaS

A CI/CD skeleton for a monorepo of about 100 services, built by about 100 developers and 300 agents. Humans and agents create changes; the factory decides, from deterministic evidence and policy, whether each change may merge.

- The idea: [Evidence-Driven Software Factory](docs/evidence_driven_software_factory.md)
- The design this repo implements: [CI/CD skeleton plan](docs/ci-cd-skeleton-plan.md)

## Layout

Every file belongs to exactly one boundary, and a PR must stay inside one boundary.

| Boundary | Path | A PR in it may touch |
| --- | --- | --- |
| Product | `product/` | Anything under `product/` |
| Internal tool | `internal-tools/<tool>/` | Only that tool |
| Internal service | `internal-services/<service>/` | Only that service |
| CI / Factory | `ci/`, `.github/` | Only CI paths |
| Workspace | root files: `nx.json`, `package.json`, lock file, `.gitignore`, `.node-version` | Only root files |
| Platform | `platform/` | Only `platform/` |
| Test framework | `test-framework/` | Only `test-framework/` |
| Docs | `docs/`, `README.md` | Only docs |

## How a change gets in

1. Open a PR. The factory gate works out its boundary, risk tier (R0 to R3) and the evidence it needs.
2. Nx builds and tests only the projects the change affects.
3. Admission compares the evidence with what the tier requires. That is the one required check.
4. The merge queue squash-merges it onto `main`, keeping history linear.
5. On `main`, each affected service is versioned from git tags and its artifacts are published. Nothing is deployed.

## Working in the repo

```bash
npm ci
npm run check
```

`npm run check` runs lint, test and build for the projects your change affects, for every language, exactly as CI does.

A project is any folder with a `service.yaml`:

```yaml
name: orders
owner: team-orders
toolchains: [go, container]
criticality: normal
consumes: [billing]
```

The `toolchains` list picks targets from [`internal-tools/toolchains/`](internal-tools/toolchains/). Adding a language means adding one folder there.

## PR titles

PR titles use conventional prefixes, because the squash commit title sets the version bump:

- `fix:` patch
- `feat:` minor
- `feat!:` major
- `docs:`, `test:`, `chore:`, `ci:`, `build:` no release

## Status

Working skeleton, being built issue by issue. See the [skeleton issues](https://github.com/Tiima/monorepo_template_PaaS/issues?q=label%3Askeleton).

## Setting up a copy of this template

| Setting | Where | What for |
| --- | --- | --- |
| `FACTORY_APP_ID`, `FACTORY_APP_PRIVATE_KEY` | Repository secrets | The factory GitHub App. Give it Contents, Pull requests, Issues and Workflows read and write, and Actions read. The release and revert jobs mint a short-lived token from it on each run |
| `FACTORY_RUNNER_PR`, `FACTORY_RUNNER_QUEUE`, `FACTORY_RUNNER_MAIN` | Repository variables | Runner labels for the three pools in [`platform/runners/`](platform/runners/); GitHub-hosted runners when unset |
| `FACTORY_EVIDENCE_S3_URI`, `FACTORY_EVIDENCE_S3_ENDPOINT` and their secrets | Variables and secrets | The write-once evidence bucket; without them evidence stays as workflow artifacts |
| `FACTORY_BUILDKIT_ADDR`, `FACTORY_BUILDKIT_ADDR_MAIN`, `FACTORY_BUILDKIT_CACHE_REF` | Repository variables, optional | The [shared BuildKit service](docs/ci-cd-skeleton-plan.md#shared-buildkit-service): its PR and main instances and the registry layer cache. Container builds use the runner's local BuildKit when unset |
| `FACTORY_BUILDKIT_TLS`, `FACTORY_BUILDKIT_MAIN_TLS` | Repository secrets, optional | Client certificates for those instances: `tar -cz ca.crt tls.crt tls.key \| base64` |
| `FACTORY_ADMIN_TOKEN` | Repository secret, optional | Lets the daily ruleset check re-apply drifted rulesets |
| Rulesets | `node ci/factory/rulesets.mjs apply` | Branch protection for `main`; the merge queue and release-tag rulesets need an organization-owned repository |
