# Sourced by /etc/bash.bashrc; keep scripts and non-interactive commands quiet.
[[ $- == *i* ]] || return 0

__docker_envs_banner() {
    local red='' amber='' cyan='' bold='' reset=''
    if [[ -t 1 && ${TERM:-dumb} != dumb && -z ${NO_COLOR+x} ]]; then
        red=$'\e[1;31m'
        amber=$'\e[0;33m'
        cyan=$'\e[0;36m'
        bold=$'\e[1m'
        reset=$'\e[0m'
    fi

    printf '\n%s  • • •%s  %sdocker_envs%s\n' "$red" "$reset" "$bold" "$reset"
    printf '%s  • • •%s  Development workspace\n' "$red" "$reset"
    printf '%s  • • •%s\n\n' "$red" "$reset"
    printf '  %sUser%s       %s (UID %s · GID %s)\n' \
        "$cyan" "$reset" "$(id -un 2>/dev/null || printf 'unknown')" "$(id -u)" "$(id -g)"
    printf '  %sWorkspace%s  %s\n' "$cyan" "$reset" "${HOME}/colcon_ws"
    if [[ -n ${ROS_DISTRO:-} ]]; then
        printf '  %sROS%s        %s\n' "$cyan" "$reset" "$ROS_DISTRO"
    fi
    if command -v claude >/dev/null 2>&1; then
        printf '  %sClaude%s     Ready — run claude to start\n' "$cyan" "$reset"
    fi
    printf '\n'

    if [[ $EUID -eq 0 ]]; then
        printf '%s' "$amber"
        cat <<'WARN'
  WARNING: This shell is running as root.
  Files created in mounted workspaces may become root-owned on the host.
  To use your host UID/GID, launch from the host with:

    docker run --user "$(id -u):$(id -g)" [OPTIONS] IMAGE
WARN
        printf '%s' "$reset"
    else
        printf '  Running as a non-root user. For writable host mounts, use the same\n'
        printf '  UID/GID as your host account (check with id on the host).\n'
    fi
    printf '\n'
}

__docker_envs_banner
unset -f __docker_envs_banner
