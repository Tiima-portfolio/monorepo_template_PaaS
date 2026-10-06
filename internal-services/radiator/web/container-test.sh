#!/bin/sh
# Smoke test for the radiator-web image: it starts as a non-root user and
# serves the page and its scripts.
set -eu
image="$1"
uid=$(docker run --rm --entrypoint id "$image" -u)
[ "$uid" != "0" ] || { echo "image runs as root"; exit 1; }
id=$(docker run -d -p 127.0.0.1::8080 "$image")
trap 'docker rm -f "$id" >/dev/null' EXIT
url="http://$(docker port "$id" 8080/tcp | head -1)"
for _ in $(seq 30); do
  curl -fsS "$url/" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "$url/" | grep -q '<title>Factory radiator</title>' || { docker logs "$id"; echo "no page"; exit 1; }
curl -fsS "$url/main.js" | grep -q "from './radiator.js'" || { echo "main.js missing or not compiled"; exit 1; }
curl -fsS -o /dev/null "$url/radiator.js" || { echo "radiator.js missing"; exit 1; }
echo "radiator-web image OK"
