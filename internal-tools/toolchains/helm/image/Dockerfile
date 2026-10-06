# The Helm toolchain image: the helm binary from its upstream image on Alpine,
# both pinned by digest. In the air-gapped network, use the internal
# registry's copies.
FROM alpine/helm:4.3.0@sha256:a6cf54599ccb99d90cf0712b30f03fdb3cab062e6b94e0418cc4db7e8a1464b2 AS helm

FROM alpine:3.22@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8
COPY --from=helm /usr/bin/helm /usr/local/bin/helm
# Toolchain images run as the caller's user, with HOME writable by anyone, so
# CI can mount a cache there.
RUN mkdir -m 1777 /home/ci
ENV HOME=/home/ci
USER 10001
