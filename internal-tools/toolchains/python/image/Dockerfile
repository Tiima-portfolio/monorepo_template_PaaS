# The Python toolchain image: Python from the official image and uv from its
# upstream image, both pinned by digest. In the air-gapped network, use the
# internal registry's copies and UV_INDEX_URL.
FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv

FROM python:3.13-slim-trixie@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f
COPY --from=uv /uv /uvx /usr/local/bin/
# Toolchain images run as the caller's user, with HOME writable by anyone, so
# CI can mount a cache there.
RUN mkdir -m 1777 /home/ci
# uv uses this image's Python only, never downloads one, and copies files out
# of its cache, which is on a different mount from the workspace.
ENV HOME=/home/ci UV_PYTHON_PREFERENCE=only-system UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
USER 10001
