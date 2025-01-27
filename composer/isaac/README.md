```
docker run --name isaac-sim --entrypoint bash -it --runtime=nvidia --gpus all -e "ACCEPT_EULA=Y" --rm --network=host     -e "PRIVACY_CONSENT=Y"     -v ~/docker/isaac-sim/cache/kit:/isaac-sim/kit/cache:rw     -v ~/docker/isaac-sim/cache/ov:/root/.cache/ov:rw     -v ~/docker/isaac-sim/cache/pip:/root/.cache/pip:rw     -v ~/docker/isaac-sim/cache/glcache:/root/.cache/nvidia/GLCache:rw     -v ~/docker/isaac-sim/cache/computecache:/root/.nv/ComputeCache:rw     -v ~/docker/isaac-sim/logs:/root/.nvidia-omniverse/logs:rw     -v ~/docker/isaac-sim/data:/root/.local/share/ov/data:rw     -v ~/docker/isaac-sim/documents:/root/Documents:rw     isaac-sim:humble
```

```
source /opt/ros/humble/setup.bash

RMW_IMPLEMENTATION=rmw_fastrtps_cpp
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/isaac-sim/exts/omni.isaac.ros2_bridge/humble/lib

OR

RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/isaac-sim/exts/omni.isaac.ros2_bridge/humble/lib
```
