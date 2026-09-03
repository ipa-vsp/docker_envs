#!/usr/bin/env bash
# Shared stage definitions, online version discovery and image naming for the
# local (non-CI) creator builds.
#
# Sourced by run_env.sh (flag driven) and create_env.sh (interactive) so both
# front-ends produce identically named images from identical layers.

STAGES_LIB_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
SCRIPTS_DIR="$( cd "${STAGES_LIB_DIR}/.." >/dev/null 2>&1 && pwd )"
CREATOR_DIR="$( cd "${SCRIPTS_DIR}/.." >/dev/null 2>&1 && pwd )"

# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
stages::info()    { echo -e "\033[32mINFO:\033[0m $*"; }
stages::warn()    { echo -e "\033[33mWARN:\033[0m $*" >&2; }
stages::error()   { echo -e "\033[31mERROR:\033[0m $*" >&2; }
stages::heading() { echo -e "\n\033[1;36m== $* ==\033[0m"; }

# --------------------------------------------------------------------------- #
# Supported combinations
#
# CI_COMBOS lists what .github/workflows/ros2-staged.yml actually builds. Other
# combinations are still allowed locally (the Dockerfiles are generic) but the
# scripts warn that upstream may not publish packages for them.
# --------------------------------------------------------------------------- #
STAGES_SUPPORTED_OS=("22.04" "24.04" "26.04")

STAGES_CI_COMBOS=(
    "24.04:rolling" "24.04:kilted" "24.04:jazzy"
    "22.04:humble"
    "26.04:lyrical"
)

# ROS distros offered per Ubuntu release.
stages::ros_for_os() {
    case "$1" in
        22.04) echo "humble iron" ;;
        24.04) echo "rolling kilted jazzy" ;;
        26.04) echo "lyrical rolling" ;;
        *)     echo "" ;;
    esac
}

stages::is_ci_combo() {
    local want="$1:$2" combo
    for combo in "${STAGES_CI_COMBOS[@]}"; do
        [[ "${combo}" == "${want}" ]] && return 0
    done
    return 1
}

# MoveIt and Nav2 are not released for every distro yet (notably lyrical).
stages::has_usage_layers() {
    case "$1" in
        rolling|jazzy|kilted|iron|humble) return 0 ;;
        *) return 1 ;;
    esac
}

# Combinations upstream has moved on from. They still build (CI covers
# 24.04-rolling), but the packages are frozen, so say so once rather than
# leaving it to be discovered from a runtime banner.
stages::deprecation_note() {
    if [[ "$1" == "24.04" && "$2" == "rolling" ]]; then
        echo "ROS Rolling has migrated to Ubuntu 26.04; 24.04 no longer receives updated Rolling packages."
    fi
}

# --------------------------------------------------------------------------- #
# Online version discovery
#
# Every lookup is best effort: on a failure the caller falls back to the
# documented defaults so a build still works without network access.
# --------------------------------------------------------------------------- #
STAGES_CURL=(curl -fsSL --max-time 20 --retry 3 --retry-delay 2 --retry-connrefused)

# Newest -> oldest MuJoCo releases. git ls-remote avoids the GitHub API rate
# limit that an unauthenticated /releases call runs into.
stages::mujoco_versions() {
    local limit="${1:-8}"
    git ls-remote --tags --refs https://github.com/google-deepmind/mujoco.git 2>/dev/null \
        | awk -F'refs/tags/' '{print $2}' \
        | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' \
        | sort -uV | tail -n "${limit}" | tac
}

# Newest -> oldest Isaac Sim wheels published on the NVIDIA package index.
stages::isaacsim_versions() {
    local limit="${1:-8}"
    "${STAGES_CURL[@]}" https://pypi.nvidia.com/isaacsim/ 2>/dev/null \
        | grep -oE 'isaacsim-[0-9]+(\.[0-9]+)+' \
        | sed 's/^isaacsim-//' \
        | sort -uV | tail -n "${limit}" | tac
}

# Newest -> oldest Isaac Lab tags. Pre-release tags (v3.0.0-beta) are kept:
# they are frequently the only build compatible with a new Isaac Sim.
stages::isaaclab_versions() {
    local limit="${1:-8}"
    git ls-remote --tags --refs https://github.com/isaac-sim/IsaacLab.git 2>/dev/null \
        | awk -F'refs/tags/' '{print $2}' \
        | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' \
        | sort -uV | tail -n "${limit}" | tac
}

# Newest -> oldest CUDA versions that publish a cudnn-devel image for this
# Ubuntu release.
stages::cuda_versions() {
    local os="$1" limit="${2:-8}"
    "${STAGES_CURL[@]}" \
        "https://hub.docker.com/v2/repositories/nvidia/cuda/tags?page_size=100&name=cudnn-devel-ubuntu${os}" 2>/dev/null \
        | grep -oE "[0-9]+\.[0-9]+\.[0-9]+-cudnn-devel-ubuntu${os//./\\.}" \
        | sed "s/-cudnn-devel-ubuntu${os}\$//" \
        | sort -uV | tail -n "${limit}" | tac
}

# Fallbacks used when a lookup returns nothing (offline, API change, ...).
STAGES_DEFAULT_CUDA="13.3.1"
STAGES_DEFAULT_MUJOCO="3.12.0"
STAGES_DEFAULT_GYM="1.3.0"
STAGES_DEFAULT_ISAACSIM="6.0.1.0"
STAGES_DEFAULT_ISAACLAB="v2.3.2"
STAGES_DEFAULT_TORCH="2.11.0"
# NOT a "latest" candidate: isaacsim-core pins mujoco-usd-converter to an exact
# version (6.0.1.0 requires ==0.2.0), so installing a newer one makes the Isaac
# Sim resolve fail outright. Bump this only in lockstep with ISAACSIM_VERSION.
STAGES_DEFAULT_USD_CONVERTER="0.2.0"

# stages::resolve_version <kind> <requested> [os]
# Turns "latest" (or an empty value) into the newest version discovered online,
# falling back to the documented default when the lookup fails. Any other value
# is passed through untouched so an exact version can always be pinned.
stages::resolve_version() {
    local kind="$1" requested="${2:-latest}" os="${3:-}" found=""
    if [[ -n "${requested}" && "${requested}" != "latest" ]]; then
        echo "${requested}"
        return 0
    fi
    case "${kind}" in
        mujoco)   found="$(stages::mujoco_versions 1)" ;;
        isaacsim) found="$(stages::isaacsim_versions 1)" ;;
        isaaclab) found="$(stages::isaaclab_versions 1)" ;;
        cuda)     found="$(stages::cuda_versions "${os}" 1)" ;;
    esac
    if [[ -n "${found}" ]]; then
        echo "${found}"
        return 0
    fi
    stages::warn "Could not look up the latest ${kind} version; using the built-in default." >&2
    case "${kind}" in
        mujoco)   echo "${STAGES_DEFAULT_MUJOCO}" ;;
        isaacsim) echo "${STAGES_DEFAULT_ISAACSIM}" ;;
        isaaclab) echo "${STAGES_DEFAULT_ISAACLAB}" ;;
        cuda)     echo "${STAGES_DEFAULT_CUDA}" ;;
    esac
}

# Isaac Sim wheels pin an exact CPython; uv provides it inside the image.
stages::isaacsim_python() {
    case "${1%%.*}" in
        6) echo "3.12" ;;
        5) echo "3.11" ;;
        4) echo "3.10" ;;
        *) echo "3.11" ;;
    esac
}

# Published PyTorch CUDA wheel indexes, newest first.
#
# PyTorch does NOT publish one index per CUDA release: there is no cu133 for
# CUDA 13.3.1, so deriving the name arithmetically from the CUDA version yields
# a 403 and the whole layer fails. The list has to be read from the server.
stages::torch_indexes() {
    "${STAGES_CURL[@]}" https://download.pytorch.org/whl/ 2>/dev/null \
        | grep -oE 'cu[0-9]{3}' | sort -uV | tac
}

# Does <index> publish <torch_version>?
#   0 = yes
#   1 = fetched successfully, not there
#   2 = could not fetch (offline, rate limited, ...)
# The third case must not be confused with the second: treating a failed fetch
# as "not there" is how a transient blip silently picks the wrong index and
# wastes a multi-GB build.
stages::torch_index_has() {
    local body
    if ! body="$("${STAGES_CURL[@]}" "https://download.pytorch.org/whl/$1/torch/" 2>/dev/null)"; then
        return 2
    fi
    [[ -z "${body}" ]] && return 2
    grep -qF -- "torch-$2" <<<"${body}"
}

# stages::torch_index_url <cuda_version> [torch_version]
#
# Picks the newest published index that is not ahead of the selected CUDA and
# actually carries the requested torch build. Both halves matter: cu132 exists
# for CUDA 13.3 but only ships torch >= 2.12, while the torch 2.11.0 that the
# Isaac Sim wheels pin lives in cu130.
stages::torch_index_url() {
    local cuda="$1" torch="${2:-}"
    local major="${cuda%%.*}"
    local minor="${cuda#*.}"; minor="${minor%%.*}"
    local want=$(( major * 10 + minor ))

    local -a candidates=()
    local idx n
    while read -r idx; do
        [[ -z "${idx}" ]] && continue
        n="${idx#cu}"
        # Same CUDA major, and not newer than the CUDA we are building against.
        if (( n / 10 == major && n <= want )); then
            candidates+=("${idx}")
        fi
    done < <(stages::torch_indexes)

    local probe_failed=false rc
    for idx in "${candidates[@]}"; do
        if [[ -z "${torch}" ]]; then
            echo "https://download.pytorch.org/whl/${idx}"
            return 0
        fi
        stages::torch_index_has "${idx}" "${torch}"; rc=$?
        case ${rc} in
            0) echo "https://download.pytorch.org/whl/${idx}"; return 0 ;;
            2) probe_failed=true ;;
        esac
    done

    # Known-good index per CUDA series, used whenever the online check could not
    # give a definite answer. Guessing the newest candidate instead would pick an
    # index that does not carry the pinned torch and fail the layer minutes in.
    local fallback
    case "${major}" in
        13) fallback="cu130" ;;
        12) fallback="cu128" ;;
        11) fallback="cu118" ;;
        *)  fallback="cu130" ;;
    esac

    if [[ "${probe_failed}" == true || ${#candidates[@]} -eq 0 ]]; then
        stages::warn "Could not confirm which PyTorch index carries torch ${torch}; using the known-good ${fallback} for CUDA ${major}.x." >&2
    else
        stages::warn "No PyTorch index for CUDA ${cuda} publishes torch ${torch}; falling back to ${fallback}." >&2
        stages::warn "If that is wrong, pin the index by editing STAGES_DEFAULT_TORCH in lib/stages.sh." >&2
    fi
    echo "https://download.pytorch.org/whl/${fallback}"
}

# stages::isaaclab_install_arg <version> <framework>
#
# Isaac Lab 3.x replaced the isaaclab.sh installer with a Python CLI and changed
# the --install vocabulary: "none" is gone (the equivalent is "core") and the RL
# frameworks moved behind an rl[...] selector with hyphenated names. Passing a
# 2.x token to a 3.x checkout fails the layer, so translate here.
stages::isaaclab_install_arg() {
    local version="${1#v}" framework="$2"
    local major="${version%%.*}"

    if (( major < 3 )); then
        echo "${framework}"
        return 0
    fi

    case "${framework}" in
        none)     echo "core" ;;
        all)      echo "all" ;;
        rsl_rl)   echo "rl[rsl-rl]" ;;
        rl_games) echo "rl[rl-games]" ;;
        sb3)      echo "rl[sb3]" ;;
        skrl)     echo "rl[skrl]" ;;
        *)        echo "${framework}" ;;
    esac
}

# --------------------------------------------------------------------------- #
# Image naming
#
# Mirrors the CI scheme from ros2-staged.yml: intermediate layers land in
# <namespace>/<layer>:<tag> and the final user image in <namespace>:<tag>, where
# the tag accumulates one component per selected stage. Versions are baked into
# the tag for the layers whose version the user chooses, so two local builds
# that differ only in MuJoCo version do not overwrite each other.
# --------------------------------------------------------------------------- #
STAGES_NAMESPACE="${STAGES_NAMESPACE:-docker_envs}"

# stages::tag_add <component>  — append one component to the running tag.
stages::tag_reset() { STAGES_TAG_PARTS=(); }
stages::tag_add()   { STAGES_TAG_PARTS+=("$1"); }
stages::tag()       { local IFS='-'; echo "${STAGES_TAG_PARTS[*]}"; }

# stages::layer_image <layer> — intermediate image name for the current tag.
stages::layer_image() { echo "${STAGES_NAMESPACE}/$1:$(stages::tag)"; }

# stages::final_image — final user image name for the current tag.
stages::final_image() { echo "${STAGES_NAMESPACE}:$(stages::tag)"; }

# --------------------------------------------------------------------------- #
# Build orchestration
#
# stages::build_plan reads the STAGES_* selection variables and fills
# STAGES_PLAN with "<dockerfile>|<base>|<image>|<build-arg>..." records. Front
# ends print the plan before running it so a build is never a surprise.
# --------------------------------------------------------------------------- #

# Selection inputs (front ends set these).
stages::init_selection() {
    STAGES_OS="24.04"
    STAGES_ROS="rolling"
    STAGES_USE_CUDA=false
    STAGES_CUDA_VERSION="${STAGES_DEFAULT_CUDA}"
    STAGES_USAGE="skip"          # manipulation | navigation | both | skip
    STAGES_SIMULATION=false      # gazebo layer
    STAGES_ZENOH=false
    STAGES_MUJOCO=false
    STAGES_MUJOCO_VERSION="${STAGES_DEFAULT_MUJOCO}"
    STAGES_GYM_VERSION="${STAGES_DEFAULT_GYM}"
    STAGES_ISAACSIM=false
    STAGES_ISAACSIM_VERSION="${STAGES_DEFAULT_ISAACSIM}"
    STAGES_ISAACLAB=false
    STAGES_ISAACLAB_VERSION="${STAGES_DEFAULT_ISAACLAB}"
    STAGES_ISAACLAB_RL="none"
    STAGES_USERNAME="admin"
    STAGES_USER_UID="$(id -u)"
    STAGES_USER_GID="$(id -g)"
    STAGES_FINAL_IMAGE=""        # empty => derived from the tag
    STAGES_PLAN=()
}

stages::_plan_add() {
    local dockerfile="$1"; shift
    local base="$1"; shift
    local image="$1"; shift
    local record="${dockerfile}|${base}|${image}"
    local arg
    for arg in "$@"; do
        record+="|${arg}"
    done
    STAGES_PLAN+=("${record}")
}

# Validate the current selection. Returns non-zero on a hard error; warns on
# combinations that are buildable but not covered by CI.
stages::validate_selection() {
    local ok=0

    if [[ ! " ${STAGES_SUPPORTED_OS[*]} " == *" ${STAGES_OS} "* ]]; then
        stages::error "Unsupported OS version: ${STAGES_OS} (allowed: ${STAGES_SUPPORTED_OS[*]})"
        ok=1
    fi

    local valid_ros; valid_ros="$(stages::ros_for_os "${STAGES_OS}")"
    if [[ -n "${valid_ros}" && ! " ${valid_ros} " == *" ${STAGES_ROS} "* ]]; then
        stages::error "ROS '${STAGES_ROS}' is not offered for Ubuntu ${STAGES_OS} (allowed: ${valid_ros})"
        ok=1
    fi

    if [[ ! -f "${CREATOR_DIR}/ros2/Dockerfile.${STAGES_ROS}" ]]; then
        stages::error "No Dockerfile for ROS distro '${STAGES_ROS}'"
        ok=1
    fi

    if [[ "${STAGES_ISAACLAB}" == true && "${STAGES_ISAACSIM}" != true ]]; then
        stages::error "Isaac Lab requires the Isaac Sim layer; enable Isaac Sim too."
        ok=1
    fi

    if [[ "${STAGES_ISAACSIM}" == true && "${STAGES_USE_CUDA}" != true ]]; then
        stages::warn "Isaac Sim without the CUDA base: the image will need a CUDA-capable runtime mounted at run time."
    fi

    if [[ "${STAGES_USAGE}" != "skip" ]] && ! stages::has_usage_layers "${STAGES_ROS}"; then
        stages::warn "MoveIt/Nav2 packages are not published for '${STAGES_ROS}'; that layer will be a no-op."
    fi

    local note; note="$(stages::deprecation_note "${STAGES_OS}" "${STAGES_ROS}")"
    if [[ -n "${note}" ]]; then
        stages::warn "${note}"
    fi

    if ! stages::is_ci_combo "${STAGES_OS}" "${STAGES_ROS}"; then
        stages::warn "Ubuntu ${STAGES_OS} + ${STAGES_ROS} is not built in CI; upstream packages may be missing."
    fi

    return ${ok}
}

# Turn the selection into an ordered build plan and derive the image names.
# Layer order matches ros2-staged.yml: base -> ros -> mujoco -> usage -> extras
# -> user.
stages::build_plan() {
    STAGES_PLAN=()
    stages::tag_reset
    stages::tag_add "${STAGES_OS}"

    local base_image image

    # --- base ---------------------------------------------------------------
    if [[ "${STAGES_USE_CUDA}" == true ]]; then
        stages::tag_add "cuda${STAGES_CUDA_VERSION}"
        base_image="nvidia/cuda:${STAGES_CUDA_VERSION}-cudnn-devel-ubuntu${STAGES_OS}"
        image="$(stages::layer_image base)"
        stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.cuda" "${base_image}" "${image}"
    else
        base_image="${STAGES_OS}"
        image="$(stages::layer_image base)"
        stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.base" "${base_image}" "${image}"
    fi
    base_image="${image}"

    # --- ROS ----------------------------------------------------------------
    stages::tag_add "${STAGES_ROS}"
    image="$(stages::layer_image ros)"
    stages::_plan_add "${CREATOR_DIR}/ros2/Dockerfile.${STAGES_ROS}" "${base_image}" "${image}"
    base_image="${image}"

    # --- MuJoCo -------------------------------------------------------------
    if [[ "${STAGES_MUJOCO}" == true ]]; then
        stages::tag_add "mujoco${STAGES_MUJOCO_VERSION}"
        image="$(stages::layer_image mujoco)"
        stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.mujoco" "${base_image}" "${image}" \
            "--build-arg" "MUJOCO_VERSION=${STAGES_MUJOCO_VERSION}" \
            "--build-arg" "GYM_VERSION=${STAGES_GYM_VERSION}"
        base_image="${image}"
    fi

    # --- usage (MoveIt / Nav2) ---------------------------------------------
    case "${STAGES_USAGE}" in
        manipulation)
            stages::tag_add "moveit"
            image="$(stages::layer_image moveit)"
            stages::_plan_add "${CREATOR_DIR}/usage/Dockerfile.moveit" "${base_image}" "${image}" \
                "--build-arg" "ROS_DISTRO=${STAGES_ROS}"
            base_image="${image}"
            ;;
        navigation)
            stages::tag_add "nav2"
            image="$(stages::layer_image nav2)"
            stages::_plan_add "${CREATOR_DIR}/usage/Dockerfile.nav2" "${base_image}" "${image}" \
                "--build-arg" "ROS_DISTRO=${STAGES_ROS}"
            base_image="${image}"
            ;;
        both)
            # No Dockerfile.both exists; stack the two layers instead.
            stages::tag_add "moveit"
            image="$(stages::layer_image moveit)"
            stages::_plan_add "${CREATOR_DIR}/usage/Dockerfile.moveit" "${base_image}" "${image}" \
                "--build-arg" "ROS_DISTRO=${STAGES_ROS}"
            base_image="${image}"
            stages::tag_add "nav2"
            image="$(stages::layer_image nav2)"
            stages::_plan_add "${CREATOR_DIR}/usage/Dockerfile.nav2" "${base_image}" "${image}" \
                "--build-arg" "ROS_DISTRO=${STAGES_ROS}"
            base_image="${image}"
            ;;
        skip) ;;
        *)
            stages::error "Unknown usage '${STAGES_USAGE}'"
            return 1
            ;;
    esac

    # --- Isaac Sim ----------------------------------------------------------
    if [[ "${STAGES_ISAACSIM}" == true ]]; then
        stages::tag_add "isaacsim${STAGES_ISAACSIM_VERSION}"
        image="$(stages::layer_image isaacsim)"
        local py torch_index
        py="$(stages::isaacsim_python "${STAGES_ISAACSIM_VERSION}")"
        torch_index="$(stages::torch_index_url "${STAGES_CUDA_VERSION}" "${STAGES_DEFAULT_TORCH}")"
        stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.isaacsim" "${base_image}" "${image}" \
            "--build-arg" "ISAACSIM_VERSION=${STAGES_ISAACSIM_VERSION}" \
            "--build-arg" "PYTHON_VERSION=${py}" \
            "--build-arg" "TORCH_VERSION=${STAGES_DEFAULT_TORCH}" \
            "--build-arg" "TORCH_INDEX_URL=${torch_index}" \
            "--build-arg" "USD_CONVERTER_VERSION=${STAGES_DEFAULT_USD_CONVERTER}"
        base_image="${image}"
    fi

    # --- Isaac Lab ----------------------------------------------------------
    if [[ "${STAGES_ISAACLAB}" == true ]]; then
        stages::tag_add "isaaclab${STAGES_ISAACLAB_VERSION#v}"
        image="$(stages::layer_image isaaclab)"
        local lab_install
        lab_install="$(stages::isaaclab_install_arg "${STAGES_ISAACLAB_VERSION}" "${STAGES_ISAACLAB_RL}")"
        stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.isaaclab" "${base_image}" "${image}" \
            "--build-arg" "ISAACLAB_VERSION=${STAGES_ISAACLAB_VERSION}" \
            "--build-arg" "ISAACLAB_INSTALL=${lab_install}"
        base_image="${image}"
    fi

    # --- Zenoh --------------------------------------------------------------
    if [[ "${STAGES_ZENOH}" == true ]]; then
        stages::tag_add "zenoh"
        image="$(stages::layer_image zenoh)"
        stages::_plan_add "${CREATOR_DIR}/usage/Dockerfile.zenoh" "${base_image}" "${image}"
        base_image="${image}"
    fi

    # --- Gazebo -------------------------------------------------------------
    if [[ "${STAGES_SIMULATION}" == true ]]; then
        stages::tag_add "gazebo"
        image="$(stages::layer_image gazebo)"
        stages::_plan_add "${CREATOR_DIR}/usage/Dockerfile.gazebo" "${base_image}" "${image}"
        base_image="${image}"
    fi

    # Docker caps a tag at 128 characters; a maximal stack of layers gets close.
    local full_tag; full_tag="$(stages::tag)"
    if (( ${#full_tag} > 128 )); then
        stages::error "Derived tag is ${#full_tag} characters (Docker allows 128): ${full_tag}"
        stages::error "Pass an explicit image name to override the derived one."
        return 1
    fi

    # --- final user image ---------------------------------------------------
    # Named automatically from the accumulated tag, the same way ros2-staged.yml
    # names its final images. -i / the interactive prompt can override it.
    if [[ -z "${STAGES_FINAL_IMAGE}" ]]; then
        STAGES_FINAL_IMAGE="$(stages::final_image)"
    fi
    stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.user" "${base_image}" "${STAGES_FINAL_IMAGE}" \
        "--build-arg" "USERNAME=${STAGES_USERNAME}" \
        "--build-arg" "USER_UID=${STAGES_USER_UID}" \
        "--build-arg" "USER_GID=${STAGES_USER_GID}" \
        "--build-arg" "ROS_DISTRO=${STAGES_ROS}"
}

stages::print_plan() {
    stages::heading "Build plan (${#STAGES_PLAN[@]} layers)"
    local i=1 record dockerfile base image
    for record in "${STAGES_PLAN[@]}"; do
        IFS='|' read -r dockerfile base image _rest <<<"${record}"
        printf '  %d. %-28s %s\n' "${i}" "${dockerfile#"${CREATOR_DIR}/"}" "${image}"
        printf '     %-28s from %s\n' "" "${base}"
        i=$((i + 1))
    done
    echo
    stages::info "Final image: ${STAGES_FINAL_IMAGE}"
}

stages::run_plan() {
    local record dockerfile base image
    local -a extra
    local step=1 total="${#STAGES_PLAN[@]}"
    for record in "${STAGES_PLAN[@]}"; do
        IFS='|' read -r -a fields <<<"${record}"
        dockerfile="${fields[0]}"
        base="${fields[1]}"
        image="${fields[2]}"
        extra=("${fields[@]:3}")
        if [[ ! -f "${dockerfile}" ]]; then
            stages::error "Missing Dockerfile: ${dockerfile}"
            return 1
        fi
        stages::heading "Building ${image} (layer ${step}/${total})"
        # Abort on the first failing layer. Without this the loop carries on and
        # every later layer fails too -- trying to *pull* the base its
        # predecessor never produced -- and the run still ends by announcing a
        # final image that does not exist.
        if ! "${SCRIPTS_DIR}/build_image.sh" "${dockerfile}" "${base}" "${image}" "${extra[@]}"; then
            echo
            stages::error "Layer ${step}/${total} failed: ${dockerfile#"${CREATOR_DIR}/"} -> ${image}"
            stages::error "Stopping here; ${STAGES_FINAL_IMAGE} was NOT built."
            if (( step > 1 )); then
                stages::info "Layers 1-$((step - 1)) were built and are cached, so a re-run resumes from this one."
            fi
            return 1
        fi
        step=$((step + 1))
    done
    stages::info "Done. Final image: ${STAGES_FINAL_IMAGE}"
}

# --------------------------------------------------------------------------- #
# Isaac Sim run support
#
# The pip distribution is NOT laid out like the NGC `nvcr.io/nvidia/isaac-sim`
# image. That image is the binary distribution rooted at /isaac-sim, which is why
# the official docker run example mounts /isaac-sim/.cache, /isaac-sim/.local/...
# and sets ACCEPT_EULA. Installed from wheels, Kit resolves all of those from
# $HOME instead, so the mounts move to /home/<user>/... — the same layout Isaac
# Lab's own docker-compose.yaml uses for its pip container.
#
# Without these mounts every container start recompiles shaders, which is the
# multi-minute "first launch" people mistake for a hang.
# --------------------------------------------------------------------------- #

# Host side of the persistent Omniverse caches. Matches the ~/docker/isaac-sim
# convention from the NVIDIA docs so an existing cache is reused.
STAGES_ISAAC_CACHE_ROOT="${STAGES_ISAAC_CACHE_ROOT:-${HOME}/docker/isaac-sim}"

# True when the image carries the Isaac Sim layer (Dockerfile.isaacsim sets
# ISAACSIM_VERSION), so run mode can configure itself instead of relying on the
# caller to remember a flag.
stages::image_has_isaacsim() {
    docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$1" 2>/dev/null \
        | grep -q '^ISAACSIM_VERSION='
}

# Read one environment variable back off a built image.
stages::image_env() {
    docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$1" 2>/dev/null \
        | sed -n "s/^$2=//p" | head -1
}

# stages::isaac_run_args <image> <container_home>
# Appends the Isaac Sim docker run arguments to STAGES_ISAAC_ARGS and creates the
# host cache directories.
stages::isaac_run_args() {
    local image="$1" home="$2"
    local root="${STAGES_ISAAC_CACHE_ROOT}"
    STAGES_ISAAC_ARGS=()

    # host subdir : container path (relative to the container user's home)
    local -a mounts=(
        "cache/ov:${home}/.cache/ov"
        "cache/pip:${home}/.cache/pip"
        "cache/glcache:${home}/.cache/nvidia/GLCache"
        "cache/computecache:${home}/.nv/ComputeCache"
        "logs:${home}/.nvidia-omniverse/logs"
        "config:${home}/.nvidia-omniverse/config"
        "data:${home}/.local/share/ov/data"
        "documents:${home}/Documents"
    )

    # The Kit SDK cache lives inside the venv; Dockerfile.isaacsim records where.
    local isaac_root; isaac_root="$(stages::image_env "${image}" ISAACSIM_ROOT)"
    if [[ -n "${isaac_root}" ]]; then
        mounts+=("cache/kit:${isaac_root}/kit/cache")
    fi

    local entry host_dir target
    for entry in "${mounts[@]}"; do
        host_dir="${root}/${entry%%:*}"
        target="${entry#*:}"
        # Created here rather than left to docker: docker would create them
        # root-owned, and the container runs as the host user.
        mkdir -p "${host_dir}"
        STAGES_ISAAC_ARGS+=(-v "${host_dir}:${target}:rw")
    done

    STAGES_ISAAC_ARGS+=(
        --gpus all
        # Baked into the image too, but set explicitly so `docker run` on this
        # image is self-documenting.
        -e OMNI_KIT_ACCEPT_EULA=YES
        # Honoured by the Omniverse telemetry/licence layer shared with the NGC
        # image; harmless here, and required if you later swap in that image.
        -e ACCEPT_EULA=Y
        -e PRIVACY_CONSENT=Y
    )
}
