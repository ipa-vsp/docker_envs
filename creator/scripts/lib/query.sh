#!/usr/bin/env bash
# Machine-readable front end to lib/stages.sh.
#
# create_env.sh and run_env.sh are written for humans: ANSI colour, headings,
# prose warnings. A GUI (or any other tool) needs the same answers as records it
# can parse without guessing at the wording, so this script sources stages.sh,
# replaces the four output helpers with record emitters, and exposes the version
# lookups plus validation/planning as subcommands.
#
# Records are <FIELD><US><FIELD>... terminated by a newline, where <US> is the
# ASCII unit separator (0x1f). Nothing in a Dockerfile path, image name, build
# argument or stages.sh message can contain it, so no quoting or escaping scheme
# is needed on either side.
#
# Usage:
#   query.sh versions cuda <os> [limit]
#   query.sh versions <mujoco|isaacsim|isaaclab> [limit]
#   query.sh branches [limit]
#   query.sh ros-for-os <os>
#   query.sh isaaclab-selectors <version>
#   query.sh defaults
#   query.sh plan              # selection comes from DEG_* environment variables
#
# `plan` always exits 0: a selection is invalid when the output carries at least
# one ERROR record, not when the process fails.

set -uo pipefail

QUERY_LIB_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source=stages.sh
source "${QUERY_LIB_DIR}/stages.sh"

# ASCII unit separator. Assigned through printf so the literal byte never has to
# appear in this file.
printf -v US '\037'

# Replace the human-facing helpers. stages.sh calls these from inside
# validate_selection, validate_isaaclab and build_plan, so redefining them here
# turns every diagnostic into a record without touching stages.sh itself.
stages::info()    { :; }
stages::heading() { :; }
stages::warn()    { printf 'WARN%s%s\n' "${US}" "$*"; }
stages::error()   { printf 'ERROR%s%s\n' "${US}" "$*"; }

# Selection fields the GUI may set, as DEG_<FIELD> -> STAGES_<FIELD>. Listed
# explicitly rather than swept from the environment so an unrelated exported
# variable can never reach the build.
QUERY_FIELDS=(
    OS ROS USE_CUDA CUDA_VERSION USAGE SIMULATION ZENOH
    MUJOCO MUJOCO_VERSION GYM_VERSION
    ISAACSIM ISAACSIM_VERSION
    ISAACLAB ISAACLAB_VERSION ISAACLAB_METHOD ISAACLAB_INSTALL
    ISAACLAB_PHYSICS ISAACLAB_VISUALIZER
    USERNAME USER_UID USER_GID NAMESPACE FINAL_IMAGE
)

# Overlay DEG_* onto the defaults from stages::init_selection. An unset or empty
# DEG_* leaves the default in place, so a front end only sends what it changed.
query::apply_environment() {
    local field source_var
    for field in "${QUERY_FIELDS[@]}"; do
        source_var="DEG_${field}"
        if [[ -n "${!source_var:-}" ]]; then
            printf -v "STAGES_${field}" '%s' "${!source_var}"
        fi
    done
}

# CUDA is the only lookup that needs the Ubuntu release, so it alone takes the
# os argument: `versions cuda 24.04 8` but `versions mujoco 8`.
query::versions() {
    local kind="${1:-}"
    case "${kind}" in
        mujoco)   stages::mujoco_versions "${2:-8}" ;;
        isaacsim) stages::isaacsim_versions "${2:-8}" ;;
        isaaclab) stages::isaaclab_versions "${2:-8}" ;;
        cuda)     stages::cuda_versions "${2:-}" "${3:-8}" ;;
        *)        stages::error "Unknown version kind: ${kind}"; return 1 ;;
    esac
}

# Each distro with the annotations create_env.sh puts in its menu labels, so a
# GUI can render the same "built in CI" / "frozen upstream" badges.
query::ros_for_os() {
    local os="${1:-}" distro flags note
    for distro in $(stages::ros_for_os "${os}"); do
        flags=""
        stages::is_ci_combo "${os}" "${distro}" && flags="ci"
        note="$(stages::deprecation_note "${os}" "${distro}")"
        [[ -n "${note}" ]] && flags="${flags:+${flags},}frozen"
        printf '%s%s%s%s%s\n' "${distro}" "${US}" "${flags}" "${US}" "${note}"
    done
}

# Everything a front end needs to populate a form before any lookup succeeds:
# the offline fallbacks plus the initial selection.
# The package-selector vocabulary changed between Isaac Lab 2.x and 3.x, so the
# menu labels a front end shows depend on the selected version. Ask stages.sh
# rather than re-encoding the translation.
query::isaaclab_selectors() {
    local version="${1:-}" framework
    for framework in none rsl_rl rl_games skrl sb3 all; do
        printf '%s%s%s\n' "${framework}" "${US}" \
            "$(stages::isaaclab_install_arg "${version}" "${framework}")"
    done
}

query::defaults() {
    stages::init_selection
    local name
    for name in CUDA MUJOCO GYM ISAACSIM ISAACLAB TORCH TORCHVISION; do
        local var="STAGES_DEFAULT_${name}"
        printf 'DEFAULT%s%s%s%s\n' "${US}" "${name}" "${US}" "${!var}"
    done
    for name in "${QUERY_FIELDS[@]}"; do
        local var="STAGES_${name}"
        printf 'SELECTION%s%s%s%s\n' "${US}" "${name}" "${US}" "${!var}"
    done
    printf 'SUPPORTED_OS%s%s\n' "${US}" "${STAGES_SUPPORTED_OS[*]}"
}

query::plan() {
    stages::init_selection
    query::apply_environment

    # Both validators emit ERROR/WARN records through the helpers above. Keep
    # going after validate_selection fails so the caller sees every problem at
    # once rather than one per round trip.
    local valid=true
    stages::validate_selection || valid=false
    stages::validate_isaaclab  || valid=false
    if [[ "${valid}" != true ]]; then
        return 0
    fi

    if ! stages::build_plan; then
        return 0
    fi

    printf 'IMAGE%s%s\n' "${US}" "${STAGES_FINAL_IMAGE}"
    printf 'REPLAY%s%s\n' "${US}" "$(stages::equivalent_command)"
    if [[ "${STAGES_ISAACLAB}" == true ]]; then
        printf 'ISAACLAB_EFFECTIVE%s%s%s%s\n' \
            "${US}" "$(stages::isaaclab_method)" "${US}" "$(stages::isaaclab_effective_install)"
    fi

    local index=1 record dockerfile base image
    local -a fields
    for record in "${STAGES_PLAN[@]}"; do
        IFS='|' read -r -a fields <<<"${record}"
        dockerfile="${fields[0]#"${CREATOR_DIR}/"}"
        base="${fields[1]}"
        image="${fields[2]}"
        printf 'LAYER%s%d%s%s%s%s%s%s' \
            "${US}" "${index}" "${US}" "${dockerfile}" "${US}" "${base}" "${US}" "${image}"
        local arg
        for arg in "${fields[@]:3}"; do
            printf '%s%s' "${US}" "${arg}"
        done
        printf '\n'
        index=$((index + 1))
    done
}

case "${1:-}" in
    versions)   shift; query::versions "$@" ;;
    branches)   shift; stages::isaaclab_branches "${1:-4}" ;;
    ros-for-os) shift; query::ros_for_os "$@" ;;
    isaaclab-selectors) shift; query::isaaclab_selectors "$@" ;;
    defaults)   query::defaults ;;
    plan)       query::plan ;;
    *)
        echo "Usage: query.sh versions|branches|ros-for-os|isaaclab-selectors|defaults|plan" >&2
        exit 2
        ;;
esac
