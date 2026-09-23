#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob
: > /home/admin/colcon_ws/applied-patches.txt
for patch in /opt/canopen/patches/*.patch \
    /opt/canopen/patches/branches/"$CANOPEN_BRANCH"/*.patch \
    /opt/canopen/patches/"$ROS_DISTRO"/*.patch; do
    git -C /home/admin/colcon_ws/src/ros2_canopen apply --check "$patch"
    git -C /home/admin/colcon_ws/src/ros2_canopen apply "$patch"
    sha256sum "$patch" >> /home/admin/colcon_ws/applied-patches.txt
done
