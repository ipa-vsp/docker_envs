# docker_envs

|       Images                  |     Build Status    |     Dockerhub    |
|-------------------------------|---------------------|------------------|
|      ROS2                 |[![ROS2 Images](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2.yml)| [prachandabhanu/build_env:humble](https://hub.docker.com/layers/prachandabhanu/build_env/humble/images/sha256-7b7eaecc9aba8c03698fdffe138103033e8061edc039822f17abb5b4ea734827?context=repo) |
|Pytorch 2.0.1 with Detectron2 and Pytorch3D |[![Pytorch with Detectron2 and Pytorch3D](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch-2-0-1.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch-2-0-1.yml)| [prachandabhanu/build_env:pytorch-1_10_0](https://hub.docker.com/layers/prachandabhanu/build_env/pytorch-1_10_0/images/sha256-d28064941741b92076b2654e31b721425f4daeb91c5e393c4cf4df296e8fbb0d?context=repo) |
| Clang Formatting               |[![Clang-Format](https://github.com/ipa-vsp/docker_envs/actions/workflows/ci-formater.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/ci-formater.yml)|
| Pre-commit formatting         | [![Pre-commit Formatting](https://github.com/ipa-vsp/docker_envs/actions/workflows/pre-formater.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/pre-formater.yml) |

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

### Attaching your workspace
To attach your workspace other than `UID` is `1000` of your host machine, you need to run the following command in your host machine to change the ownership of the workspace.
``` sudo chown -R 1000:1000 || sudo chmod -R u+w ```

### [GUI with docker in Windows](https://github.com/prachandabhanu/docker_gui_windows11.git)
