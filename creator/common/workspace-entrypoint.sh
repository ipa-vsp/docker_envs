#!/bin/bash
# Build ROS dependency
echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc

sudo apt-get update
rosdep update

# NOTE: RCUTILS_COLORIZED_OUTPUT, parse_git_branch and the PROMPT_COMMAND are
# baked into the image bashrc (/etc/bash.bashrc via creator/scripts/bashrc), so
# they no longer need to be appended here.

# if RMW_IMPLEMENTATION=rmw_zenoh_cpp is set, source the zenoh workspace
if [ "$RMW_IMPLEMENTATION" = "rmw_zenoh_cpp" ]; then
    echo "source /home/ws_rmw_zenoh/install/local_setup.bash" >> ~/.bashrc
fi

# Execute any command passed to the entrypoint
exec "$@"
