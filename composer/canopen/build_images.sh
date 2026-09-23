#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/scripts/common.sh"
[[ $# -le 1 ]] || { echo "Expected at most one distribution" >&2; exit 2; }
select_distros "${1:-all}"
check_config
mkdir -p "$CANOPEN_ROOT/artifacts"
# Resolve once so every master-based image uses the same source snapshot.
resolve_revision() {
    git ls-remote https://github.com/ros-industrial/ros2_canopen.git "refs/heads/$1" | awk '{print $1}'
}
export CANOPEN_MASTER_REV="${CANOPEN_MASTER_REV:-$(resolve_revision master)}"
export CANOPEN_HUMBLE_REV="${CANOPEN_HUMBLE_REV:-$(resolve_revision humble)}"
[[ "$CANOPEN_MASTER_REV" =~ ^[0-9a-f]{40}$ && "$CANOPEN_HUMBLE_REV" =~ ^[0-9a-f]{40}$ ]]
printf 'CANOPEN_MASTER_REV=%s\nCANOPEN_HUMBLE_REV=%s\n' \
    "$CANOPEN_MASTER_REV" "$CANOPEN_HUMBLE_REV" > "$CANOPEN_ROOT/artifacts/revisions.env"
overall=0
for distro in "${DISTROS[@]}"; do
    out="$CANOPEN_ROOT/artifacts/$distro"
    mkdir -p "$out"
    os="$(distro_os "$distro")"
    base="docker_envs:$os-$distro"
    printf 'BUILDING\n' > "$out/build-status.txt"
    printf 'NOT_RUN (image rebuild)\n' > "$out/validation-status.txt"
    if ! docker image inspect "$base" >/dev/null 2>&1; then
        if ! bash "$CANOPEN_ROOT/scripts/build-base.sh" "$distro" \
            2>&1 | tee "$out/base-build.log"; then
            printf 'FAIL: base image\n' > "$out/build-status.txt"
            overall=1
            continue
        fi
    fi
    docker image inspect "$base" > "$out/base-image.json"
    if "${COMPOSE[@]}" --progress plain build "$distro" 2>&1 | tee "$out/build.log"; then
        docker image inspect "docker_envs/canopen:$distro" > "$out/image.json"
        docker image inspect --format '{{.Id}}' "docker_envs/canopen:$distro" > "$out/built-image-id.txt"
        printf 'PASS\n' > "$out/build-status.txt"
    else
        printf 'FAIL: CANopen image\n' > "$out/build-status.txt"
        overall=1
    fi
done
for distro in "${DISTROS[@]}"; do
    printf '%s: %s\n' "$distro" "$(cat "$CANOPEN_ROOT/artifacts/$distro/build-status.txt")"
done
exit "$overall"
