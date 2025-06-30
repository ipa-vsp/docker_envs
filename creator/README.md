# Create your own Docker workspace
# ==============================
- `cd scripts`. This directory contains the scripts to create a new Docker workspace.
- `./run_env.sh`. This script will create a new Docker workspace and run it.
    - `./run_env.sh -h` for help.

    ```bash
        Usage: ./run_env.sh -o 22.04|20.04 -v humble|rolling|noetic -u manipulation|navigation|both -s true|false -i image_name -b|-r -w dev_ws
            -o Select OS version 22.04 or 20.04
            -v Select ROS version
            -u Select usage of the image
            -s Enable simulation
            -i Image Name
            -b Build mode
            -r Run mode
            -w Attach your workspace only required while run (-r)
            -h Show help
    ```
- Example to create a new Docker workspace with Ubuntu 22.04, ROS Humble, Navigation and Simulation enabled.
    - `./run_env.sh -o 22.04 -v humble -u navigation -s true -i my_image -b`
- Example to run a Docker workspace with Ubuntu 22.04, ROS Humble, Navigation and Simulation enabled. However, you can attach your workspace to the container. This requires you to have a workspace in the same directory as the script. Or you can use the `-w` flag to specify the path to your workspace.
    - `./run_env.sh -o 22.04 -v humble -u navigation -s true -i my_image -w path_to_your_worspace -r`

### Automated builds on GitHub
ROS images are built and published using the
[`ros2-staged.yml`](../.github/workflows/ros2-staged.yml) workflow. The workflow
creates each layer in a separate job and pushes intermediate images. MuJoCo
layers are only built for Ubuntu&nbsp;24.04, while other layers cover all valid
Ubuntu and ROS combinations.

# Docker Workspaces using VSCode devcontainer
=============================================
- Create a new folder named `.devcontainer` in your workspace and creat a file named `devcontainer.json` in it.
- Copy the following and modify according to your requirements.

    ```json
    {
        "name": "ROS2 Development Container",
        "privileged": true,
        "remoteUser": "admin", // User name
        "image": "canopen_docker:latest", // Image name
        "containerName": "cntr_colcon_canopen_ws", // Container name
        "build": { // If you want to build the image from Dockerfile otherwise comment this section. Also, this requires you to have a Dockerfile in the same directory as the devcontainer.json
            "dockerfile": "DOCKERFILE"
            // "args": {
            //     "USERNAME": "vish"
            // }
        },
        "workspaceFolder": "/home/admin/colcon_ws", // Workspace path created in dockerfile.
        "workspaceMount": "source=${localWorkspaceFolder},target=/home/admin/colcon_ws,type=bind", // Bind your workspace to the container
        "customizations": {
            "vscode": {
                "extensions":[
                    "ms-vscode.cpptools",
                    "ms-vscode.cpptools-themes",
                    "ms-azuretools.vscode-docker",
                    "ms-vscode.cpptools-extension-pack",
                    "donjayamanne.python-extension-pack",
                    "josetr.cmake-language-support-vscode",
                    "visualstudioexptteam.vscodeintellicod",
                    "visualstudioexptteam.intellicode-api-usage-examples",
                    "ms-vscode.cmake-tools",
                    "twxs.cmake",
                    "ms-iot.vscode-ros",
                    "github.copilot"
                ]
            }
        },
        "containerEnv": { // Environment variables
            "DISPLAY": ":1",
            "ROS_LOCALHOST_ONLY": "1",
            "ROS_DOMAIN_ID": "42",
            "NVIDIA_VISIBLE_DEVICES": "all",
            "NVIDIA_DRIVER_CAPABILITIES": "all"
        },
        "runArgs": [
            "--net=host",
            "--gpus=all"
        ],
        "mounts": [
            "source=/tmp/.X11-unix,target=/tmp/.X11-unix,type=bind,consistency=cached",
            "source=/etc/timezone,target=/etc/timezone,type=bind",
            "source=/etc/localtime,target=/etc/localtime,type=bind"
        ],
        "postCreateCommand": "/usr/local/bin/scripts/workspace-entrypoint.sh && sudo chown -R admin:admin /home/admin/colcon_ws" // Caution: This will run the entrypoint script in the dockerfile. You can modify it according to your requirements. Remember to change user name and workspace path.
    }
    ```
- Example Dockerfile.

    ```dockerfile
    FROM myenvos:22.04.rolling.moveit

    RUN apt-get update && apt-get install -y \
            software-properties-common sudo \
            cmake clang curl\
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

    RUN apt-get update && apt-get install -y \
            can-utils net-tools \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

    RUN add-apt-repository ppa:lely/ppa && apt-get update \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

    RUN apt-get update && apt-get install -y \
            liblely-coapp-dev liblely-co-tools python3-dcf-tools pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

    RUN apt-get update \
            && pkg-config --cflags liblely-coapp \
            && pkg-config --libs liblely-coapp \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

    # Setup non-root admin user
    ARG USERNAME=admin
    ARG USER_UID=1000
    ARG USER_GID=1000

    # Reuse triton-server user as 'admin' user if exists
    RUN if [ $(getent group triton-server) ]; then \
            groupmod --gid ${USER_GID} -n ${USERNAME} triton-server ; \
            usermod -l ${USERNAME} -m -d /home/${USERNAME} triton-server ; \
            mkdir -p /home/${USERNAME} ; \
            sudo chown ${USERNAME}:${USERNAME} /home/${USERNAME} ; \
        fi

    # Create the 'admin' user if not already exists
    RUN if [ ! $(getent passwd ${USERNAME}) ]; then \
            groupadd --gid ${USER_GID} ${USERNAME} ; \
            useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} ; \
        fi

    # Update 'admin' user
    RUN echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
        && chmod 0440 /etc/sudoers.d/${USERNAME} \
        && adduser ${USERNAME} video && adduser ${USERNAME} sudo

    # Copy scripts
    RUN mkdir -p /usr/local/bin/scripts
    COPY *entrypoint.sh /usr/local/bin/scripts/
    RUN  chmod +x /usr/local/bin/scripts/*.sh

    USER ${USERNAME}
    WORKDIR /home/${USERNAME}
    RUN mkdir -p colcon_ws

    ENV USERNAME=${USERNAME}
    ENV USER_GID=${USER_GID}
    ENV USER_UID=${USER_UID}

    ENV NVIDIA_VISIBLE_DEVICES \
        ${NVIDIA_VISIBLE_DEVICES:-all}
    ENV NVIDIA_DRIVER_CAPABILITIES \
        ${NVIDIA_DRIVER_CAPABILITIES:+$NVIDIA_DRIVER_CAPABILITIES,}graphics
    ```

## Description of the devcontainer.json file
There is two way to utilize the image built by the script the devcontainer.
- During `./run_env.sh` exports the final image as my_image:latest. You can use this image in the devcontainer.json file. This is the recommended way. However, this might have necessary packages that you require.
- Use dockerfile to build the image. Main advantage of this is that you can add any packages that you require.
