#!/usr/bin/env bash
# Flag-driven build/run front end for the local creator images.
#
# For an interactive walk-through of the same stages, use ./create_env.sh.

set -uo pipefail

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source=lib/stages.sh
source "${ROOT}/lib/stages.sh"

ON_EXIT=()
function cleanup() {
    for command in "${ON_EXIT[@]:-}"; do
        $command &>/dev/null || true
    done
}
trap cleanup EXIT

function help() {
    cat <<'EOF'
Usage: run_env.sh -b|-r [options]

Modes:
  -b                Build the image stack
  -r                Run a container from the final image
  -p                Print the build plan and exit (dry run)

Stages:
  -o <os>           Ubuntu version: 22.04 | 24.04 | 26.04            (default: 24.04)
  -v <ros>          ROS distro: rolling|kilted|jazzy|humble|iron|lyrical
                                                                     (default: rolling)
  -c [<version>]    CUDA + cuDNN devel base; "latest" or e.g. 13.3.1 (default: latest)
  -u <usage>        manipulation | navigation | both | skip          (default: skip)
  -m [<version>]    MuJoCo layer; "latest" or e.g. 3.12.0            (default: latest)
  -I [<version>]    Isaac Sim layer; "latest" or e.g. 6.0.1.0        (default: latest)
  -L [<version>]    Isaac Lab layer; "latest" or e.g. v2.3.2         (default: latest)
                    Requires -I.
  -z                Add the Zenoh RMW layer
  -s                Add the Gazebo simulation layer

Image / user:
  -i <image>        Final image name. Omitted => derived from the selected
                    stages, e.g. docker_envs:24.04-jazzy-mujoco3.12.0-moveit
  -N <namespace>    Image namespace for derived names                (default: docker_envs)
  -n <username>     User created inside the image                    (default: admin)
  -U <uid>          UID for that user                                (default: current host UID)
  -G <gid>          GID for that user                                (default: current host GID)

Run mode:
  -w <path>         Workspace to bind-mount (required with -r)
  -g                Pass --gpus all to docker run
  -h                Show this help

Examples:
  ./run_env.sh -b -o 24.04 -v jazzy -u manipulation -m latest
  ./run_env.sh -b -o 22.04 -v humble -c 13.3.1 -I latest -L latest
  ./run_env.sh -r -i docker_envs:24.04-jazzy-moveit -w ~/colcon_ws
EOF
    exit 1
}

stages::init_selection

BUILD=false
RUN=false
DRY_RUN=false
WORKSPACE=""
USE_GPU=false
# Requested versions before "latest" is resolved online.
CUDA_REQUEST=""
MUJOCO_REQUEST=""
ISAACSIM_REQUEST=""
ISAACLAB_REQUEST=""

# -c, -m, -I and -L take an optional argument: `-m` alone means "latest".
# getopts cannot express that, so grab the next word only when it does not look
# like another flag.
function optional_arg() {
    local next="${!OPTIND:-}"
    if [[ -n "${next}" && "${next}" != -* ]]; then
        echo "${next}"
        OPTIND=$((OPTIND + 1))
    else
        echo "latest"
    fi
}

while getopts "o:v:u:i:N:w:n:U:G:cmILzbsrpgh" opt; do
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
        c) STAGES_USE_CUDA=true;  CUDA_REQUEST="$(optional_arg)" ;;
        m) STAGES_MUJOCO=true;    MUJOCO_REQUEST="$(optional_arg)" ;;
        I) STAGES_ISAACSIM=true;  ISAACSIM_REQUEST="$(optional_arg)" ;;
        L) STAGES_ISAACLAB=true;  ISAACLAB_REQUEST="$(optional_arg)" ;;
        z) STAGES_ZENOH=true ;;
        s) STAGES_SIMULATION=true ;;
        b) BUILD=true ;;
        r) RUN=true ;;
        p) DRY_RUN=true ;;
        g) USE_GPU=true ;;
        h | ?) help ;;
    esac
done

if [[ "${DRY_RUN}" == true ]]; then
    BUILD=true
fi

if [[ "${BUILD}" == false && "${RUN}" == false ]] || [[ "${BUILD}" == true && "${RUN}" == true ]]; then
    stages::error "Specify exactly one of build (-b), run (-r) or dry run (-p)."
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
# Run
# --------------------------------------------------------------------------- #
if [[ "${RUN}" == true ]]; then
    if [[ -z "${WORKSPACE}" ]]; then
        stages::error "Workspace path (-w) is required in run mode."
        help
    fi
    if [[ -z "${STAGES_FINAL_IMAGE}" ]]; then
        stages::error "Image name (-i) is required in run mode."
        help
    fi

    CONTAINER="$(echo "${STAGES_FINAL_IMAGE}" | tr ':/.' '___')_container"
    TARGET_WS="/home/${STAGES_USERNAME}/colcon_ws"
    DOCKER_ARGS=(
        -e "DISPLAY=${DISPLAY:-}"
        -v /tmp/.X11-unix:/tmp/.X11-unix:ro
        -v /etc/timezone:/etc/timezone:ro
        -v /etc/localtime:/etc/localtime:ro
        -v "${WORKSPACE}:${TARGET_WS}:rw"
        --user "${STAGES_USER_UID}:${STAGES_USER_GID}"
        --privileged
        --name "${CONTAINER}"
        --rm
    )
    # Only bind-mount .Xauthority when it exists; docker would otherwise create a
    # directory at that path and X11 auth would silently fail.
    if [[ -f "${HOME}/.Xauthority" ]]; then
        DOCKER_ARGS+=(-v "${HOME}/.Xauthority:/home/${STAGES_USERNAME}/.Xauthority:rw")
    fi
    if [[ "${USE_GPU}" == true ]]; then
        DOCKER_ARGS+=(--gpus all)
    fi

    if command -v xhost &>/dev/null; then
        xhost +local: >/dev/null
        ON_EXIT+=("xhost -local:")
    else
        stages::warn "xhost not found; GUI applications may not work."
    fi

    docker run "${DOCKER_ARGS[@]}" -it "${STAGES_FINAL_IMAGE}" bash
fi
