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
  -a <gid>          Add a supplementary numeric group (repeatable)
  -M <umask>        New-file permission mask (default: 0022; shared group: 0002)
  -d <device>       Pass a specific device to Docker (repeatable)
  -P                Enable privileged mode explicitly for hardware workloads
  -X                Do not auto-configure Isaac Sim (skip GPU + cache mounts)
  -h                Show this help

Isaac Sim images are detected automatically in run mode: the GPU, the EULA
variables and the persistent Omniverse cache directories under
~/docker/isaac-sim are wired up for you. Override the cache location with
STAGES_ISAAC_CACHE_ROOT.

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
NO_ISAAC_SETUP=false
EXTRA_RUN_ARGS=()
WORKSPACE_UMASK=0022
# Requested versions before "latest" is resolved online.
CUDA_REQUEST=""
MUJOCO_REQUEST=""
ISAACSIM_REQUEST=""
ISAACLAB_REQUEST=""

# -c, -m, -I and -L take an optional argument: `-m` alone means "latest".
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

while getopts "o:v:u:i:N:w:n:U:G:a:M:d:j:e:B:V:cmILzbsrpgPXh" opt; do
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
        z) STAGES_ZENOH=true ;;
        s) STAGES_SIMULATION=true ;;
        b) BUILD=true ;;
        r) RUN=true ;;
        p) DRY_RUN=true ;;
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

    CONTAINER="$(echo "${STAGES_FINAL_IMAGE}" | tr ':/.' '___')_container"
    TARGET_WS="/home/${STAGES_USERNAME}/colcon_ws"
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
    for host_path in /tmp/.X11-unix /etc/timezone /etc/localtime; do
        if [[ -e "${host_path}" ]]; then
            DOCKER_ARGS+=(--mount "type=bind,source=${host_path},target=${host_path},readonly")
        fi
    done
    # Use the existing X11 cookie without changing the host X server ACL.
    AUTHORITY="${XAUTHORITY:-${HOME}/.Xauthority}"
    if [[ -f "${AUTHORITY}" ]]; then
        DOCKER_ARGS+=(--mount "type=bind,source=${AUTHORITY},target=/tmp/docker-envs.Xauthority,readonly"
                      -e XAUTHORITY=/tmp/docker-envs.Xauthority)
    fi
    # An Isaac Sim image needs the GPU and the persistent Omniverse caches, or it
    # recompiles every shader on each start. Detected from the image so this does
    # not depend on remembering a flag; it already includes --gpus all.
    ISAAC_CONFIGURED=false
    if [[ "${NO_ISAAC_SETUP}" != true ]] && stages::image_has_isaacsim "${STAGES_FINAL_IMAGE}"; then
        stages::info "Isaac Sim image detected; mounting Omniverse caches from ${STAGES_ISAAC_CACHE_ROOT}"
        stages::isaac_run_args "${STAGES_FINAL_IMAGE}" "/home/${STAGES_USERNAME}" || exit 1
        DOCKER_ARGS+=("${STAGES_ISAAC_ARGS[@]}")
        ISAAC_CONFIGURED=true
    fi

    # Only add --gpus once: isaac_run_args already did when it ran.
    if [[ "${USE_GPU}" == true && "${ISAAC_CONFIGURED}" == false ]]; then
        DOCKER_ARGS+=(--gpus all)
    fi

    docker run "${DOCKER_ARGS[@]}" -it "${STAGES_FINAL_IMAGE}" bash
fi
