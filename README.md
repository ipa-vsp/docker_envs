# docker_envs

|       Images                  |     Build Status    |
|-------------------------------|---------------------|
|       Galactic                |[![ROS2 Images](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml)|
|      Humble                 |[![ROS2 Images](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml)|
| Turtlebot3 with Noetic        |[![ROS Turtlebot Images](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros-turtlebot3.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros-turtlebot3.yml)|
|Pytorch 1.10.0 with Detectron2 |[![Pytorch with Detectron2](https://github.com/prachandabhanu/docker_envs/actions/workflows/pytorch-1-10.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/pytorch-1-10.yml)|
| Clang Formatting               |[![clang-format](https://github.com/prachandabhanu/docker_envs/actions/workflows/docker-image.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/docker-image.yml)|

## [Precommit hook](https://pre-commit.com/)
1. Install: `pip install pre-commit`
2. Check version: `pre-commit --version`
3. Setup workspace: `pre-commit install`
4. Run against all files: `pre-commit run --all-files` or `pre-commit run --all-files --hook-stage manual`

## Azure Kinect Docker
Currently Azure kinect driver only available for Ubuntu 18.04.
1. Build the image `cd azure` and `docker-compose up --build`. This should open the `k4aviewer`.
2. Please set your `ROS_IP` eviroment variable.
3. Run `docker-compose -f docker-compose-user.yml up`. Open two containers
    - First container launches ROS Azure Kinect driver.
    - Second Container launches RVIZ to visualize the camera data.

## Docker Compose
Reference: [link](https://docs.docker.com/compose/install/)
1. Run this command to download the current stable release of Docker Compose:
    ```
    sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    ```
2. Apply executable permissions to the binary:
    ```
    sudo chmod +x /usr/local/bin/docker-compose
    ```
    ---
    NOTE

    Note: If the command docker-compose fails after installation, check your path. You can also create a symbolic link to /usr/bin or any other directory in your path
    ---
For example:
    ```
    sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
    ```

3. Test Installation
    ```
    docker-compose --version
    ```

4. [Documentation GPU Integration](https://docs.docker.com/compose/gpu-support/)
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
4. To avoid the vulnerability use this instead of above,
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
