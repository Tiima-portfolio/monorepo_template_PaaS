# The TypeScript toolchain image: Node and npm from the official image, pinned
# by digest. In the air-gapped network, use the internal registry's copy.
FROM node:24-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe
# Stryker's test runner needs ps. Toolchain images run as the caller's user,
# with HOME writable by anyone, so CI can mount a cache there.
RUN apt-get update \
 && apt-get install -y --no-install-recommends procps=2:4.0.4-9 \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -m 1777 /home/ci
ENV HOME=/home/ci
USER 10001
