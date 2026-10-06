#!/bin/sh
# Smoke test for the ci-helm image: Helm is the version the toolchain pins (or,
# before the toolchain exists, the one the Dockerfile copies), and it can
# create, lint and render a chart as an arbitrary user.
set -eu
image="$1"
run() { docker run --rm --user 12345:12345 "$image" "$@"; }
if [ -f ../toolchain.yaml ]; then
  helm=$(sed -n 's/^ *helm: "\(.*\)"/\1/p' ../toolchain.yaml)
else
  helm=$(sed -n 's#^FROM alpine/helm:\([^@]*\)@.*#\1#p' Dockerfile)
fi
run helm version --short | grep -q "^v$helm+" || { echo "helm is not $helm"; exit 1; }
run sh -ec '
  cd /tmp && helm create smoke >/dev/null
  helm lint smoke >/dev/null
  helm template smoke smoke | grep -q "^kind: Deployment"'
echo "ci-helm image OK"
