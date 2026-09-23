#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/scripts/common.sh"
[[ $# -le 1 ]] || { echo "Expected at most one distribution" >&2; exit 2; }
select_distros "${1:-all}"
check_config
overall=0
container=""
cleanup() {
    if [[ -n "$container" ]]; then docker rm -f "$container" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for distro in "${DISTROS[@]}"; do
    out="$CANOPEN_ROOT/artifacts/$distro"
    mkdir -p "$out"
    printf 'RUNNING\n' > "$out/validation-status.txt"
    image="docker_envs/canopen:$distro"
    if [[ ! -f "$out/build-status.txt" ]] || [[ "$(cat "$out/build-status.txt")" != PASS ]] || \
        [[ "$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null || true)" != "$(cat "$out/built-image-id.txt" 2>/dev/null || true)" ]]; then
        printf 'BLOCKED: run build_images.sh %s successfully first\n' "$distro" > "$out/validation-status.txt"
        overall=1
        continue
    fi
    # Only this short-lived helper can load modules. Test containers need NET_ADMIN alone.
    if ! docker run --rm --user root --cap-add SYS_MODULE \
        --mount type=bind,src=/lib/modules,dst=/lib/modules,readonly \
        --entrypoint /usr/sbin/modprobe "$image" vcan > "$out/vcan-setup.log" 2>&1; then
        printf 'BLOCKED: host vcan module (see vcan-setup.log)\n' > "$out/validation-status.txt"
        overall=1
        continue
    fi
    # Archive previous results so a failed startup cannot appear to have old passing tests.
    if [[ -d "$out/results" ]]; then
        mv "$out/results" "$out/results-$(date -u +%Y%m%dT%H%M%S)-$$"
    fi
    container="canopen-validate-$distro-$$"
    rc=0
    "${COMPOSE[@]}" run --no-deps -T --name "$container" "$distro" \
        python3 /opt/canopen/validate.py 2>&1 | tee "$out/validation.log" || rc=$?
    docker inspect "$container" > "$out/validation-container.json"
    if ! docker cp "$container:/tmp/canopen-results" "$out/results"; then rc=1; fi
    cleanup
    container=""
    if [[ $rc -eq 0 ]]; then
        printf 'PASS\n' > "$out/validation-status.txt"
    else
        printf 'FAIL: validation exited %s (see results/summary.json)\n' "$rc" > "$out/validation-status.txt"
        overall=1
    fi
done
for distro in "${DISTROS[@]}"; do
    printf '%s: %s\n' "$distro" "$(cat "$CANOPEN_ROOT/artifacts/$distro/validation-status.txt")"
done
exit "$overall"
