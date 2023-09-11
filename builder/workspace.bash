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
    local ws=$1; shift
    setup_rosdep
    if [ -f "$ws"/src/extra.sh ]; then
        "$ws"/src/extra.sh
    fi
}

function run_sh_files() {
    local ws=$1; shift
    local sh_files=("$@")
    setup_rosdep
    for file in "${sh_files[@]}";
    do
       if [ -f "$ws"/src/"$file" ]; then
        chmod +x "$ws"/src/"$file"
        "$ws"/src/"$file"
        fi
    done
}

function strip_xml_comments {
    sed -e '/<!--/ , /-->/d'
}

function read_depends {
    local src=$1; shift
    for dt in "$@"; do
        grep_opt -rhoP "(?<=<$dt>)[\w-]+(?=</$dt>)" "$src" | strip_xml_comments
    done
}


function list_packages {
    if [ "$ROS_VERSION" -eq 1 ]; then
        local src=$1; shift
        "/opt/ros/$ROS_DISTRO"/env.sh catkin_topological_order --only-names "/opt/ros/$ROS_DISTRO/share"
        "/opt/ros/$ROS_DISTRO"/env.sh catkin_topological_order --only-names "$src"
    fi
    if [ "$ROS_VERSION" -eq 2 ]; then
        if ! command -v colcon > /dev/null; then
            apt_get_install python3-colcon-common-extensions
        fi
        local src=$1; shift
        colcon list --base-paths "/opt/ros/$ROS_DISTRO/share" --names-only
        colcon list --base-paths "$src" --names-only
    fi
}

function apt_get_install {
    local cmd=()
    if command -v sudo > /dev/null; then
        cmd+=(sudo)
    fi
    cmd+=(apt-get install --no-install-recommends -qq -y)
    if [ -n "$*" ]; then
        "${cmd[@]}" "$@"
    else
        xargs -r "${cmd[@]}"
    fi
}

function setup_rosdep {
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    if [ "$ROS_VERSION" -eq 1 ]; then
        if [ "$ROS_DISTRO" == "noetic" ]; then
            if ! command -v rosdep > /dev/null; then
                apt_get_install python3-rosdep > /dev/null
            fi
        else
            if ! command -v rosdep > /dev/null; then
                apt_get_install python-rosdep > /dev/null
            fi
        fi
    fi
    if [ "$ROS_VERSION" -eq 2 ]; then
        if ! command -v rosdep > /dev/null; then
            apt_get_install python3-rosdep > /dev/null
        fi
    fi

    if command -v sudo > /dev/null; then
        sudo rosdep init || true
    else
        rosdep init | true
    fi
    rosdep update
}

function install_from_rosinstall {
    local rosinstall_file=$1
    local location=$2
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    if ! command -v vcstool > /dev/null; then
        if [[ "$ROS_VERSION" -eq 1 ]]; then
            if [ "$ROS_DISTRO" = "noetic" ]; then
                apt_get_install python3-vcstool > /dev/null
            else
                apt_get_install python-vcstool > /dev/null
            fi
        fi
        if [[ "$ROS_VERSION" -eq 2 ]]; then
            apt_get_install python3-vcstool > /dev/null
        fi
        if [[ "$ROS_VERSION" -ne 2 ]] && [[ "$ROS_VERSION" -ne 1 ]]; then
            echo "Cannot get ROS_VERSION"
            exit 1
        fi
    fi
    # install git
    if ! command -v git > /dev/null; then
        apt_get_install git > /dev/null
    fi
    vcs import "$location" < "$rosinstall_file"
    rm "$rosinstall_file"
}

function resolve_depends {
    local ws=$1
    if [ -z "$ws" ]; then
        echo "Error: Workspace path is not provided."
        return 1
    fi

    case "$ROS_VERSION" in
        1)
            # For ROS1
            echo "Resolving dependencies for ROS1..."
            rosdep install --from-paths "$ws" --ignore-src -y -r --rosdistro "$ROS_DISTRO"
            ;;

        2)
            # For ROS2
            echo "Resolving dependencies for ROS2..."
            rosdep install --from-paths "$ws" --ignore-src -y -r --rosdistro "$ROS_DISTRO"
            ;;

        *)
            echo "Error: Unsupported ROS version. Please use ROS 1 or 2."
            return 1
            ;;
    esac
}

function remove_comments {
    local src=$1
    find "$src" -name 'package.xml' | while read -r file; do
        sed -i '/<!--/,/-->/d' "$file"
    done
}

function create_depends {
    if [[ "$ROS_VERSION" -eq 1 ]]; then
        local src=$1; shift
        remove_comments "$src"
        comm -23 <(read_depends "$src" "$@"| sort -u) <(list_packages "$src" | sort -u) | xargs -r "/opt/ros/$ROS_DISTRO"/env.sh rosdep resolve | grep_opt -v '^#' | sort -u
    elif [[ "$ROS_VERSION" -eq 2 ]]; then
        local src=$1; shift
        remove_comments "$src"
        comm -23 <(read_depends "$src" "$@"| sort -u) <(list_packages "$src" | sort -u) | xargs -r rosdep resolve | grep_opt -v '^#' | sort -u
    else
        echo "Cannot get ROS_VERSION"
        exit 1
    fi
}

function install_dep_python {
    local ws=$1
    apt_get_install python3-pip >/dev/null
    find "$ws" -type f -name 'requirements.txt' -exec pip install -r {} \;
}

function build_workspace {
    local ws=$1
    apt_get_install build-essential
    setup_rosdep
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    for file in $(find "$ws/src" -type f -regex '.*\.\(rosinstall\|repo\|repos\)'); do
        echo "Installing from $file..."
        install_from_rosinstall "$file" "$ws/src"
    done
    resolve_depends "$ws/src"
    create_depends "$ws/src" depend build_export_depend exec_depend run_depend > "$ws/DEPENDS"
    create_depends "$ws/src" depend build_depend build_export_depend | apt_get_install
    install_dep_python "$ws/src"
    if [ "$ROS_VERSION" -eq 1 ]; then
        "/opt/ros/$ROS_DISTRO/env.sh" catkin_make_isolated -C "$ws" -DCATKIN_ENABLE_TESTING=0 "$CMAKE_ARGS"
    elif [ "$ROS_VERSION" -eq 2 ]; then
        cd "$ws" && colcon build --cmake-args -DBUILD_TESTING=OFF "$CMAKE_ARGS"
    fi
}

function test_workspace {
    local ws=$1
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    # create_depends "$ws/src" depend exec_depend run_depend test_depend | apt_get_install
    if [ "$ROS_VERSION" -eq 1 ]; then
        "/opt/ros/$ROS_DISTRO/env.sh" catkin_make_isolated -C "$ws" -DCATKIN_ENABLE_TESTING=1
        "/opt/ros/$ROS_DISTRO/env.sh" catkin_test_results --verbose "$ws"
    elif [ "$ROS_VERSION" -eq 2 ]; then
        cd "$ws" && colcon test
        colcon test-result --verbose
    fi
}

function install_depends {
    local ws=$1; shift
    apt_get_install < "$ws/DEPENDS"
}

function install_workspace {
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    echo "ROS_VERSION: $ROS_VERSION"
    echo "ROS_DISTRO: $ROS_DISTRO"
    if [[ "$ROS_VERSION" -eq 1 ]]; then
        echo "It is: $ROS_DISTRO"
        local ws=$1; shift
        "/opt/ros/$ROS_DISTRO"/env.sh catkin_make_isolated -C "$ws" --install --install-space "/opt/ros/$ROS_DISTRO"
    fi
    if [[ "$ROS_VERSION" -eq 2 ]]; then
        echo "It is: $ROS_DISTRO"
        local ws=$1; shift
        rm -r "$ws"/build
        make_ros_entrypoint "$ws" > /ros_entrypoint.sh
        source "/ros_entrypoint.sh"
    fi
    if [[ "$ROS_VERSION" -ne 2 ]] && [[ "$ROS_VERSION" -ne 1 ]]; then
        exit 1
    fi
}

function make_ros_entrypoint {
    local ws=$1; shift
cat <<- _EOF_
#!/bin/bash
set -e

# setup ros2 environment
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
