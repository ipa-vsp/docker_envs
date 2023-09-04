#!/bin/bash

set -e
set -o pipefail

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
    if ! command -v rosdep > /dev/null; then
        if [ "$ROS_VERSION" -eq 1 ] && [ "$ROS_DISTRO" != "noetic" ]; then
            apt_get_install python-rosdep
        else
            apt_get_install python3-rosdep
        fi
    fi
    if command -v sudo > /dev/null; then
        sudo rosdep init || true
    else
        rosdep init || true
    fi
    rosdep update
}

function install_from_rosinstall {
    local rosinstall_file=$1
    local location=$2
    apt_get_install git vcstool >/dev/null
    vcs import "$location" < "$rosinstall_file"
    rm "$rosinstall_file"
}

function resolve_depends {
    local ws=$1
    rosdep install --from-paths "$ws" --ignore-src -y -r
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
    find "$ws/src" -type f -regex '.*\.\(rosinstall\|repo\|repos\)' -exec install_from_rosinstall {} "$ws/src/" \;
    resolve_depends "$ws/src"
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
    if [ "$ROS_VERSION" -eq 1 ]; then
        "/opt/ros/$ROS_DISTRO/env.sh" catkin_make_isolated -C "$ws" -DCATKIN_ENABLE_TESTING=1
        "/opt/ros/$ROS_DISTRO/env.sh" catkin_test_results --verbose "$ws"
    elif [ "$ROS_VERSION" -eq 2 ]; then
        cd "$ws" && colcon test
        colcon test-result --verbose
    fi
}

function install_workspace {
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    if [ "$ROS_VERSION" -eq 1 ]; then
        local ws=$1
        "/opt/ros/$ROS_DISTRO/env.sh" catkin_make_isolated -C "$ws" --install --install-space "/opt/ros/$ROS_DISTRO"
    elif [ "$ROS_VERSION" -eq 2 ]; then
        local ws=$1
        rm -rf "$ws/build"
        make_ros_entrypoint "$ws" > /ros_entrypoint.sh
        source "/ros_entrypoint.sh"
    fi
}

function make_ros_entrypoint {
    local ws=$1
cat <<- _EOF_ > /ros_entrypoint.sh
#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"
if [ -f "$ws/install/setup.bash" ]; then
    source "$ws/install/setup.bash"
fi
exec "\$@"
_EOF_

chmod +x /ros_entrypoint.sh
}

if [ -n "$*" ]; then
    "$@"
fi
