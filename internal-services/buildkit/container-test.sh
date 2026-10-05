#!/bin/sh
# Smoke test for the BuildKit service image: the daemon must start as a
# non-root user with the factory's config and build an image.
set -eu
image="$1"
name="buildkit-smoke-$$"

# Rootless buildkitd needs these unconfined profiles (see BuildKit's
# docs/rootless.md); the Kubernetes manifests set the same.
docker run -d --name "$name" \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  --security-opt systempaths=unconfined \
  "$image" >/dev/null
# On failure, show the daemon's last log lines.
cleanup() {
  rc=$?
  [ "$rc" -eq 0 ] || docker logs "$name" 2>&1 | tail -20
  docker rm -f "$name" >/dev/null
}
trap cleanup EXIT

i=0
until docker exec "$name" buildctl debug workers >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -lt 60 ] || { echo "buildkitd did not start"; exit 1; }
  sleep 1
done

uid=$(docker exec "$name" id -u)
[ "$uid" != "0" ] || { echo "buildkitd runs as root"; exit 1; }

# The factory's config is loaded: its 6h garbage collection rule is on the worker.
docker exec "$name" buildctl debug workers --verbose | grep -q 'Keep duration:.*6h0m0s' \
  || { echo "factory buildkitd.toml not loaded"; exit 1; }

# Build a small image from a Dockerfile, offline: FROM scratch needs no registry.
docker exec "$name" sh -c '
  set -e
  ctx=$(mktemp -d)
  printf "FROM scratch\nCOPY hello /hello\n" > "$ctx/Dockerfile"
  echo hello > "$ctx/hello"
  buildctl build --frontend dockerfile.v0 --local context="$ctx" --local dockerfile="$ctx" \
    --output type=oci,dest="$ctx/image.tar"
  tar -tf "$ctx/image.tar" | grep -q "^oci-layout$"
'
echo "buildkit image OK"
