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

# Isaac Lab branches worth building from: the two development lines first, then
# the release maintenance branches newest first. The repository also carries
# dozens of personal, CI and backport branches; they are filtered out so the
# menu stays short and every entry is something a user would actually pin to.
stages::isaaclab_branches() {
    local limit="${1:-4}"
    local -a heads=() ordered=()
    mapfile -t heads < <(
        git ls-remote --heads https://github.com/isaac-sim/IsaacLab.git 2>/dev/null \
            | awk -F'refs/heads/' '{print $2}'
    )
    (( ${#heads[@]} == 0 )) && return 0

    local b
    for b in main develop; do
        printf '%s\n' "${heads[@]}" | grep -qxF "${b}" && ordered+=("${b}")
    done
    mapfile -t -O "${#ordered[@]}" ordered < <(
        printf '%s\n' "${heads[@]}" | grep -E '^release/v?[0-9]+\.[0-9]+' | sort -urV
    )

    (( ${#ordered[@]} == 0 )) && return 0
    printf '%s\n' "${ordered[@]}" | head -n "${limit}"
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
STAGES_DEFAULT_ISAACSIM="6.1.0.0"
STAGES_DEFAULT_ISAACLAB="release/3.0.0"
STAGES_DEFAULT_TORCH="2.11.0"
STAGES_DEFAULT_TORCHVISION="0.26.0"

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

# Versioned refs are unambiguous; current development branches use 3.x.
stages::isaaclab_major() {
    local ref="${1#release/}"
    ref="${ref#v}"
    if [[ "$ref" =~ ^([0-9]+)\. ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo 3
    fi
}

# stages::isaaclab_install_arg <version> <framework>
#
# Isaac Lab 3.x delegates isaaclab.sh to its Python CLI and changed
# the --install vocabulary: "none" is gone (the equivalent is "core") and the RL
# frameworks moved behind an rl[...] selector with hyphenated names. Passing a
# 2.x token to a 3.x checkout fails the layer, so translate here.
stages::isaaclab_install_arg() {
    local version="$1" framework="$2"
    local major; major="$(stages::isaaclab_major "${version}")"

    if (( major < 3 )); then
        echo "${framework}"
        return 0
    fi

    case "${framework}" in
        none)     echo "core" ;;
        all)      echo "rl[rsl-rl],rl[rl-games],rl[skrl],rl[sb3]" ;;
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

# stages::tag_slug <text> — make <text> safe for a Docker tag component. Only
# needed for refs typed by the user (an Isaac Lab branch such as
# release/3.0.0 would otherwise produce an invalid image reference).
stages::tag_slug() { local s="${1//[^A-Za-z0-9._-]/-}"; echo "${s}"; }
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
    STAGES_ISAACLAB_METHOD="auto"
    STAGES_ISAACLAB_INSTALL="default"
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

# Match the two source-installation paths documented for release/3.0.0.
stages::isaaclab_method() {
    if [[ "${STAGES_ISAACLAB_METHOD}" != auto ]]; then
        echo "${STAGES_ISAACLAB_METHOD}"
    elif [[ "${STAGES_ISAACSIM}" == true ]]; then
        echo python-env
    else
        echo legacy
    fi
}

stages::validate_isaaclab() {
    [[ "${STAGES_ISAACLAB}" == true ]] || return 0
    local method major
    method="$(stages::isaaclab_method)"
    major="$(stages::isaaclab_major "${STAGES_ISAACLAB_VERSION}")"
    case "$method" in
        python-env)
            if [[ "${STAGES_ISAACSIM}" != true ]]; then
                stages::error "python-env requires Isaac Sim (-I). Use -j legacy for Kit-less Isaac Lab 3.x."
                return 1
            fi
            if (( major >= 3 )) && [[ "${STAGES_ISAACSIM_VERSION%%.*}" != 6 ]]; then
                stages::error "Isaac Lab 3.x requires Isaac Sim 6.x with Python 3.12."
                return 1
            fi
            ;;
        legacy)
            if (( major < 3 )) || [[ "${STAGES_ISAACSIM}" == true ]]; then
                stages::error "legacy selects Kit-less Isaac Lab 3.x; omit -I or use -j python-env."
                return 1
            fi
            ;;
        *) stages::error "Isaac Lab method must be auto, legacy, or python-env."; return 1 ;;
    esac
    if [[ ",${STAGES_ISAACLAB_INSTALL}," == *,isaacsim,* ]]; then
        stages::error "Select Isaac Sim through -I and -j python-env, not the isaacsim package selector."
        return 1
    fi
    local selector_pattern='^[a-z0-9_-]+(\[[a-z0-9_,-]+\])?(,[a-z0-9_-]+(\[[a-z0-9_,-]+\])?)*$'
    if [[ ! "${STAGES_ISAACLAB_INSTALL}" =~ $selector_pattern ]]; then
        stages::error "Invalid Isaac Lab package selectors: ${STAGES_ISAACLAB_INSTALL}"
        return 1
    fi
}

# Turn the selection into an ordered build plan and derive the image names.
# Layer order matches ros2-staged.yml: base -> ros -> mujoco -> usage -> extras
# -> user.
stages::build_plan() {
    stages::validate_isaaclab || return 1
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
        local py
        py="$(stages::isaacsim_python "${STAGES_ISAACSIM_VERSION}")"
        stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.isaacsim" "${base_image}" "${image}" \
            "--build-arg" "ISAACSIM_VERSION=${STAGES_ISAACSIM_VERSION}" \
            "--build-arg" "PYTHON_VERSION=${py}" \
            "--build-arg" "TORCH_VERSION=${STAGES_DEFAULT_TORCH}" \
            "--build-arg" "TORCHVISION_VERSION=${STAGES_DEFAULT_TORCHVISION}"
        base_image="${image}"
    fi

    # --- Isaac Lab ----------------------------------------------------------
    if [[ "${STAGES_ISAACLAB}" == true ]]; then
        stages::tag_add "isaaclab$(stages::tag_slug "${STAGES_ISAACLAB_VERSION#v}")"
        local lab_method
        lab_method="$(stages::isaaclab_method)"
        stages::tag_add "$lab_method"
        if [[ "${STAGES_ISAACLAB_INSTALL}" != default ]]; then
            stages::tag_add "packages$(printf %s "${STAGES_ISAACLAB_INSTALL}" | sha256sum | cut -c1-8)"
        fi
        image="$(stages::layer_image isaaclab)"
        stages::_plan_add "${CREATOR_DIR}/common/Dockerfile.isaaclab" "${base_image}" "${image}" \
            "--build-arg" "ISAACLAB_VERSION=${STAGES_ISAACLAB_VERSION}" \
            "--build-arg" "ISAACLAB_METHOD=${lab_method}" \
            "--build-arg" "ISAACLAB_INSTALL=${STAGES_ISAACLAB_INSTALL}"
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
        if [[ "$dockerfile" == */Dockerfile.isaaclab ]]; then
            printf '     installation: %s; packages: %s\n' "$(stages::isaaclab_method)" "${STAGES_ISAACLAB_INSTALL}"
        fi
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
    local image="$1" container_home="$2"
    local root="${STAGES_ISAAC_CACHE_ROOT}"
    STAGES_ISAAC_ARGS=()

    # host subdir : container path (relative to the container user's home)
    local -a mounts=(
        "cache/ov:${container_home}/.cache/ov"
        "cache/pip:${container_home}/.cache/pip"
        "cache/glcache:${container_home}/.cache/nvidia/GLCache"
        "cache/computecache:${container_home}/.nv/ComputeCache"
        "logs:${container_home}/.nvidia-omniverse/logs"
        "config:${container_home}/.nvidia-omniverse/config"
        "data:${container_home}/.local/share/ov/data"
        "documents:${container_home}/Documents"
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
        mkdir -p "${host_dir}" || return 1
        if [[ ! -w "${host_dir}" ]]; then
            stages::error "Isaac cache directory is not writable: ${host_dir}"
            return 1
        fi
        host_dir="$(cd -- "${host_dir}" && pwd -P)" || return 1
        if [[ "${host_dir}" == *,* ]]; then
            stages::error "Isaac cache paths containing commas are not supported."
            return 1
        fi
        STAGES_ISAAC_ARGS+=(--mount "type=bind,source=${host_dir},target=${target}")
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
