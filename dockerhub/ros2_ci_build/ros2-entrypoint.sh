#!/bin/bash

# Build ROS dependency
echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
source /opt/ros/${ROS_DISTRO}/setup.bash

export RCUTILS_COLORIZED_OUTPUT=1
sudo apt-get update
rosdep update

$@
