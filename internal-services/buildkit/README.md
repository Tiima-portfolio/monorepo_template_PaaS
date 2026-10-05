# buildkit

The shared BuildKit service, owned by team-platform: a rootless `buildkitd`
that container builds use when `FACTORY_BUILDKIT_ADDR` is set. Without it they
use the runner's local BuildKit, as on public GitHub-hosted runners. See
[Shared BuildKit service](../../docs/ci-cd-skeleton-plan.md#shared-buildkit-service).

| File | What |
| --- | --- |
| `Dockerfile` | The upstream rootless image, pinned by digest, with our config |
| `buildkitd.toml` | Daemon settings: garbage collection, parallelism, history, mirrors |
| `container-test.sh` | Starts the daemon and builds a small image through it |

The image is released like any other service image, as
`<registry>/buildkit:<version>`. Bumping BuildKit is a digest change in the
`Dockerfile`; the smoke test proves the new daemon still builds.

## Running it locally

```bash
docker run -d --name buildkitd \
  --security-opt seccomp=unconfined --security-opt apparmor=unconfined \
  --security-opt systempaths=unconfined buildkit:ci
docker exec buildkitd buildctl debug workers
```
