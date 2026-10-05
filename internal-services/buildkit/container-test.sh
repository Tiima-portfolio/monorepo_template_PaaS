#!/bin/sh
# Smoke test for the BuildKit service: both instances' manifests render, and
# the daemon starts as a non-root user with the factory's config and builds
# an image.
set -eu
image="$1"
name="buildkit-smoke-$$"

if command -v kubectl >/dev/null 2>&1; then
  for overlay in pr main; do
    kubectl kustomize "deploy/overlays/$overlay" >/dev/null \
      || { echo "deploy/overlays/$overlay does not render"; exit 1; }
  done
else
  echo "kubectl not found: skipping the manifest check"
fi

# Rootless buildkitd needs unprivileged user namespaces. Ubuntu 24.04 hosts,
# including GitHub-hosted runners, restrict them through AppArmor; cluster
# nodes need the same setting (see README). On an ephemeral CI runner we
# lift the restriction; elsewhere we say what to change.
sysctl=/proc/sys/kernel/apparmor_restrict_unprivileged_userns
if [ "$(cat "$sysctl" 2>/dev/null || echo 0)" = "1" ]; then
  if [ "${CI:-}" = "true" ]; then
    sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
  else
    echo "This host restricts unprivileged user namespaces; run: sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
    exit 1
  fi
fi

# Rootless buildkitd needs these unconfined profiles (see BuildKit's
# docs/rootless.md). Kubernetes has no systempaths option, so the manifests
# use --oci-worker-no-process-sandbox instead.
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
