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
            # For ROS1, you can directly use your provided logic or the logic from the given function.
            echo "Resolving dependencies for ROS1..."
            rosdep install --from-paths "$ws" --ignore-src -y -r
            ;;

        2)
            # For ROS2, similar to above. You can customize this.
            echo "Resolving dependencies for ROS2..."
            rosdep install --from-paths "$ws" --ignore-src -y -r
            ;;

        *)
            echo "Error: Unsupported ROS version. Please use ROS 1 or 2."
            return 1
            ;;
    esac
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
