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

## Trust boundaries

- **PR and merge queue runners hold no write credentials.** They run code a PR
  may have changed, so they can only read the cache and can't publish.
- **Only `main` runners write.** They build commits already admitted to
  `main`: cache writes, image pushes and releases happen there.
- **Every job gets a fresh runner.** Runners are ephemeral and never reused.
