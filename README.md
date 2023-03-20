# docker_envs

|       Images                  |     Build Status    |     Dockerhub    |
|-------------------------------|---------------------|------------------|
|       Galactic                |[![ROS2 Images](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml)| [prachandabhanu/build_env:galactic](https://hub.docker.com/layers/prachandabhanu/build_env/galactic/images/sha256-de9ea230f7c2d7978eca18db2a86b718121f8ef1bd914996716394fe5a76da6c?context=repo) |
|      Humble                 |[![ROS2 Images](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros2.yml)| [prachandabhanu/build_env:humble](https://hub.docker.com/layers/prachandabhanu/build_env/humble/images/sha256-7b7eaecc9aba8c03698fdffe138103033e8061edc039822f17abb5b4ea734827?context=repo) |
| Turtlebot3 with Noetic        |[![ROS Turtlebot Images](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros-turtlebot3.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/ros-turtlebot3.yml)| [prachandabhanu/build_env:noetic-turtlebot3-waffle](https://hub.docker.com/layers/prachandabhanu/build_env/noetic-turtlebot3-waffle/images/sha256-59aa966ee507cdedfecefa8071f9b7dabbf5c37b153683ac04cf1aea497d7b38?context=repo) [prachandabhanu/build_env:noetic-turtlebot3-burger](https://hub.docker.com/layers/prachandabhanu/build_env/noetic-turtlebot3-burger/images/sha256-1cdee6e3c50ae3b91cb8094168f9aef1d7cc1f8fa0c50998f08e5c75281b8e65?context=repo) |
|Pytorch 1.10.0 with Detectron2 |[![Pytorch with Detectron2](https://github.com/prachandabhanu/docker_envs/actions/workflows/pytorch-1-10.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/pytorch-1-10.yml)| [prachandabhanu/build_env:pytorch-1_10_0](https://hub.docker.com/layers/prachandabhanu/build_env/pytorch-1_10_0/images/sha256-d28064941741b92076b2654e31b721425f4daeb91c5e393c4cf4df296e8fbb0d?context=repo) |
| Clang Formatting               |[![clang-format](https://github.com/prachandabhanu/docker_envs/actions/workflows/docker-image.yml/badge.svg)](https://github.com/prachandabhanu/docker_envs/actions/workflows/docker-image.yml)|

## [Precommit hook](https://pre-commit.com/)
1. Install: `pip install pre-commit`
2. Check version: `pre-commit --version`
3. Setup workspace: `pre-commit install`
4. Run against all files: `pre-commit run --all-files` or `pre-commit run --all-files --hook-stage manual`

## Creating custom workspace
A new method is being created (under test) to adopt your docker workspaces flexibly.

`cd <your path>/docker_workspace/ros2_linux/script`

run: `./run_env.sh -h ` to get the options that are available for you.

| Options | Argument  | Description |
|---------|-----------|-------------|
|  -v     | `humble|rolling` | Select ROS version. Currently `humble` and `rolling` is available. ToDo: `noetic` |
|  -u     | `manipulation|navigation|both`|Select usage of the image such as for manipulation or navigation or both. ToDo: only base |
|  -s     | `true|false` | Enable simulation. Default it is disabled |
|  -i     | `name of the image` | Provide the Image Name |
|  -b     | `NULL` | Choose build mode |
|  -r     | `NULL` | Run mode |
|  -w     | `/path/to/your/workspace` | Attach your workspace only required while run (-r) |
|  -h     | `NULL` | Show help |

### Build
Example: `./run_env.sh -v rolling -u manipulation -i canopen_image -b`
### Run
Example: `./run_env.sh -v rolling -u manipulation -i canopen -w ~/ros_ws/colcon_can_ws -r`

### Dev Containers
todo

### [GUI with docker in Windows](https://github.com/prachandabhanu/docker_gui_windows11.git)
