# Create your own Docker workspace

Local, layered image builds. Each stage is a separate Dockerfile and a separate
image, exactly like the staged CI workflow — so a rebuild only redoes the layers
that changed.

There are two front ends over the same build engine:

| Script | Use it when |
|--------|-------------|
| [`scripts/create_env.sh`](scripts/create_env.sh) | You want to be walked through the choices. Fetches the current MuJoCo / Isaac Sim / Isaac Lab / CUDA versions online and offers them as a menu. |
| [`scripts/run_env.sh`](scripts/run_env.sh) | You already know what you want, or you are scripting it. Also the script that runs a built image. |

Both source [`scripts/lib/stages.sh`](scripts/lib/stages.sh), which owns the
stage order, the online version lookups and the image naming, so the two front
ends always produce identically named images.

## Interactive build

```bash
cd creator/scripts
./create_env.sh              # walk through every stage and build
./create_env.sh --dry-run    # walk through the prompts, print the plan, build nothing
```

It asks one question per stage:

| Stage | Choices |
|-------|---------|
| 1. Ubuntu release | `22.04`, `24.04`, `26.04` |
| 2. Base image | plain `ubuntu:<release>`, or NVIDIA CUDA + cuDNN **devel**. CUDA versions are listed live from Docker Hub for the release you picked (newest first, e.g. `13.3.1`). |
| 3. ROS 2 distribution | Only the distros valid for that Ubuntu release; the ones CI builds are marked. |
| 4. Application stack | `manipulation` (MoveIt), `navigation` (Nav2), `both`, `skip` |
| 5. MuJoCo | Versions listed live from the MuJoCo release tags, plus the Gymnasium version |
| 6. Isaac Sim | Versions listed live from `pypi.nvidia.com` |
| 7. Isaac Lab | Tags listed live from the Isaac Lab repository, plus the RL framework to install |
| 8. Extra layers | Zenoh (`rmw_zenoh_cpp`), Gazebo |
| 9. User & naming | Username, UID, GID, image namespace, final image name |

Entry **1** in every version menu is the newest release found online, so accepting
the defaults always gives you the current version. Every menu also has an
`other (type a version)` escape hatch for pinning something specific, and each
lookup falls back to a built-in default if you are offline.

Before anything is built you get a summary, the full layer plan, and a
confirmation prompt. At the end it prints the equivalent `run_env.sh` command so
the same stack can be rebuilt without the prompts.

## Automatic image naming

Nothing has to be named by hand. Like
[`ros2-staged.yml`](../.github/workflows/ros2-staged.yml), each layer gets its
own image and the tag accumulates one component per selected stage:

```
docker_envs/base:24.04-cuda13.3.1
docker_envs/ros:24.04-cuda13.3.1-jazzy
docker_envs/mujoco:24.04-cuda13.3.1-jazzy-mujoco3.12.0
docker_envs/moveit:24.04-cuda13.3.1-jazzy-mujoco3.12.0-moveit
docker_envs/isaacsim:24.04-cuda13.3.1-jazzy-mujoco3.12.0-moveit-isaacsim6.0.1.0
docker_envs/isaaclab:24.04-cuda13.3.1-jazzy-...-isaaclab2.3.2
docker_envs:24.04-cuda13.3.1-jazzy-mujoco3.12.0-moveit-isaacsim6.0.1.0-isaaclab2.3.2   <- final
```

Intermediate layers live under the `<namespace>/<layer>` repository and the final
user image under `<namespace>` itself, mirroring CI. Versions are part of the tag
for the layers whose version you choose, so two builds differing only in, say,
MuJoCo version do not overwrite each other.

Override the namespace with `-N`, or the final name outright with `-i`. Unlike
CI, the local build **keeps** its intermediate layers — that is what makes a
rebuild cheap.

## Non-interactive build

```bash
Usage: run_env.sh -b|-r [options]

Modes:
  -b                Build the image stack
  -r                Run a container from the final image
  -p                Print the build plan and exit (dry run)

Stages:
  -o <os>           Ubuntu version: 22.04 | 24.04 | 26.04            (default: 24.04)
  -v <ros>          ROS distro: rolling|kilted|jazzy|humble|iron|lyrical
                                                                     (default: rolling)
  -c [<version>]    CUDA + cuDNN devel base; "latest" or e.g. 13.3.1 (default: latest)
  -u <usage>        manipulation | navigation | both | skip          (default: skip)
  -m [<version>]    MuJoCo layer; "latest" or e.g. 3.12.0            (default: latest)
  -I [<version>]    Isaac Sim layer; "latest" or e.g. 6.0.1.0        (default: latest)
  -L [<version>]    Isaac Lab layer; "latest" or e.g. v2.3.2         (default: latest)
                    Requires -I.
  -z                Add the Zenoh RMW layer
  -s                Add the Gazebo simulation layer

Image / user:
  -i <image>        Final image name (default: derived from the stages)
  -N <namespace>    Image namespace for derived names                (default: docker_envs)
  -n <username>     User created inside the image                    (default: admin)
  -U <uid>          UID for that user                                (default: current host UID)
  -G <gid>          GID for that user                                (default: current host GID)

Run mode:
  -w <path>         Workspace to bind-mount (required with -r)
  -g                Pass --gpus all to docker run
  -h                Show this help
```

The version flags take an **optional** argument: `-m` alone means "look up and
use the newest MuJoCo release", `-m 3.11.0` pins one.

```bash
cd creator/scripts

# ROS 2 Jazzy with MoveIt and the newest MuJoCo
./run_env.sh -b -o 24.04 -v jazzy -u manipulation -m

# See what a build would do, without building it
./run_env.sh -p -o 24.04 -v jazzy -c -I -L

# Humble on the CUDA 13.3.1 base with the newest Isaac Sim and Isaac Lab
./run_env.sh -b -o 22.04 -v humble -c 13.3.1 -I -L

# Run a built image with a workspace attached
./run_env.sh -r -i docker_envs:24.04-jazzy-moveit -w ~/colcon_ws -g
```

## Stages

| Stage | Dockerfile | Notes |
|-------|-----------|-------|
| Base (plain) | [`common/Dockerfile.base`](common/Dockerfile.base) | `ubuntu:<release>` plus the build/Python toolchain |
| Base (CUDA) | [`common/Dockerfile.cuda`](common/Dockerfile.cuda) | `nvidia/cuda:<version>-cudnn-devel-ubuntu<release>`; same package set as the plain base, so the ROS layers do not care which one they sit on |
| ROS 2 | [`ros2/Dockerfile.<distro>`](ros2/) | One file per distro |
| MuJoCo | [`common/Dockerfile.mujoco`](common/Dockerfile.mujoco) | Native distribution under `/opt/mujoco` **and** the Python bindings + Gymnasium in a venv at `/opt/venv` |
| MoveIt / Nav2 | [`usage/Dockerfile.moveit`](usage/Dockerfile.moveit), [`usage/Dockerfile.nav2`](usage/Dockerfile.nav2) | `both` stacks the two layers |
| Isaac Sim | [`common/Dockerfile.isaacsim`](common/Dockerfile.isaacsim) | `isaacsim[all,extscache]` wheels in a uv-managed venv at `/opt/isaac-venv` |
| Isaac Lab | [`common/Dockerfile.isaaclab`](common/Dockerfile.isaaclab) | Cloned at the selected tag into `/opt/IsaacLab`, installed into the Isaac Sim venv |
| Zenoh | [`usage/Dockerfile.zenoh`](usage/Dockerfile.zenoh) | Builds `rmw_zenoh_cpp` |
| Gazebo | [`usage/Dockerfile.gazebo`](usage/Dockerfile.gazebo) | |
| User | [`common/Dockerfile.user`](common/Dockerfile.user) | Creates the non-root user, the workspace and the entrypoint |

### ROS distro / Ubuntu pairing

`stages.sh` only offers the distros that make sense for the Ubuntu release you
picked, and annotates two cases:

* **built in CI** — the combination [`ros2-staged.yml`](../.github/workflows/ros2-staged.yml)
  publishes, so it is known-good. Anything else still builds, but upstream may
  not publish every package.
* **frozen upstream** — ROS Rolling has migrated to Ubuntu 26.04, so `24.04` +
  `rolling` still builds from the packages that exist today but will not receive
  further updates. Prefer `26.04` + `rolling`, or `24.04` + `jazzy`/`kilted`.

### CUDA base

The CUDA base uses the `cudnn-devel` flavour, which carries the CUDA toolkit and
the cuDNN headers, for all three Ubuntu releases:

```
nvidia/cuda:13.3.1-cudnn-devel-ubuntu22.04
nvidia/cuda:13.3.1-cudnn-devel-ubuntu24.04
nvidia/cuda:13.3.1-cudnn-devel-ubuntu26.04
```

The version list is read from Docker Hub at build time rather than hard-coded, so
newer CUDA releases show up on their own. Note that older CUDA versions are not
published for every Ubuntu release — Ubuntu 26.04 currently only has 13.3.1 — which
is exactly why the menu is filtered by the release you picked.

### Isaac Sim and Isaac Lab

The Isaac Sim wheels pin an exact CPython version that does not match the distro
interpreter on every Ubuntu release, so this layer builds its own
[uv](https://docs.astral.sh/uv/)-managed virtualenv at `/opt/isaac-venv` and
installs `torch`, `mujoco-usd-converter` and `isaacsim[all,extscache]` into it.

That venv is deliberately **not** on `PATH`: its interpreter is not the one ROS 2
was built against, so prepending it would break `ros2` and `colcon`. Activate it
explicitly instead — the image defines an alias:

```bash
isaac-activate           # == source /opt/isaac-venv/bin/activate
python -c "import isaacsim"
```

Isaac Lab is installed into that same venv and exposes an `isaaclab` alias for
`/opt/IsaacLab/isaaclab.sh`. It can only be selected together with Isaac Sim; the
scripts refuse the combination otherwise. Its reinforcement-learning
dependencies are opt-in (`none` by default, up to `all`) because they add a lot
of weight.

These layers are large — several GB of wheels — and Isaac Sim needs a GPU at run
time (`./run_env.sh -r ... -g`, or `docker run --gpus all`).

### Version lookups

Every version list is resolved when you run the script, never baked into a
Dockerfile:

| Component | Source |
|-----------|--------|
| CUDA | Docker Hub tags for `nvidia/cuda`, filtered to `cudnn-devel-ubuntu<release>` |
| MuJoCo | Release tags of `google-deepmind/mujoco` |
| Isaac Sim | The `isaacsim` project on `pypi.nvidia.com` |
| Isaac Lab | Tags of `isaac-sim/IsaacLab` |

Each lookup has a timeout and a built-in fallback version, so a build still works
without network access.

## Automated builds on GitHub

ROS images are built and published using the
[`ros2-staged.yml`](../.github/workflows/ros2-staged.yml) workflow. The workflow
creates each layer in a separate job, pushing intermediate images to GHCR so the
next job can consume them. A final `cleanup-intermediates` job then deletes those
intermediate stage packages (`base`, `ros`, `moveit`) once every final user image
has been published, so only the final images persist in the registry.

The CUDA, Isaac Sim and Isaac Lab layers described above are **local only** — the
staged workflow does not build them.

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
