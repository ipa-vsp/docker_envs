#!/usr/bin/env bash
set -eo pipefail
source "/opt/ros/$ROS_DISTRO/setup.bash"
source /home/admin/colcon_ws/install/setup.bash
if ! ip link show vcan0 >/dev/null 2>&1; then
    sudo ip link add vcan0 type vcan
fi
sudo ip link set vcan0 up
exec "$@"
