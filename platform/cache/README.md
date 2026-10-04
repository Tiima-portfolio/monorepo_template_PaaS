# Nx remote cache

Nx talks to a self-hosted cache over HTTP when
`NX_SELF_HOSTED_REMOTE_CACHE_SERVER` is set. Run any server that implements
Nx's remote cache HTTP API, backed by an S3-compatible bucket inside the
network (for example MinIO).

- Two tokens: `read-only-token` for the `pr` and `queue` runner pools, and
  `read-write-token` for the `main` pool. The server rejects writes with the
  read-only token, so a PR can never plant a cache entry.
- If the server is down, Nx falls back to building locally: slower, not stuck.
- Target: at least 80% cache hits on PR builds.
