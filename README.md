# docker_envs

|  ROS2 |  foxy  | Galactic |
|-------|--------|----------|
| Azure Build Status| [![Build Status](https://dev.azure.com/IWT-Digitization/BuildEnv/_apis/build/status/ROS2?branchName=main&jobName=ROS2&configuration=ROS2%20Foxy)](https://dev.azure.com/IWT-Digitization/BuildEnv/_build/latest?definitionId=18&branchName=main) | [![Build Status](https://dev.azure.com/IWT-Digitization/BuildEnv/_apis/build/status/ROS2?branchName=main&jobName=ROS2&configuration=ROS2%20Galactic)](https://dev.azure.com/IWT-Digitization/BuildEnv/_build/latest?definitionId=18&branchName=main) | 

## Azure Kinect Docker
Currently Azure kinect driver only avialable for Ubuntu 18.04.
1. Build the image `cd azure` and `docker-compose up --build`. This should open the `k4aviewer`.
2. Please set your `ROS_IP` eviroment variable.
3. Run `docker-compose -f docker-compose-user.yml up`. Open two containers
    - First container launches ROS Azure Kinect driver.
    - Second Container launches RVIZ to visualize the camera data.

## Docker for ROS2 Foxy
todo

## Docker for KUKA IIWA7
todo

## Docker for ROS Melodic
todo
### Docker commands
1. Docker compose with file `docker-compose -f <file name> up --build`
### GUI with docker
1. Install [Nvidia docker2](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Add `runtime: nvidia` in docker compose
3. If there is problem with GUI in docker then run `xhost +` or `xhost -`
4. To avoid the vulnerablity use this instead of above,
    - `xhost +SI:localuser:$(id -un)`
    - To allow root in container access to X, run `xhost +SI:localuser:root`

### GUI with docker in Windows
1. Download [VcXsrv](https://sourceforge.net/projects/vcxsrv/) and install.
    - check the box **Disable access control**
2. 
```
environment: 
            - DISPLAY=172.16.17.132:0
```