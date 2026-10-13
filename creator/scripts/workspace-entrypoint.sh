#!/usr/bin/env bash
# Load runtime environments without modifying the image or mounted workspace.
set -e

workspace_umask="${WORKSPACE_UMASK:-0022}"
if [[ ! "$workspace_umask" =~ ^[0-7]{3,4}$ ]]; then
    echo "WORKSPACE_UMASK must contain three or four octal digits" >&2
    exit 1
fi
umask "$workspace_umask"

# The image ships no ~/colcon_ws. Mounting only ~/colcon_ws/src (or setting it
# as working_dir) makes Docker create the parent as root:root inside the
# container, where colcon cannot write build/ install/ log/. Reclaim that one
# directory - never recursively, never a mountpoint (that would be host data).
ws="${HOME:-}/colcon_ws"
if [[ $EUID -ne 0 && -d "$ws" && ! -w "$ws" ]] \
        && ! mountpoint -q "$ws" 2>/dev/null \
        && [[ "$(stat -c %u "$ws")" == 0 ]]; then
    sudo -n chown "$(id -u):$(id -g)" "$ws" 2>/dev/null || \
        echo "warning: $ws is root-owned; run: sudo chown $(id -u):$(id -g) $ws" >&2
fi
unset ws

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
