#!/usr/bin/env bash
# Flag-driven build/run front end for the local creator images.
#
# For an interactive walk-through of the same stages, use ./create_env.sh.

set -uo pipefail

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source=lib/stages.sh
source "${ROOT}/lib/stages.sh"

function help() {
    cat <<'EOF'
Usage: run_env.sh -b|-p|-r|-S|-E|-K [options]

Modes (exactly one):
  -b                Build the image stack
  -p                Print the build plan and exit (dry run)
  -r                Run a one-off interactive container (removed on exit)
  -S                Start a persistent container in the background
  -E                Enter the running container with a new shell
  -K                Stop the running container (it is removed)

Stages:
  -o <os>           Ubuntu version: 22.04 | 24.04 | 26.04            (default: 24.04)
  -v <ros>          ROS distro: rolling|kilted|jazzy|humble|iron|lyrical
                                                                     (default: rolling)
  -c [<version>]    CUDA + cuDNN devel base; "latest" or e.g. 13.3.1 (default: latest)
  -u <usage>        manipulation | navigation | both | skip          (default: skip)
  -m [<version>]    MuJoCo layer; "latest" or e.g. 3.12.0            (default: latest)
  -I [<version>]    Isaac Sim layer; "latest" or e.g. 6.1.0.0        (default: latest)
  -L [<version>]    Isaac Lab layer; "latest", a tag (v2.3.2) or a branch
                    (main, release/3.0.0)                            (default: latest)
  -j <method>       Isaac Lab: auto | python-env (with -I) | legacy (Kit-less)
  -e <selectors>    Isaac Lab packages: default | core | 'newton,rl[rsl-rl]'
                    default invokes upstream -i without a selector.
  -B <physics>     Lab physics support: default | newton | ovphysx | both |
                    isaacsim | all (isaacsim/all require -I)
  -V <visualizer>  Lab visualization: default | newton | rerun | viser | kit | all
                    kit requires -I; all adds Newton, Rerun and Viser.
                    -B/-V add to -e; use -e core for only the selected extras.
  -R [<ref>]        cuRobo layer (Python 3.12); branch or tag        (default: main)
  -z                Add the Zenoh RMW layer
  -s                Add the Gazebo simulation layer

Image / user:
  -i <image>        Final image name. Omitted => derived from the selected
                    stages, e.g. docker_envs:24.04-jazzy-mujoco3.12.0-moveit
  -N <namespace>    Image namespace for derived names                (default: docker_envs)
  -n <username>     User created inside the image                    (default: admin)
  -U <uid>          UID for that user                                (default: current host UID)
  -G <gid>          GID for that user                                (default: current host GID)

Container (-r, -S, -E, -K):
  -w <path>         Workspace to bind-mount (required with -r and -S)
  -C <name>         Container name (default: derived from the image name)
  -H                Host network and IPC (ROS 2 discovery, shared memory)
  -g                Pass --gpus all to docker run
  -a <gid>          Add a supplementary numeric group (repeatable)
  -M <umask>        New-file permission mask (default: 0022; shared group: 0002)
  -d <device>       Pass a specific device to Docker (repeatable)
  -P                Enable privileged mode explicitly for hardware workloads
  -X                Do not auto-configure Isaac (skip GPU, cache and output mounts)
  -h                Show this help

Every image has one Python environment, /opt/venv: active by default,
owned by the container user, and visible to ROS 2 (system Python) when its
Python matches the distribution's.

Isaac images are detected automatically in -r/-S mode:
  - Isaac Sim: GPU, EULA variables, Omniverse caches under ~/docker/isaac-sim
    (override with STAGES_ISAAC_CACHE_ROOT)
  - Isaac Lab: logs/ and data_storage/ under ~/docker/isaac-lab
    (override with STAGES_ISAACLAB_OUTPUT_ROOT)

Examples:
  ./run_env.sh -b -o 24.04 -v jazzy -u manipulation -m latest
  ./run_env.sh -b -o 24.04 -v jazzy -I 6.1.0.0 -L release/3.0.0
  ./run_env.sh -b -o 24.04 -v jazzy -c -u manipulation -R
  ./run_env.sh -r -i docker_envs:24.04-jazzy-moveit -w ~/colcon_ws
  ./run_env.sh -S -H -i docker_envs:24.04-jazzy-moveit -w ~/colcon_ws
  ./run_env.sh -E -i docker_envs:24.04-jazzy-moveit
  ./run_env.sh -K -i docker_envs:24.04-jazzy-moveit
EOF
    exit 1
}

stages::init_selection

BUILD=false
RUN=false
DRY_RUN=false
START=false
ENTER=false
STOP=false
WORKSPACE=""
CONTAINER=""
HOST_NETWORK=false
USE_GPU=false
NO_ISAAC_SETUP=false
EXTRA_RUN_ARGS=()
WORKSPACE_UMASK=0022
ENTRYPOINT=/usr/local/bin/scripts/workspace-entrypoint.sh
# Requested versions before "latest" is resolved online.
CUDA_REQUEST=""
MUJOCO_REQUEST=""
ISAACSIM_REQUEST=""
ISAACLAB_REQUEST=""
CUROBO_REQUEST=""

# -c, -m, -I, -L and -R take an optional argument: `-m` alone means "latest".
# getopts cannot express that, so grab the next word only when it does not look
# like another flag.
#
# The result goes in OPT_VALUE rather than on stdout: a command substitution
# would run this in a subshell, where the OPTIND increment is discarded. getopts
# would then re-read the value as a non-option and stop parsing, silently
# dropping every remaining flag.
# getopts indexes into the script's "$@", but inside a function ${!OPTIND}
# resolves against the *function's* parameters -- which are empty -- so the
# script's argument list has to be captured up front.
SCRIPT_ARGV=("$@")
OPT_VALUE=""
function optional_arg() {
    # OPTIND is 1-based and already points past the flag; SCRIPT_ARGV is 0-based.
    local next="${SCRIPT_ARGV[OPTIND-1]:-}"
    if [[ -n "${next}" && "${next}" != -* ]]; then
        OPT_VALUE="${next}"
        OPTIND=$((OPTIND + 1))
    else
        OPT_VALUE="latest"
    fi
}

while getopts "o:v:u:i:N:w:n:U:G:a:M:d:j:e:B:V:C:cmILRzbsrpgPXSEKHh" opt; do
    case ${opt} in
        o) STAGES_OS="${OPTARG}" ;;
        v) STAGES_ROS="${OPTARG}" ;;
        u) STAGES_USAGE="${OPTARG}" ;;
        i) STAGES_FINAL_IMAGE="${OPTARG}" ;;
        N) STAGES_NAMESPACE="${OPTARG}" ;;
        w) WORKSPACE="${OPTARG}" ;;
        n) STAGES_USERNAME="${OPTARG}" ;;
        U) STAGES_USER_UID="${OPTARG}" ;;
        G) STAGES_USER_GID="${OPTARG}" ;;
        c) STAGES_USE_CUDA=true;  optional_arg; CUDA_REQUEST="${OPT_VALUE}" ;;
        m) STAGES_MUJOCO=true;    optional_arg; MUJOCO_REQUEST="${OPT_VALUE}" ;;
        I) STAGES_ISAACSIM=true;  optional_arg; ISAACSIM_REQUEST="${OPT_VALUE}" ;;
        B) STAGES_ISAACLAB_PHYSICS="${OPTARG}" ;;
        V) STAGES_ISAACLAB_VISUALIZER="${OPTARG}" ;;
        j) STAGES_ISAACLAB_METHOD="${OPTARG}" ;;
        e) STAGES_ISAACLAB_INSTALL="${OPTARG}" ;;
        L) STAGES_ISAACLAB=true;  optional_arg; ISAACLAB_REQUEST="${OPT_VALUE}" ;;
        R) STAGES_CUROBO=true;    optional_arg; CUROBO_REQUEST="${OPT_VALUE}" ;;
        z) STAGES_ZENOH=true ;;
        s) STAGES_SIMULATION=true ;;
        b) BUILD=true ;;
        r) RUN=true ;;
        p) DRY_RUN=true ;;
        S) START=true ;;
        E) ENTER=true ;;
        K) STOP=true ;;
        C) CONTAINER="${OPTARG}" ;;
        H) HOST_NETWORK=true ;;
        g) USE_GPU=true ;;
        a)
            [[ "${OPTARG}" =~ ^[0-9]+$ ]] || { stages::error "Supplementary GID must be numeric"; exit 1; }
            EXTRA_RUN_ARGS+=(--group-add "${OPTARG}") ;;
        M) WORKSPACE_UMASK="${OPTARG}" ;;
        d) EXTRA_RUN_ARGS+=(--device "${OPTARG}") ;;
        P) EXTRA_RUN_ARGS+=(--privileged) ;;
        X) NO_ISAAC_SETUP=true ;;
        h | ?) help ;;
    esac
done

if [[ "${DRY_RUN}" == true ]]; then
    BUILD=true
fi

MODES=0
for mode in "${BUILD}" "${RUN}" "${START}" "${ENTER}" "${STOP}"; do
    [[ "${mode}" == true ]] && MODES=$((MODES + 1))
done
if (( MODES != 1 )); then
    stages::error "Specify exactly one mode: -b, -p, -r, -S, -E or -K."
    help
fi

# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
if [[ "${BUILD}" == true ]]; then
    if ! stages::validate_selection; then
        exit 1
    fi

    if [[ "${STAGES_USE_CUDA}" == true ]]; then
        STAGES_CUDA_VERSION="$(stages::resolve_version cuda "${CUDA_REQUEST}" "${STAGES_OS}")"
    fi
    if [[ "${STAGES_MUJOCO}" == true ]]; then
        STAGES_MUJOCO_VERSION="$(stages::resolve_version mujoco "${MUJOCO_REQUEST}")"
    fi
    if [[ "${STAGES_ISAACSIM}" == true ]]; then
        STAGES_ISAACSIM_VERSION="$(stages::resolve_version isaacsim "${ISAACSIM_REQUEST}")"
    fi
    if [[ "${STAGES_ISAACLAB}" == true ]]; then
        STAGES_ISAACLAB_VERSION="$(stages::resolve_version isaaclab "${ISAACLAB_REQUEST}")"
    fi

    if [[ "${STAGES_CUROBO}" == true ]]; then
        # cuRobo is built from a branch or tag; "latest" means its main line.
        [[ "${CUROBO_REQUEST}" == latest ]] && CUROBO_REQUEST="${STAGES_DEFAULT_CUROBO}"
        STAGES_CUROBO_VERSION="${CUROBO_REQUEST:-${STAGES_DEFAULT_CUROBO}}"
    fi

    if ! stages::build_plan; then
        exit 1
    fi
    stages::print_plan

    if [[ "${DRY_RUN}" == true ]]; then
        stages::info "Dry run: nothing was built."
        exit 0
    fi

    stages::run_plan
    exit $?
fi

# --------------------------------------------------------------------------- #
# Container modes: -r, -S, -E, -K
# --------------------------------------------------------------------------- #
if [[ -z "${STAGES_FINAL_IMAGE}" ]]; then
    stages::error "Image name (-i) is required to run, start, enter or stop a container."
    help
fi
CUSTOM_CONTAINER=false
[[ -n "${CONTAINER}" ]] && CUSTOM_CONTAINER=true
if [[ -z "${CONTAINER}" ]]; then
    CONTAINER="$(echo "${STAGES_FINAL_IMAGE}" | tr ':/.' '___')_container"
elif [[ ! "${CONTAINER}" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]; then
    stages::error "Invalid container name: ${CONTAINER}"
    exit 1
fi
TARGET_WS="/home/${STAGES_USERNAME}/colcon_ws"

container_running() {
    [[ "$(docker container inspect -f '{{.State.Status}}' "${CONTAINER}" 2>/dev/null)" == running ]]
}

# X11: copy the current display cookie with the FamilyWild address (ffff) into a
# per-user directory. A wildcard cookie also matches when the container hostname
# differs from the host's (bridge network). The directory, not the file, is
# mounted, so -E can refresh the cookie for a running container (a replaced
# file would keep the old inode in a single-file mount). The X server's access
# control is not modified. Same approach as IsaacLab's docker/utils/x11_utils.py.
XAUTH_DIR="${XDG_RUNTIME_DIR:-/tmp}/docker-envs-xauth-$(id -u)"
XAUTH_TARGET_DIR=/tmp/docker-envs-xauth
x11_cookie() {
    [[ -n "${DISPLAY:-}" ]] && command -v xauth >/dev/null 2>&1 || return 1
    local cookies
    cookies="$(xauth nlist "${DISPLAY}" 2>/dev/null)" || return 1
    [[ -n "${cookies}" ]] || return 1
    (umask 077 && mkdir -p "${XAUTH_DIR}") || return 1
    rm -f "${XAUTH_DIR}/xauth.new"
    sed -e 's/^..../ffff/' <<<"${cookies}" \
        | xauth -q -f "${XAUTH_DIR}/xauth.new" nmerge - 2>/dev/null || return 1
    mv -f "${XAUTH_DIR}/xauth.new" "${XAUTH_DIR}/xauth"
}

validate_run_inputs() {
    if [[ -z "${WORKSPACE}" ]]; then
        stages::error "Workspace path (-w) is required to run or start a container."
        help
    fi
    if [[ ! "${STAGES_USER_UID}" =~ ^[0-9]+$ || ! "${STAGES_USER_GID}" =~ ^[0-9]+$ ]]; then
        stages::error "UID and GID must be numeric."
        exit 1
    fi
    if [[ ! "${WORKSPACE_UMASK}" =~ ^[0-7]{3,4}$ ]]; then
        stages::error "Umask must contain three or four octal digits."
        exit 1
    fi
    if [[ ! -d "${WORKSPACE}" ]]; then
        stages::error "Workspace does not exist: ${WORKSPACE}. Create it as your host user first."
        exit 1
    fi
    WORKSPACE="$(cd -- "${WORKSPACE}" && pwd -P)" || exit 1
    if [[ "${WORKSPACE}" == *,* ]]; then
        stages::error "Workspace paths containing commas are not supported by this launcher."
        exit 1
    fi
}

# Fill DOCKER_ARGS for `docker run`, shared by -r and -S.
build_run_args() {
    DOCKER_ARGS=(
        -e "DISPLAY=${DISPLAY:-}"
        -e "HOME=/home/${STAGES_USERNAME}"
        -e "WORKSPACE_UMASK=${WORKSPACE_UMASK}"
        --mount "type=bind,source=${WORKSPACE},target=${TARGET_WS}"
        --workdir "${TARGET_WS}"
        --user "${STAGES_USER_UID}:${STAGES_USER_GID}"
        --name "${CONTAINER}"
        --rm
        "${EXTRA_RUN_ARGS[@]}"
    )
    local host_path
    for host_path in /tmp/.X11-unix /etc/timezone /etc/localtime; do
        if [[ -e "${host_path}" ]]; then
            DOCKER_ARGS+=(--mount "type=bind,source=${host_path},target=${host_path},readonly")
        fi
    done
    if x11_cookie; then
        DOCKER_ARGS+=(--mount "type=bind,source=${XAUTH_DIR},target=${XAUTH_TARGET_DIR},readonly"
                      -e "XAUTHORITY=${XAUTH_TARGET_DIR}/xauth")
    else
        # Fall back to the existing cookie file (no display or no xauth tool).
        local authority="${XAUTHORITY:-${HOME}/.Xauthority}"
        if [[ -f "${authority}" ]]; then
            DOCKER_ARGS+=(--mount "type=bind,source=${authority},target=/tmp/docker-envs.Xauthority,readonly"
                          -e XAUTHORITY=/tmp/docker-envs.Xauthority)
        fi
    fi
    if [[ "${HOST_NETWORK}" == true ]]; then
        DOCKER_ARGS+=(--network host --ipc host)
    fi
    # An Isaac Sim image needs the GPU and the persistent Omniverse caches, or it
    # recompiles every shader on each start. Detected from the image so this does
    # not depend on remembering a flag; it already includes --gpus all.
    local isaac_configured=false
    if [[ "${NO_ISAAC_SETUP}" != true ]]; then
        if stages::image_has_isaacsim "${STAGES_FINAL_IMAGE}"; then
            stages::info "Isaac Sim image detected; mounting Omniverse caches from ${STAGES_ISAAC_CACHE_ROOT}"
            stages::isaac_run_args "${STAGES_FINAL_IMAGE}" "/home/${STAGES_USERNAME}" || return 1
            DOCKER_ARGS+=("${STAGES_ISAAC_ARGS[@]}")
            isaac_configured=true
        fi
        if stages::image_has_isaaclab "${STAGES_FINAL_IMAGE}"; then
            stages::info "Isaac Lab image detected; persisting logs/ and data_storage/ under ${STAGES_ISAACLAB_OUTPUT_ROOT}"
            stages::isaaclab_output_args "${STAGES_FINAL_IMAGE}" || return 1
            DOCKER_ARGS+=("${STAGES_ISAACLAB_ARGS[@]}")
        fi
    fi
    # Only add --gpus once: isaac_run_args already did when it ran.
    if [[ "${USE_GPU}" == true && "${isaac_configured}" == false ]]; then
        DOCKER_ARGS+=(--gpus all)
    fi
}

if [[ "${RUN}" == true ]]; then
    validate_run_inputs
    build_run_args || exit 1
    docker run "${DOCKER_ARGS[@]}" -it "${STAGES_FINAL_IMAGE}" bash
    exit $?
fi

if [[ "${START}" == true ]]; then
    validate_run_inputs
    if container_running; then
        stages::info "Container ${CONTAINER} is already running; enter it with -E."
        exit 0
    fi
    build_run_args || exit 1
    # --init reaps processes and forwards signals, so -K stops at once.
    docker run -d --init "${DOCKER_ARGS[@]}" "${STAGES_FINAL_IMAGE}" sleep infinity >/dev/null || exit $?
    ENTER_CMD=("$0" -E -i "${STAGES_FINAL_IMAGE}" -n "${STAGES_USERNAME}")
    [[ "${CUSTOM_CONTAINER}" == true ]] && ENTER_CMD+=(-C "${CONTAINER}")
    stages::info "Started ${CONTAINER}. Open a shell with:"
    printf '    %s\n' "${ENTER_CMD[*]}"
    exit 0
fi

if [[ "${ENTER}" == true ]]; then
    if ! container_running; then
        stages::error "Container ${CONTAINER} is not running. Start it with -S."
        exit 1
    fi
    # Refresh the cookie in the mounted directory for the current display.
    x11_cookie || true
    # The entrypoint applies WORKSPACE_UMASK and loads ROS for this shell too.
    docker exec -it -e "DISPLAY=${DISPLAY:-}" --workdir "${TARGET_WS}" \
        "${CONTAINER}" "${ENTRYPOINT}" bash
    exit $?
fi

if [[ "${STOP}" == true ]]; then
    if ! container_running; then
        stages::info "Container ${CONTAINER} is not running."
        exit 0
    fi
    docker stop "${CONTAINER}" >/dev/null || exit $?
    stages::info "Stopped and removed ${CONTAINER}."
fi
