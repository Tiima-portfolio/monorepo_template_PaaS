#!/bin/sh
# Smoke test for the edge-proxy image: it must start, print its greeting and
# run as a non-root user.
set -eu
image="$1"
out=$(docker run --rm "$image")
[ "$out" = "Hello from edge-proxy" ] || { echo "unexpected output: $out"; exit 1; }
uid=$(docker run --rm --entrypoint id "$image" -u)
[ "$uid" != "0" ] || { echo "image runs as root"; exit 1; }
echo "edge-proxy image OK"
