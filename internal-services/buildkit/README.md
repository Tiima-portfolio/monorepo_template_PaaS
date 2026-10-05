# buildkit

The shared BuildKit service, owned by team-platform: a rootless `buildkitd`
that container builds use when `FACTORY_BUILDKIT_ADDR` is set. Without it they
use the runner's local BuildKit, as on public GitHub-hosted runners. See
[Shared BuildKit service](../../docs/ci-cd-skeleton-plan.md#shared-buildkit-service).

| File | What |
| --- | --- |
| `Dockerfile` | The upstream rootless image, pinned by digest, with our config |
| `buildkitd.toml` | Daemon settings: garbage collection, parallelism, history, mirrors |
| `deploy/` | Kustomize manifests: `overlays/pr` and `overlays/main` |
| `container-test.sh` | Renders both overlays, starts the daemon and builds a small image through it |

The image is released like any other service image, as
`<registry>/buildkit:<version>`. Bumping BuildKit is a digest change in the
`Dockerfile`; the smoke test proves the new daemon still builds.

## Host requirement

Rootless BuildKit needs unprivileged user namespaces. Hosts that restrict
them through AppArmor (Ubuntu 23.10 and later, so also GitHub-hosted runners)
need `kernel.apparmor_restrict_unprivileged_userns=0`; the smoke test sets it
on CI runners itself. Cluster nodes that run the service need it too.

## Deploying it

The factory never deploys anything; the CI/platform team applies these with
its own tooling, after setting the image in `deploy/base/kustomization.yaml`
to a released version and digest. It needs cert-manager.

```bash
kubectl apply -k deploy/overlays/pr
kubectl apply -k deploy/overlays/main
```

| Instance | Namespace | Serves | Why separate |
| --- | --- | --- | --- |
| `buildkit-pr` | `buildkit-pr` | Runner pods labelled `factory.dev/runner-pool: pr` or `queue` | Build steps of PR code run inside it |
| `buildkit-main` | `buildkit-main` | Runner pods labelled `factory.dev/runner-pool: main` | Builds what is released; never sees unadmitted code |

Each instance has its own CA. Clients use the `buildkit-client-certs` Secret
of their instance (`ca.crt`, `tls.crt`, `tls.key`) and the address
`tcp://buildkit.<namespace>.svc:1234`.

## Running it locally

```bash
docker run -d --name buildkitd \
  --security-opt seccomp=unconfined --security-opt apparmor=unconfined \
  --security-opt systempaths=unconfined buildkit:ci
docker exec buildkitd buildctl debug workers
```
