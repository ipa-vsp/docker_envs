#!/bin/bash

set -e
set -o pipefail

function builder_setup {
    apt_get_install python3-colcon-common-extensions python3-catkin-pkg python3-pip
    python3 -m pip install catkin_pkg
}

function grep_opt {
    grep "$@" || [[ $? = 1 ]]
}

function update_list {
    local ws=$1
    shift
    setup_rosdep
    if [ -f "$ws"/src/extra.sh ]; then
        "$ws"/src/extra.sh
    fi
}

function run_sh_files() {
    local ws=$1
    shift
    local sh_files=("$@")
    setup_rosdep
    for file in "${sh_files[@]}"; do
        if [ -f "$ws"/src/"$file" ]; then
            chmod +x "$ws"/src/"$file"
            "$ws"/src/"$file"
        fi
    done
}

function read_depends {
    local src=$1
    shift
    for dt in "$@"; do
        grep_opt -rhoP "(?<=<$dt>)[\w-]+(?=</$dt>)" "$src"
    done
}

function list_packages {
    local src=$1
    shift
    local rest="$*"
    while [[ $rest =~ (.*)"--"(.*) ]]; do
        IFS=' ' read -ra eles <<<"${BASH_REMATCH[2]}"
        v="${eles[0]}"
        if [[ -n "${eles[@]:1}" ]]; then
            declare -a "$v"="( $(printf '%q ' "${eles[@]:1}") )"
        fi
        rest=${BASH_REMATCH[1]}
        unset IFS
    done

    local cmd=("/opt/ros/$ROS_DISTRO/share")
    if [ "$ROS_VERSION" -eq 1 ]; then
        "/opt/ros/$ROS_DISTRO"/env.sh catkin_topological_order --only-names "/opt/ros/$ROS_DISTRO/share"
        "/opt/ros/$ROS_DISTRO"/env.sh catkin_topological_order --only-names "$src"
        if [[ -n "${underlay[@]}" ]]; then
            for ws in "${underlay[@]}"; do
                if [ -d "$ws" ]; then
                    "/opt/ros/$ROS_DISTRO"/env.sh catkin_topological_order --only-names "$ws"
                fi
            done
        fi
    fi

    if [[ -n "${underlay[@]}" ]]; then
        if [ "$ROS_VERSION" -eq 2 ]; then
            for ws in "${underlay[@]}"; do
                if [ -d "$ws/install" ]; then
                    cmd+=("$ws/install/*")
                fi
            done
        fi
    fi

    cmd+=("$src")
    if [ "$ROS_VERSION" -eq 2 ]; then
        if ! command -v colcon >/dev/null; then
            apt_get_install python3-colcon-common-extensions
        fi
        echo "check path: ${cmd[@]}"
        colcon list --base-paths "${cmd[@]}" --names-only
    fi
}

function setup_rosdep {
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    if [ "$ROS_VERSION" -eq 1 ]; then
        if [ "$ROS_DISTRO" == "noetic" ]; then
            if ! command -v rosdep >/dev/null; then
                apt_get_install python3-rosdep >/dev/null
            fi
        else
            if ! command -v rosdep >/dev/null; then
                apt_get_install python-rosdep >/dev/null
            fi
        fi
    fi
    if [ "$ROS_VERSION" -eq 2 ]; then
        if ! command -v rosdep >/dev/null; then
            apt_get_install python3-rosdep >/dev/null
        fi
    fi
    if command -v sudo >/dev/null; then
        sudo rosdep init || true
    else
        rosdep init | true
    fi
    rosdep update
}

function resolve_depends {
    local src=$1
    shift
    local rest="$*"
    while [[ $rest =~ (.*)"--"(.*) ]]; do
        IFS=' ' read -ra eles <<<"${BASH_REMATCH[2]}"
        v="${eles[0]}"
        if [[ -n "${eles[@]:1}" ]]; then
            declare -a "$v"="( $(printf '%q ' "${eles[@]:1}") )"
        fi
        rest=${BASH_REMATCH[1]}
        unset IFS
    done

    if [[ "$ROS_VERSION" -eq 1 ]]; then
        comm -23 <(read_depends "$src" "${deptypes[@]}" | sort -u) <(list_packages "$src" --underlay "${underlay[@]}" | sort -u) | xargs -r "/opt/ros/$ROS_DISTRO"/env.sh rosdep resolve | grep_opt -v '^#' | sort -u
    fi

    if [[ "$ROS_VERSION" -eq 2 ]]; then
        comm -23 <(read_depends "$src" "${deptypes[@]}" | sort -u) <(list_packages "$src" --underlay "${underlay[@]}" | sort -u) | xargs -r rosdep resolve | grep_opt -v '^#' | sort -u || true
    fi
    if [ "$ROS_VERSION" -ne 2 ] && [ "$ROS_VERSION" -ne 1 ]; then
        echo "Cannot get ROS_VERSION"
        exit 1
    fi
}

function apt_get_install {
    local cmd=()
    if command -v sudo >/dev/null; then
        cmd+=(sudo)
    fi
    cmd+=(apt-get install --no-install-recommends -qq -y)
    if [ -n "$*" ]; then
        "${cmd[@]}" "$@"
    else
        xargs -r "${cmd[@]}"
    fi
}

function pass_ci_token {
    local rosinstall_file=$1
    shift
    if ! command -v gettext >/dev/null; then
        apt_get_install gettext >/dev/null
    fi
    sed -i 's/https:\/\/git-ce\./https:\/\/gitlab-ci-token:\$\{CI_JOB_TOKEN\}\@git-ce\./g' "$rosinstall_file"
    envsubst <"$rosinstall_file" >tmp.rosinstall
    rm "$rosinstall_file"
    mv tmp.rosinstall "$rosinstall_file"
}

function install_poetry() {
    if ! command -v poetry &>/dev/null; then
        echo "Poetry is not installed. Installing poetry..."
        if ! command -v pip3 &>/dev/null; then
            echo "pip3 is not installed. Installing python3-pip..."
            apt_get_install python3-pip
            if ! command -v pip3 &>/dev/null; then
                echo "Failed to install python3-pip. Exiting."
                exit 1
            fi
        fi
        python3 -m pip install poetry
        if ! command -v poetry &>/dev/null; then
            echo "Failed to install poetry. Exiting."
            exit 1
        else
            echo "Poetry successfully installed."
        fi
    else
        echo "Poetry is already installed."
    fi
    poetry config virtualenvs.create false
}

function find_pyproject_dirs() {
    local workspace="$1"
    local depth="$2"
    local pyproject_dirs=()
    while IFS= read -r dir; do
        pyproject_dirs+=("$dir")
    done < <(find "$workspace" -maxdepth "$depth" -type f -name "pyproject.toml" -exec dirname {} \; | sort -u)
    echo "${pyproject_dirs[@]}"
}

function poetry_install_in_dirs() {
    local workspace="$1"
    local depth="$2"
    install_poetry
    poetry config virtualenvs.create false
    local pyproject_dirs=($(find_pyproject_dirs "$workspace" "$depth"))
    for dir in "${pyproject_dirs[@]}"; do
        echo "Running 'poetry install' in directory: $dir"
        poetry install -C "$dir" --no-ansi
        if [ $? -eq 0 ]; then
            echo "Successfully installed dependencies in $dir"
        else
            echo "Failed to install dependencies in $dir"
        fi
    done
}

function update_git_submodules() {
    local workspace="$1"
    local git_dirs=($(find "$workspace" -type d -name ".git"))
    for git_dir in "${git_dirs[@]}"; do
        local repo_dir=$(dirname "$git_dir")
        echo "Checking repository: $repo_dir"
        cd "$repo_dir" || continue
        if git submodule status &>/dev/null; then
            echo "Updating submodules in: $repo_dir"
            git submodule update --init --recursive
            if [ $? -eq 0 ]; then
                echo "Successfully updated and initialized submodules in $repo_dir"
            else
                echo "Failed to update and initialize submodules in $repo_dir"
            fi
        else
            echo "No git submodules found in $repo_dir"
        fi
    done
}

function make_ros_entrypoint {
    local ws=$1
    shift
    cat <<-_EOF_
#!/bin/bash
set -e
source "/opt/ros/$ROS_DISTRO/setup.bash" --
if [ -f "$ws"/install/setup.bash ]; then
    source "$ws/install/setup.bash" --
fi
exec "\$@"
_EOF_
}

if [ -n "$*" ]; then
    "$@"
fi
