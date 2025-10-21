#!/bin/bash
# Build ROS dependency
echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
echo "export RCUTILS_COLORIZED_OUTPUT=1" >> ~/.bashrc

sudo apt-get update
rosdep update

# Add parse_git_branch function to .bashrc
echo 'parse_git_branch() {
    branch=$(git symbolic-ref --short HEAD 2>/dev/null)
    remote=$(git config --get branch."$branch".remote 2>/dev/null)
    if [ -n "$branch" ]; then
        echo -e "\[\033[0;33m\][$remote: \[\033[0;31m\]$branch\[\033[0;33m\]]"
    fi
}' >> ~/.bashrc

# Add PROMPT_COMMAND with parse_git_branch to .bashrc
echo 'PROMPT_COMMAND='\''PS1="${VIRTUAL_ENV:+(${VIRTUAL_ENV##*/}) }\\[\e[0;32m\\]\\u@\\h:\\[\\e[0;34m\\]\\w$(parse_git_branch)\\[\\e[0m\\]\\$ "'\''' >> ~/.bashrc

# if RMW_IMPLEMENTATION=rmw_zenoh_cpp is set, source the zenoh workspace
if [ "$RMW_IMPLEMENTATION" = "rmw_zenoh_cpp" ]; then
    echo "source /home/ws_rmw_zenoh/install/local_setup.bash" >> ~/.bashrc
fi

# Execute any command passed to the entrypoint
exec "$@"
