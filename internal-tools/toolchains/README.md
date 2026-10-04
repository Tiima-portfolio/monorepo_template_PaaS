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
nightly run. Go has it, through gremlins; other languages can add it in
their own folder.
