# Product

Everything that ships. A PR inside `product/` may change several services
together, so a feature lands as one squash commit.

Each service is a folder with a `service.yaml` (owner, toolchains, criticality,
what it consumes, its contract) and a `guardrails.yaml` its owner controls.
Create one with:

```bash
node internal-tools/toolchains/new-service.mjs --name <name> --lang <toolchain> --owner <team>
```
