#!/bin/sh
# Smoke test for the radiator-api image: it starts as a non-root user, answers
# its health check and serves the radiator data.
set -eu
image="$1"
uid=$(docker run --rm --entrypoint id "$image" -u)
[ "$uid" != "0" ] || { echo "image runs as root"; exit 1; }
id=$(docker run -d -p 127.0.0.1::8000 "$image")
trap 'docker rm -f "$id" >/dev/null' EXIT
url="http://$(docker port "$id" 8000/tcp | head -1)"
for _ in $(seq 30); do
  curl -fsS "$url/healthz" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "$url/healthz" | grep -q '"ok"' || { docker logs "$id"; echo "no health check answer"; exit 1; }
curl -fsS "$url/api/radiator" | grep -q '"services"' || { echo "no radiator data"; exit 1; }
echo "radiator-api image OK"
