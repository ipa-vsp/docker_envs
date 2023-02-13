#!/bin/bash
# Build ROS dependency
echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc
source /opt/ros/${ROS_DISTRO}/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

sudo apt-get update
rosdep update

$@
