#!/bin/sh
# Runs a toolchain target's command in the toolchain's pinned image when
# FACTORY_TOOLCHAIN_IMAGES=true, and on the host otherwise. plugin.js wraps
# every target whose toolchain names an image:
#
#   sh in-image.sh <image> <command>
#
# Projects outside the toolchains, such as CI's own, can name a toolchain
# instead of an image, and get the image pinned in its toolchain.yaml:
#
#   sh in-image.sh python 'uv run pytest'
#
# The workspace is mounted at the same path, so reports keep their paths. The
# command runs as the caller's user, with a cache directory per image as HOME.
#
# Optional settings:
#   FACTORY_TOOLCHAIN_REGISTRY  air-gapped: pull the same digest from this
#                               registry instead, e.g. registry.example.internal
#   FACTORY_TOOLCHAIN_CACHE     where the per-image caches live
set -eu
image="$1"
command="$2"
if [ "${FACTORY_TOOLCHAIN_IMAGES:-}" != true ]; then
  exec sh -c "$command"
fi
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
if [ -f "$here/$image/toolchain.yaml" ]; then
  image=$(sed -n 's/^image: *//p' "$here/$image/toolchain.yaml")
fi
if [ -n "${FACTORY_TOOLCHAIN_REGISTRY:-}" ]; then
  image="$FACTORY_TOOLCHAIN_REGISTRY/${image#*/}"
fi
name=${image##*/}
name=${name%%@*}
name=${name%%:*}
cache="${FACTORY_TOOLCHAIN_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/factory-toolchains}/$name"
mkdir -p "$cache"
set -- --rm --user "$(id -u):$(id -g)" -v "$root:$root" -v "$cache:/home/ci" -w "$PWD"
# The factory's settings and the package mirror settings, when they are set.
for var in $(env | sed -n 's/^\(FACTORY_[A-Z0-9_]*\)=.*/\1/p') CI NPM_CONFIG_REGISTRY GOPROXY GONOSUMDB GOFLAGS UV_INDEX_URL UV_DEFAULT_INDEX; do
  set -- "$@" -e "$var"
done
exec docker run "$@" "$image" sh -c "$command"
