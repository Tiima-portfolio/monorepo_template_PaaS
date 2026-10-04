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
