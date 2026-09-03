#!/usr/bin/env bash
# Interactive front end for the local creator image stack.
#
# Walks through every build stage, offering the choices valid for the previous
# selections. MuJoCo, Isaac Sim, Isaac Lab and CUDA version lists are fetched
# online on every run, so the newest release is always on the menu.
#
# The non-interactive equivalent is ./run_env.sh.

set -uo pipefail

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source=lib/stages.sh
source "${ROOT}/lib/stages.sh"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" || "${1:-}" == "-p" ]] && DRY_RUN=true
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "Usage: create_env.sh [--dry-run]"
    echo "  --dry-run   Walk through the prompts and print the plan without building."
    exit 0
fi

# --------------------------------------------------------------------------- #
# Prompt helpers
#
# The prompt is printed with printf rather than `read -p` so it is still visible
# when answers are piped in (bash suppresses the -p prompt for non-terminals).
# --------------------------------------------------------------------------- #

# ask_choice <prompt> <default-index> <option>...
# Result in CHOICE.
ask_choice() {
    local prompt="$1" default="$2"; shift 2
    local options=("$@") i answer
    echo
    echo "${prompt}"
    for i in "${!options[@]}"; do
        if (( i + 1 == default )); then
            printf '  %2d) %s  [default]\n' "$((i + 1))" "${options[i]}"
        else
            printf '  %2d) %s\n' "$((i + 1))" "${options[i]}"
        fi
    done
    while true; do
        printf 'Select [1-%d] (%d): ' "${#options[@]}" "${default}"
        read -r answer || answer=""
        answer="${answer:-${default}}"
        if [[ "${answer}" =~ ^[0-9]+$ ]] && (( answer >= 1 && answer <= ${#options[@]} )); then
            CHOICE="${options[answer - 1]}"
            echo "  -> ${CHOICE}"
            return 0
        fi
        echo "  Please enter a number between 1 and ${#options[@]}."
    done
}

# ask_yes_no <prompt> <yes|no default>
ask_yes_no() {
    local prompt="$1" default="$2" answer hint="y/N"
    [[ "${default}" == "yes" ]] && hint="Y/n"
    while true; do
        printf '\n%s [%s]: ' "${prompt}" "${hint}"
        read -r answer || answer=""
        answer="${answer:-${default}}"
        case "${answer,,}" in
            y|yes) return 0 ;;
            n|no)  return 1 ;;
            *)     echo "  Please answer y or n." ;;
        esac
    done
}

# ask_value <prompt> <default>  — result in VALUE.
ask_value() {
    local prompt="$1" default="$2" answer
    printf '\n%s [%s]: ' "${prompt}" "${default}"
    read -r answer || answer=""
    VALUE="${answer:-${default}}"
}

# ask_version <label> <kind> [os]
# Shows the versions discovered online plus a manual-entry escape hatch.
# Result in VERSION.
ask_version() {
    local label="$1" kind="$2" os="${3:-}"
    local -a versions=()
    printf '\nLooking up available %s versions...\n' "${label}"
    case "${kind}" in
        mujoco)   mapfile -t versions < <(stages::mujoco_versions 8) ;;
        isaacsim) mapfile -t versions < <(stages::isaacsim_versions 8) ;;
        isaaclab) mapfile -t versions < <(stages::isaaclab_versions 8) ;;
        cuda)     mapfile -t versions < <(stages::cuda_versions "${os}" 8) ;;
    esac

    if (( ${#versions[@]} == 0 )); then
        stages::warn "Could not reach the ${label} index (offline?). Falling back to the built-in default."
        case "${kind}" in
            mujoco)   VERSION="${STAGES_DEFAULT_MUJOCO}" ;;
            isaacsim) VERSION="${STAGES_DEFAULT_ISAACSIM}" ;;
            isaaclab) VERSION="${STAGES_DEFAULT_ISAACLAB}" ;;
            cuda)     VERSION="${STAGES_DEFAULT_CUDA}" ;;
        esac
        ask_value "${label} version" "${VERSION}"
        VERSION="${VALUE}"
        return 0
    fi

    # The list is newest first, so entry 1 is always "the latest".
    local -a labelled=("${versions[0]} (latest)")
    local v
    for v in "${versions[@]:1}"; do
        labelled+=("${v}")
    done
    labelled+=("other (type a version)")

    ask_choice "Which ${label} version?" 1 "${labelled[@]}"
    if [[ "${CHOICE}" == "other (type a version)" ]]; then
        ask_value "${label} version" "${versions[0]}"
        VERSION="${VALUE}"
    else
        VERSION="${CHOICE% (latest)}"
    fi
}

# Print the ./run_env.sh invocation matching the answers just given, so an
# interactive session can be replayed non-interactively (scripts, CI, notes).
equivalent_command() {
    local cmd="./run_env.sh -b -o ${STAGES_OS} -v ${STAGES_ROS}"
    [[ "${STAGES_USE_CUDA}" == true ]]   && cmd+=" -c ${STAGES_CUDA_VERSION}"
    [[ "${STAGES_USAGE}" != skip ]]      && cmd+=" -u ${STAGES_USAGE}"
    [[ "${STAGES_MUJOCO}" == true ]]     && cmd+=" -m ${STAGES_MUJOCO_VERSION}"
    [[ "${STAGES_ISAACSIM}" == true ]]   && cmd+=" -I ${STAGES_ISAACSIM_VERSION}"
    [[ "${STAGES_ISAACLAB}" == true ]]   && cmd+=" -L ${STAGES_ISAACLAB_VERSION}"
    [[ "${STAGES_ZENOH}" == true ]]      && cmd+=" -z"
    [[ "${STAGES_SIMULATION}" == true ]] && cmd+=" -s"
    cmd+=" -n ${STAGES_USERNAME} -U ${STAGES_USER_UID} -G ${STAGES_USER_GID}"
    [[ "${STAGES_FINAL_IMAGE}" != "${DERIVED_IMAGE}" ]] && cmd+=" -i ${STAGES_FINAL_IMAGE}"
    echo "    ${cmd}"
}

# --------------------------------------------------------------------------- #
# Walk through the stages
# --------------------------------------------------------------------------- #
stages::init_selection

cat <<'BANNER'

+---------------------------------------------------------------+
|  docker_envs :: interactive workspace builder                 |
|  Press Enter at any prompt to accept the [default].           |
+---------------------------------------------------------------+
BANNER

# --- Stage 1: Ubuntu -------------------------------------------------------
stages::heading "Stage 1/9 - Ubuntu release"
ask_choice "Which Ubuntu release should the image be based on?" 2 \
    "22.04" "24.04" "26.04"
STAGES_OS="${CHOICE}"

# --- Stage 2: base flavour -------------------------------------------------
stages::heading "Stage 2/9 - Base image"
if ask_yes_no "Use the NVIDIA CUDA + cuDNN devel base (needed for GPU workloads, Isaac Sim)?" "no"; then
    STAGES_USE_CUDA=true
    ask_version "CUDA" cuda "${STAGES_OS}"
    STAGES_CUDA_VERSION="${VERSION}"
else
    STAGES_USE_CUDA=false
    stages::info "Using the plain ubuntu:${STAGES_OS} base."
fi

# --- Stage 3: ROS ----------------------------------------------------------
stages::heading "Stage 3/9 - ROS 2 distribution"
read -r -a ROS_OPTIONS <<<"$(stages::ros_for_os "${STAGES_OS}")"
ROS_LABELS=()
for distro in "${ROS_OPTIONS[@]}"; do
    label="${distro}"
    stages::is_ci_combo "${STAGES_OS}" "${distro}" && label+=" (built in CI)"
    [[ -n "$(stages::deprecation_note "${STAGES_OS}" "${distro}")" ]] && label+=" (frozen upstream)"
    ROS_LABELS+=("${label}")
done
ask_choice "Which ROS 2 distribution?" 1 "${ROS_LABELS[@]}"
STAGES_ROS="${CHOICE%% *}"

# --- Stage 4: usage --------------------------------------------------------
stages::heading "Stage 4/9 - Application stack"
if stages::has_usage_layers "${STAGES_ROS}"; then
    ask_choice "Which application packages should be pre-installed?" 4 \
        "manipulation (MoveIt)" "navigation (Nav2)" "both" "skip"
else
    stages::warn "MoveIt/Nav2 are not published for ${STAGES_ROS} yet."
    ask_choice "Which application packages should be pre-installed?" 1 \
        "skip" "manipulation (MoveIt)" "navigation (Nav2)" "both"
fi
STAGES_USAGE="${CHOICE%% *}"

# --- Stage 5: MuJoCo -------------------------------------------------------
stages::heading "Stage 5/9 - MuJoCo"
if ask_yes_no "Add the MuJoCo physics layer?" "no"; then
    STAGES_MUJOCO=true
    ask_version "MuJoCo" mujoco
    STAGES_MUJOCO_VERSION="${VERSION}"
    ask_value "Gymnasium version" "${STAGES_DEFAULT_GYM}"
    STAGES_GYM_VERSION="${VALUE}"
fi

# --- Stage 6: Isaac Sim ----------------------------------------------------
stages::heading "Stage 6/9 - NVIDIA Isaac Sim"
if ask_yes_no "Add the Isaac Sim layer (large: several GB of wheels)?" "no"; then
    STAGES_ISAACSIM=true
    ask_version "Isaac Sim" isaacsim
    STAGES_ISAACSIM_VERSION="${VERSION}"
    if [[ "${STAGES_USE_CUDA}" != true ]]; then
        stages::warn "Isaac Sim on a non-CUDA base needs a GPU runtime supplied at run time (docker run --gpus all)."
    fi
fi

# --- Stage 7: Isaac Lab ----------------------------------------------------
stages::heading "Stage 7/9 - NVIDIA Isaac Lab"
if [[ "${STAGES_ISAACSIM}" == true ]]; then
    if ask_yes_no "Add the Isaac Lab layer?" "no"; then
        STAGES_ISAACLAB=true
        ask_version "Isaac Lab" isaaclab
        STAGES_ISAACLAB_VERSION="${VERSION}"
        ask_choice "Which reinforcement-learning framework should Isaac Lab install?" 1 \
            "none" "rsl_rl" "rl_games" "skrl" "sb3" "all"
        STAGES_ISAACLAB_RL="${CHOICE}"
    fi
else
    stages::info "Skipped: Isaac Lab builds on the Isaac Sim layer, which was not selected."
fi

# --- Stage 8: extras -------------------------------------------------------
stages::heading "Stage 8/9 - Extra layers"
ask_yes_no "Add the Zenoh middleware (rmw_zenoh_cpp) layer?" "no" && STAGES_ZENOH=true
ask_yes_no "Add the Gazebo simulation layer?" "no" && STAGES_SIMULATION=true

# --- Stage 9: user + naming ------------------------------------------------
stages::heading "Stage 9/9 - Container user and image name"
ask_value "Username to create inside the image" "${STAGES_USERNAME}"
STAGES_USERNAME="${VALUE}"
ask_value "UID for ${STAGES_USERNAME}" "${STAGES_USER_UID}"
STAGES_USER_UID="${VALUE}"
ask_value "GID for ${STAGES_USERNAME}" "${STAGES_USER_GID}"
STAGES_USER_GID="${VALUE}"
ask_value "Image namespace for the derived names" "${STAGES_NAMESPACE}"
STAGES_NAMESPACE="${VALUE}"

if ! stages::validate_selection; then
    exit 1
fi

# Derive the names first so the automatic one can be shown as the default.
if ! stages::build_plan; then
    exit 1
fi
DERIVED_IMAGE="${STAGES_FINAL_IMAGE}"
ask_value "Final image name" "${DERIVED_IMAGE}"
if [[ "${VALUE}" != "${DERIVED_IMAGE}" ]]; then
    STAGES_FINAL_IMAGE="${VALUE}"
    stages::build_plan || exit 1
fi

# --- Summary ---------------------------------------------------------------
stages::heading "Summary"
printf '  %-16s %s\n' "Ubuntu:"    "${STAGES_OS}"
printf '  %-16s %s\n' "Base:"      "$([[ ${STAGES_USE_CUDA} == true ]] && echo "CUDA ${STAGES_CUDA_VERSION} + cuDNN (devel)" || echo "ubuntu:${STAGES_OS}")"
printf '  %-16s %s\n' "ROS 2:"     "${STAGES_ROS}"
printf '  %-16s %s\n' "Usage:"     "${STAGES_USAGE}"
printf '  %-16s %s\n' "MuJoCo:"    "$([[ ${STAGES_MUJOCO} == true ]] && echo "${STAGES_MUJOCO_VERSION} (gymnasium ${STAGES_GYM_VERSION})" || echo "-")"
printf '  %-16s %s\n' "Isaac Sim:" "$([[ ${STAGES_ISAACSIM} == true ]] && echo "${STAGES_ISAACSIM_VERSION}" || echo "-")"
printf '  %-16s %s\n' "Isaac Lab:" "$([[ ${STAGES_ISAACLAB} == true ]] && echo "${STAGES_ISAACLAB_VERSION} (rl: ${STAGES_ISAACLAB_RL})" || echo "-")"
printf '  %-16s %s\n' "Zenoh:"     "$([[ ${STAGES_ZENOH} == true ]] && echo "yes" || echo "-")"
printf '  %-16s %s\n' "Gazebo:"    "$([[ ${STAGES_SIMULATION} == true ]] && echo "yes" || echo "-")"
printf '  %-16s %s\n' "User:"      "${STAGES_USERNAME} (${STAGES_USER_UID}:${STAGES_USER_GID})"

stages::print_plan

if [[ "${DRY_RUN}" == true ]]; then
    echo
    stages::info "Dry run: nothing was built."
    stages::info "Equivalent non-interactive command:"
    equivalent_command
    exit 0
fi

if ! ask_yes_no "Start the build?" "yes"; then
    stages::info "Aborted; nothing was built."
    exit 0
fi

stages::run_plan || exit 1

echo
stages::info "Run it with:"
echo "    ${ROOT}/run_env.sh -r -i ${STAGES_FINAL_IMAGE} -n ${STAGES_USERNAME} -w <your_workspace>"
echo
stages::info "Rebuild the same stack without the prompts:"
equivalent_command
