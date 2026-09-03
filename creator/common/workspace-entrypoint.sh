#!/bin/bash
# Build ROS dependency
echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc

sudo apt-get update
rosdep update

# Apply the inotify limits baked into /etc/sysctl.d/99-inotify.conf. /proc/sys is
# read-only unless the container is privileged, so this is best effort. `sysctl -p`
# exits 0 even when a write is refused, so verify the value afterwards instead of
# trusting its exit status. When it did not take, the host limit is what applies
# and it has to be raised on the host.
if [ -f /etc/sysctl.d/99-inotify.conf ]; then
    sudo sysctl -p /etc/sysctl.d/99-inotify.conf >/dev/null 2>&1
    watches=$(cat /proc/sys/fs/inotify/max_user_watches)
    if [ "${watches}" -lt 524288 ]; then
        echo "WARN: fs.inotify.max_user_watches is ${watches}; large colcon"
        echo "      workspaces may fail with ENOSPC. Run the container with"
        echo "      --privileged, or raise it on the host:"
        echo "      echo fs.inotify.max_user_watches=524288 | sudo tee /etc/sysctl.d/99-inotify.conf"
        echo "      sudo sysctl --system"
    fi
fi

# NOTE: RCUTILS_COLORIZED_OUTPUT, parse_git_branch and the PROMPT_COMMAND are
# baked into the image bashrc (/etc/bash.bashrc via creator/scripts/bashrc), so
# they no longer need to be appended here.

# Make the Claude Code CLI (~/.local/bin) reachable from non-login shells such
# as `docker exec -it ... bash`, which read ~/.bashrc but never ~/.profile.
if ! grep -qF '$HOME/.local/bin' ~/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
fi
# `source ~/.bashrc` is a no-op here (it returns early for non-interactive
# shells), so export it directly for whatever this entrypoint exec's.
export PATH="$HOME/.local/bin:$PATH"

# Refresh the shared Claude config cloned into the workspace at build time.
# Best effort: a container with no network should still start. The directory is
# absent when something is bind-mounted over colcon_ws (run_env.sh does this),
# which hides the copy baked into the image.
CLAUDE_DIR="$HOME/colcon_ws/.claude"
if [ -d "${CLAUDE_DIR}/.git" ]; then
    if git -C "${CLAUDE_DIR}" pull --ff-only; then
        echo "Updated ${CLAUDE_DIR}"
    else
        echo "WARN: could not update ${CLAUDE_DIR}; using the version in the image"
    fi
fi

# if RMW_IMPLEMENTATION=rmw_zenoh_cpp is set, source the zenoh workspace
if [ "$RMW_IMPLEMENTATION" = "rmw_zenoh_cpp" ]; then
    echo "source /home/ws_rmw_zenoh/install/local_setup.bash" >> ~/.bashrc
fi

# Execute any command passed to the entrypoint
exec "$@"
