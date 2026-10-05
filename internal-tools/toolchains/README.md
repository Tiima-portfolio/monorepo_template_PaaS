# Toolchains

One folder per language or build kind. Each folder holds a `toolchain.yaml`
with the Nx targets for projects that list it in their `service.yaml`:

```yaml
# product/services/orders/service.yaml
name: orders
owner: team-orders
toolchains: [go, container]
criticality: normal
consumes: [billing]
```

`plugin.js` reads every `toolchain.yaml` and every `service.yaml` and builds
the Nx project graph from them. To add a language, add a folder with a
`toolchain.yaml`; nothing in `ci/`, `nx.json` or any workflow changes.

`{name}` and `{projectRoot}` in a toolchain's commands and inputs are
replaced per project. Commands run with the project root as working directory.

## Creating a project

```bash
node internal-tools/toolchains/new-service.mjs --name orders --lang typescript --owner team-orders
```

`--kind` is `product` (default), `internal-service` or `internal-tool`, and
`--with container` adds a second toolchain. The new project gets the
toolchain's `template/`, a `service.yaml` and a `guardrails.yaml` with defaults.

## Toolchains

| Toolchain | Lint | Test | Build | Package |
| --- | --- | --- | --- | --- |
| typescript | `tsc --noEmit` | `node --test` | `tsc` | `npm pack` |
| go | `gofmt -l`, `go vet` | `go test` | static binary | `.tar.gz` |
| python | `ruff check`, `ruff format --check` | `pytest` via `uv` | wheel via `uv build` | wheel |
| rust | `cargo fmt --check`, `cargo clippy` | `cargo llvm-cov` (tests with coverage) | release binary | `.tar.gz` |
| container | `hadolint` | `docker run` or `container-test.sh` | image via `docker buildx` | image archive, pushed to the registry on release |

When a project lists more than one toolchain, targets with the same name run
in the order listed. `toolchains: [go, container]` builds the Go binary and
then the image that copies it.

Each toolchain folder is also an Nx project, `toolchain-<name>`, and every
service depends on the toolchains it lists. A change to the Go toolchain
therefore re-tests every Go service, and they get a patch release when it
merges.

A toolchain may also define a `mutation` target that writes
`mutation/report.json` (files with their mutations, each KILLED or LIVED).
The factory uses it for the mutation score from risk tier R2 up and in the
nightly run. Go uses gremlins, TypeScript Stryker, Python mutmut and Rust
cargo-mutants; a small converter in each toolchain folder writes the common
report. `{toolchainDir}` in a command is the toolchain folder, relative to
the project.

Container images are built through `container/buildx.mjs`. It uses the shared
BuildKit service ([`internal-services/buildkit`](../../internal-services/buildkit/))
when `FACTORY_BUILDKIT_ADDR` is set and the service answers, and the local
BuildKit otherwise, with a warning if the service was set but down. With the
service, `FACTORY_BUILDKIT_TLS_DIR` holds the client certificate and
`FACTORY_BUILDKIT_CACHE_REF` a registry repository for the layer cache, which
only runners with `FACTORY_BUILDKIT_CACHE_WRITE=true` (main) write.

Test targets also write per-test reports to `test-results/` (JUnit XML for
TypeScript and Python, Go's JSON test events), so the factory can quarantine
a single flaky test instead of a whole project.

## Toolchain images

CI runs each toolchain's targets in a container image built in this folder and
pinned by digest in its `toolchain.yaml`:

```yaml
# internal-tools/toolchains/go/toolchain.yaml
image: ghcr.io/<owner>/<repo>/ci-go:<commit>@sha256:<digest>
```

A target can name its own image instead (the container toolchain's `lint`
runs in `ci-lint`), or set `image: false` to stay on the host (its image
builds use BuildKit on the host).

| Image | Folder | Holds |
| --- | --- | --- |
| `ci-lint` | `lint-image/` | hadolint, shellcheck, actionlint, yamllint, markdownlint-cli2, taplo |
| `ci-typescript` | `typescript/image/` | Node and npm |
| `ci-go` | `go/image/` | Go, gremlins, Node |
| `ci-python` | `python/image/` | Python, uv |
| `ci-rust` | `rust/image/` | Rust with rustfmt, clippy, llvm-tools, cargo-llvm-cov, cargo-mutants, Node |

Each image folder is a `[container]` project with a smoke test that checks the
tool versions against the toolchain's `setup.mise`, which stays the version
list for local work. On `main`, the `images` workflow publishes a changed image
to GHCR and writes its digest to the run summary; moving the pin is a separate
PR, and it re-tests every service on that toolchain.

`in-image.sh` does the running. With `FACTORY_TOOLCHAIN_IMAGES=true`, as CI
sets it, a target runs in its image with `docker run`: as your user, with the
workspace mounted at the same path and a cache directory per image as `HOME`.
Without it, targets run on the host with the tools `mise` installs. To check a
change exactly as CI does:

```bash
FACTORY_TOOLCHAIN_IMAGES=true npx nx affected -t lint test build
```

For an air-gapped network, mirror the images into the internal registry and set
`FACTORY_TOOLCHAIN_REGISTRY` to its host; the digests stay the same.
