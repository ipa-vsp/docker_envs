#!/usr/bin/env bash
# Load runtime environments without modifying the image or mounted workspace.
set -e

workspace_umask="${WORKSPACE_UMASK:-0022}"
if [[ ! "$workspace_umask" =~ ^[0-7]{3,4}$ ]]; then
    echo "WORKSPACE_UMASK must contain three or four octal digits" >&2
    exit 1
fi
umask "$workspace_umask"

if [[ -n "${ROS_DISTRO:-}" && -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
fi
if [[ "${RMW_IMPLEMENTATION:-}" == rmw_zenoh_cpp && -f /home/ws_rmw_zenoh/install/local_setup.bash ]]; then
    source /home/ws_rmw_zenoh/install/local_setup.bash
fi
if [[ $# -eq 0 ]]; then
    set -- /bin/bash
fi
exec "$@"
