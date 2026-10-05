# The Go toolchain image: Go from the official image, gremlins for mutation
# testing, and Node for go-test.mjs. Base images are pinned by digest; in the
# air-gapped network, use the internal registry's copies and GOPROXY.
FROM node:24-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe AS node

FROM golang:1.25-trixie@sha256:2c4c60ef415fbfa5e90300722293bef36c5e63fae17570ce18f580af933dbd73
COPY --from=node /usr/local/bin/node /usr/local/bin/node
# Tools go to /usr/local/bin and the module cache is dropped. Toolchain images
# run as the caller's user on a workspace mounted from the host, so HOME is
# writable by anyone and git (for go build's VCS stamp) trusts any repository.
RUN GOBIN=/usr/local/bin go install github.com/go-gremlins/gremlins/cmd/gremlins@v0.6.0 \
 && go clean -modcache -cache \
 && git config --system --add safe.directory '*' \
 && mkdir -m 1777 /home/ci
# Module and build caches under HOME, which CI mounts as a cache.
ENV HOME=/home/ci GOPATH=/home/ci/go
USER 10001
