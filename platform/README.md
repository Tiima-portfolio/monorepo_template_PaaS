# Platform

Configuration templates for running the factory inside an air-gapped network,
with GitHub as the only outside service. Nothing here is applied
automatically; the CI/platform team applies it with its own tooling.

| Piece | Folder | Used by |
| --- | --- | --- |
| Runner pools: `pr`, `queue`, `main` | [`runners/`](runners/) | `FACTORY_RUNNER_PR`, `FACTORY_RUNNER_QUEUE`, `FACTORY_RUNNER_MAIN` repository variables |
| Nx remote cache | [`cache/`](cache/) | `NX_SELF_HOSTED_REMOTE_CACHE_SERVER` and its access tokens |
| Write-once evidence bucket | [`evidence/`](evidence/) | The evidence collector (issue #21) |
| Package and image mirrors | [`mirror/`](mirror/) | Toolchains, through standard environment variables |
| Trust zones: namespaces, service accounts, network policies | [`zones/`](zones/) | Separates PR code from the trusted factory |
| Shared BuildKit service | [`internal-services/buildkit/deploy/`](../internal-services/buildkit/deploy/) | `FACTORY_BUILDKIT_*` on the runner pods, read by the container toolchain |

## Trust boundaries

- **PR and merge queue runners hold no write credentials.** They run code a PR
  may have changed, so they can only read the cache and can't publish.
- **Only `main` runners write.** They build commits already admitted to
  `main`: cache writes, image pushes and releases happen there.
- **PR code never reaches the main BuildKit.** The `pr` and `queue` pools use
  the `buildkit-pr` instance; only the `main` pool reaches `buildkit-main`,
  and only it writes the registry layer cache.
- **Every job gets a fresh runner.** Runners are ephemeral and never reused.

## Evidence index

[`evidence/schema.sql`](evidence/schema.sql) creates the index table. When the
`FACTORY_EVIDENCE_DB_URL` secret is set, the evidence collector writes one row
per check and per decision for every commit on `main`.
