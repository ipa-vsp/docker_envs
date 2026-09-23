#!/usr/bin/env bash
# Shared host-side helpers. Source this file from the public scripts.
set -euo pipefail
CANOPEN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$CANOPEN_ROOT/docker-compose.yml")
select_distros() {
    case "${1:-all}" in
        all) DISTROS=(rolling lyrical jazzy humble) ;;
        rolling|lyrical|jazzy|humble) DISTROS=("$1") ;;
        *) echo "Usage: $0 [all|rolling|lyrical|jazzy|humble]" >&2; exit 2 ;;
    esac
}
distro_os() {
    case "$1" in
        rolling|lyrical) echo 26.04 ;;
        jazzy) echo 24.04 ;;
        humble) echo 22.04 ;;
    esac
}
check_config() {
    local script
    for script in "$CANOPEN_ROOT"/*.sh "$CANOPEN_ROOT"/scripts/*.sh; do
        bash -n "$script"
    done
    "${COMPOSE[@]}" config --quiet
}
