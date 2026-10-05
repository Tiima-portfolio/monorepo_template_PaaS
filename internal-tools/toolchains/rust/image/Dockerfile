# The Rust toolchain image: Rust from the official image with rustfmt, clippy
# and llvm-tools, cargo-llvm-cov and cargo-mutants, and Node for
# mutants-report.mjs. Base images are pinned by digest; in the air-gapped
# network, use the internal registry's copies and a crate mirror.
FROM node:24-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe AS node

FROM rust:1.99.0-slim-trixie@sha256:0952c7a429d2f53c7f1f5e0796190690e7d8db367ec4a66ce0419763b9e5e0d0
COPY --from=node /usr/local/bin/node /usr/local/bin/node
# The tools go to /usr/local/cargo/bin, on PATH; the crate cache is dropped, and
# HOME is writable by anyone, since toolchain images run as the caller's user.
RUN rustup component add rustfmt clippy llvm-tools \
 && cargo install --locked cargo-llvm-cov@0.9.1 cargo-mutants@27.1.0 \
 && rm -rf "$CARGO_HOME/registry" "$CARGO_HOME/git" \
 && mkdir -m 1777 /home/ci
# Cargo's crate cache under HOME, which CI mounts as a cache.
ENV HOME=/home/ci CARGO_HOME=/home/ci/.cargo
USER 10001
