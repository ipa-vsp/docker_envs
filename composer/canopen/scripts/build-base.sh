#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
distro="$1"
os="$(distro_os "$distro")"
creator="$CANOPEN_ROOT/../../creator"
if [[ "$distro" == rolling ]]; then
    # Rolling Resolute desktop is currently published only in ros2-testing.
    # Patch an isolated copy so the repository's creator remains untouched.
    overlay="$(mktemp -d "$CANOPEN_ROOT/artifacts/rolling/creator-XXXXXX")"
    cp -a "$creator" "$overlay/creator"
    patch --batch --forward -p1 -d "$overlay" < "$CANOPEN_ROOT/patches/creator/rolling-testing.patch"
    sha256sum "$CANOPEN_ROOT/patches/creator/rolling-testing.patch" > \
        "$CANOPEN_ROOT/artifacts/rolling/base-patches.txt"
    creator="$overlay/creator"
fi
exec bash "$creator/scripts/run_env.sh" \
    -b -o "$os" -v "$distro" -u skip -n admin -U 1000 -G 1000 -i "docker_envs:$os-$distro"
