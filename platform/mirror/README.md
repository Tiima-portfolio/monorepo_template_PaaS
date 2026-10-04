# Package and image mirrors

Builds reach packages only through internal mirrors. Set these on the runner
images and developer machines; the toolchains use them without changes.

| Ecosystem | Setting |
| --- | --- |
| npm | `NPM_CONFIG_REGISTRY=https://npm.<internal-domain>/` |
| Go | `GOPROXY=https://goproxy.<internal-domain>`, `GONOSUMDB`, `GOFLAGS=-mod=mod` |
| Python (uv) | `UV_INDEX_URL=https://pypi.<internal-domain>/simple` |
| Rust | `.cargo/config.toml` source replacement to the internal crate mirror |
| Container base images | `FROM <internal-registry>/library/<image>@sha256:<digest>` |
| Toolchain tools (Node, Go, Python, uv, Rust, hadolint) | baked into the runner image at the versions in each `toolchain.yaml`, so jobs download nothing |
| BuildKit image | the `FACTORY_BUILDKIT_IMAGE` repository variable |

New packages are requested through the mirror's intake: security approves
them, the mirror syncs, and the waiting PR is re-run. Security fixes have a
fast lane.
