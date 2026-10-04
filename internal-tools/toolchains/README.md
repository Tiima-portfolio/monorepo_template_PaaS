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
