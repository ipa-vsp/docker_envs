#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: setup-local-bashrc.sh [options]

Idempotently install a docker_envs-inspired shell configuration into ~/.bashrc.

Options:
  --ros-distro <name>    Default ROS distro to source from /opt/ros (optional).
  --zenoh-setup <path>   Path to zenoh workspace setup file (default: /home/ws_rmw_zenoh/install/local_setup.bash).
  --no-zenoh             Skip sourcing any zenoh workspace, even if RMW_IMPLEMENTATION=rmw_zenoh_cpp.
  --bashrc <path>        Target bashrc file (default: ~/.bashrc).
  -h, --help             Show this message.

Environment overrides:
  ROS_DISTRO_DEFAULT     Same as --ros-distro when the flag is omitted.
  ZENOH_SETUP_DEFAULT    Same as --zenoh-setup when the flag is omitted.
EOF
}

ROS_DISTRO_DEFAULT="${ROS_DISTRO_DEFAULT:-}"
ZENOH_SETUP_DEFAULT="${ZENOH_SETUP_DEFAULT:-/home/ws_rmw_zenoh/install/local_setup.bash}"
BASHRC_PATH="${HOME}/.bashrc"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ros-distro)
      [[ $# -lt 2 ]] && { echo "Missing argument for --ros-distro" >&2; usage; exit 1; }
      ROS_DISTRO_DEFAULT="$2"
      shift 2
      ;;
    --zenoh-setup)
      [[ $# -lt 2 ]] && { echo "Missing argument for --zenoh-setup" >&2; usage; exit 1; }
      ZENOH_SETUP_DEFAULT="$2"
      shift 2
      ;;
    --no-zenoh)
      ZENOH_SETUP_DEFAULT=""
      shift
      ;;
    --bashrc)
      [[ $# -lt 2 ]] && { echo "Missing argument for --bashrc" >&2; usage; exit 1; }
      BASHRC_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

CONFIG_FILE="${HOME}/.docker_envs_shell"
BLOCK_START="# >>> docker_envs shell configuration >>>"
BLOCK_END="# <<< docker_envs shell configuration <<<"
SOURCE_SNIPPET='[ -f "$HOME/.docker_envs_shell" ] && source "$HOME/.docker_envs_shell"'

mkdir -p "$(dirname "${CONFIG_FILE}")"
touch "${CONFIG_FILE}"

# Backup the existing bashrc once.
if [[ -f "${BASHRC_PATH}" && ! -f "${BASHRC_PATH}.pre_docker_envs" ]]; then
  cp "${BASHRC_PATH}" "${BASHRC_PATH}.pre_docker_envs"
elif [[ ! -f "${BASHRC_PATH}" ]]; then
  touch "${BASHRC_PATH}"
fi

cat > "${CONFIG_FILE}" <<EOF
${BLOCK_START}

ROS_DISTRO_DEFAULT="${ROS_DISTRO_DEFAULT}"
ZENOH_SETUP_PATH="${ZENOH_SETUP_DEFAULT}"

__docker_envs_select_ros_distro() {
  if [ -n "\${ROS_DISTRO:-}" ]; then
    echo "\$ROS_DISTRO"
  elif [ -n "\${ROS_DISTRO_DEFAULT:-}" ]; then
    echo "\$ROS_DISTRO_DEFAULT"
  fi
}

__docker_envs_source_ros() {
  local chosen
  chosen="\$(__docker_envs_select_ros_distro)"
  if [ -n "\$chosen" ] && [ -f "/opt/ros/\${chosen}/setup.bash" ]; then
    # shellcheck disable=SC1090
    source "/opt/ros/\${chosen}/setup.bash"
  fi
}

__docker_envs_source_zenoh() {
  if [ "\${RMW_IMPLEMENTATION:-}" = "rmw_zenoh_cpp" ] && [ -n "\${ZENOH_SETUP_PATH:-}" ] && [ -f "\$ZENOH_SETUP_PATH" ]; then
    # shellcheck disable=SC1090
    source "\$ZENOH_SETUP_PATH"
  fi
}

__docker_envs_source_ros
__docker_envs_source_zenoh
export RCUTILS_COLORIZED_OUTPUT=1

parse_git_branch() {
  local branch remote
  branch=\$(git symbolic-ref --short HEAD 2>/dev/null)
  remote=\$(git config --get "branch.\${branch}.remote" 2>/dev/null)
  if [ -n "\$branch" ]; then
    if [ -n "\$remote" ]; then
      echo -e "\\[\\033[0;33m\\][\$remote: \\[\\033[0;31m\\]\$branch\\[\\033[0;33m\\]]"
    else
      echo -e "\\[\\033[0;33m\\][\\[\\033[0;31m\\]\$branch\\[\\033[0;33m\\]]"
    fi
  fi
}

__docker_envs_prompt() {
  local exit_code="\$?"
  local prompt="\\[\\e[0;32m\\]\\u@\\h:\\[\\e[0;34m\\]\\w\$(parse_git_branch)"
  if [ "\$exit_code" -ne 0 ]; then
    prompt="\\[\\e[0;31m\\](\$exit_code) \$prompt"
  fi
  PS1="\${VIRTUAL_ENV:+(\${VIRTUAL_ENV##*/}) }\$prompt\\[\\e[0m\\]\\$ "
}

if [ -n "\${PROMPT_COMMAND:-}" ]; then
  case ";\${PROMPT_COMMAND};" in
    *";__docker_envs_prompt;"*) ;;
    *)
      PROMPT_COMMAND="__docker_envs_prompt; \${PROMPT_COMMAND}"
      ;;
  esac
else
  PROMPT_COMMAND="__docker_envs_prompt"
fi

# Ensure color-friendly utilities.
if [ -x /usr/bin/dircolors ]; then
  if [ -r "\$HOME/.dircolors" ]; then
    eval "\$(dircolors -b "\$HOME/.dircolors")"
  else
    eval "\$(dircolors -b)"
  fi
fi

alias ls='ls --color=auto'
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias sudo='sudo '

# Enable interactive shell completions when available.
if [ -f /etc/profile.d/bash_completion.sh ]; then
  # shellcheck disable=SC1091
  source /etc/profile.d/bash_completion.sh
elif [ -f /usr/share/bash-completion/bash_completion ]; then
  # shellcheck disable=SC1091
  source /usr/share/bash-completion/bash_completion
fi

# Hook ROS 2 and colcon argcomplete integrations.
if command -v register-python-argcomplete >/dev/null 2>&1; then
  eval "\$(register-python-argcomplete ros2)"
  eval "\$(register-python-argcomplete colcon)"
elif command -v register-python-argcomplete3 >/dev/null 2>&1; then
  eval "\$(register-python-argcomplete3 ros2)"
  eval "\$(register-python-argcomplete3 colcon)"
elif [ -f /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash ]; then
  # shellcheck disable=SC1091
  source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash
fi

${BLOCK_END}
EOF

# Ensure the bashrc sources the new configuration.
if ! grep -Fxq "${SOURCE_SNIPPET}" "${BASHRC_PATH}"; then
  printf '\n%s\n' "${SOURCE_SNIPPET}" >> "${BASHRC_PATH}"
fi

echo "Updated ${CONFIG_FILE} and ensured ${BASHRC_PATH} sources it."
echo "Open a new shell or run: source ${CONFIG_FILE}"
