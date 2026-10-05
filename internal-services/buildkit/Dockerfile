# The shared BuildKit service: rootless buildkitd with the factory's config.
# Pinned by digest; in the air-gapped network use the internal registry's copy.
FROM moby/buildkit:v0.33.1-rootless@sha256:f8a833b2de9d68e27f0815e4a737abdfaf8a2e4c615650557df11025101557b4
COPY buildkitd.toml /home/user/.config/buildkit/buildkitd.toml
# The base image's non-root user; numeric so the host can resolve it (DL3066).
USER 1000:1000
