#!/usr/bin/env bash
# Build-time creation of the single, image-wide Python environment.
#
# Every Python layer (MuJoCo, Isaac Sim, Isaac Lab, cuRobo, Graphify) installs
# into this one environment; none of them creates its own. It is created by
# Dockerfile.venv right after the ROS layer, and by Dockerfile.user as a fallback
# for stacks that skip that layer (the CI images).
#
# PYTHON_VERSION is "system" (the distribution interpreter ROS is built for) or
# an X.Y version that a later layer pins, e.g. Isaac Sim's wheels.
set -euo pipefail
: "${VIRTUAL_ENV:=/opt/venv}" "${PYTHON_VERSION:=system}"

if [[ -x "$VIRTUAL_ENV/bin/python" ]]; then
    echo "Reusing $VIRTUAL_ENV ($("$VIRTUAL_ENV/bin/python" --version))"
else
    python=/usr/bin/python3
    [[ "$PYTHON_VERSION" != system ]] && python="$PYTHON_VERSION"
    # A matching distribution interpreter is preferred over a uv download, so
    # the environment stays binary compatible with the ROS Python packages.
    # System site packages keep apt's python3-* (rosdep, colcon, ...) visible.
    uv venv --python "$python" --python-preference system \
        --system-site-packages --seed "$VIRTUAL_ENV"
fi

version="$("$VIRTUAL_ENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [[ "$PYTHON_VERSION" != system && "$version" != "$PYTHON_VERSION" ]]; then
    echo "$VIRTUAL_ENV has Python $version; this stack needs $PYTHON_VERSION." >&2
    exit 1
fi

# Let the system interpreter (ros2, launch files, colcon-built nodes) import
# what is installed in the environment. The .pth goes into the *last* system
# site directory, so apt packages that ROS is compiled against keep precedence
# and the environment only adds what apt does not provide.
system_version="$(/usr/bin/python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [[ "$version" == "$system_version" ]]; then
    site_dir="/usr/lib/python${version}/dist-packages"
    install -d "$site_dir"
    "$VIRTUAL_ENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' \
        > "$site_dir/zz-opt-venv.pth"
    echo "System Python $system_version and ROS see $(cat "$site_dir/zz-opt-venv.pth")"
else
    echo "Python $version differs from the system Python $system_version:" \
         "ROS nodes cannot import packages from $VIRTUAL_ENV." >&2
fi
