#!/bin/bash

# Humble
cd ../../docker_workspaces/scripts
# ./run_env.sh -o 22.04 -v humble -u skip -i canopen_humble:test -b

# Rolling
./run_env.sh -o rolling -v rolling -u skip -i canopen_rolling:test -b

# Iron
# ./run_env.sh -o iron -v iron -u skip -i canopen_iron:test -b

# cd back to canopen
cd ../../composed_ws/canopen

# Check folder "../../../colcon_can_ws/src" exists
if [ -d "../../../colcon_can_ws/src" ]; then
    echo "Folder ../../../colcon_can_ws/src exists."
else
    echo "Folder ../../../colcon_can_ws/src does not exist."
    mkdir -p ../../../colcon_can_ws/src
    git clone https://github.com/ipa-vsp/ros2_canopen.git ../../../colcon_can_ws/src/
    exit 1
fi
