# Create your own Docker workspace

Local, layered image builds. Each stage is a separate Dockerfile and a separate
image, exactly like the staged CI workflow — so a rebuild can reuse unchanged instructions. A changed layer also invalidates
downstream layers that depend on it.

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
| 7. Isaac Lab | Tags **and** branches listed live from the Isaac Lab repository (4 of each), plus the RL framework to install |
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
  -L [<version>]    Isaac Lab layer; "latest", a tag (v2.3.2) or a branch
                    (main, release/3.0.0)                            (default: latest)
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
| Isaac Lab | [`common/Dockerfile.isaaclab`](common/Dockerfile.isaaclab) | Cloned at the selected tag or branch into `/opt/IsaacLab`, installed into the Isaac Sim venv |
| Zenoh | [`usage/Dockerfile.zenoh`](usage/Dockerfile.zenoh) | Builds `rmw_zenoh_cpp` |
| Gazebo | [`usage/Dockerfile.gazebo`](usage/Dockerfile.gazebo) | |
| User | [`common/Dockerfile.user`](common/Dockerfile.user) | Creates the non-root user, the workspace and the entrypoint |

### ROS distro / Ubuntu pairing

`stages.sh` only offers the distros that make sense for the Ubuntu release you
picked, and annotates two cases:

* **configured in CI** — the combination [`ros2-staged.yml`](../.github/workflows/ros2-staged.yml)
  is intended to publish. Check the actual workflow matrix and run status; local
  menu annotations are hints, not evidence that a build succeeded. Upstream may
  not publish every package for other combinations.
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

These layers are large — around 8 GB of wheels, `isaacsim-extscache-kit` alone
being 5.5 GiB — and Isaac Sim needs a GPU at run time (`./run_env.sh -r ... -g`,
or `docker run --gpus all`).

#### If the Isaac Sim layer times out

A single slow download failing the whole layer is the most likely way this build
breaks:

```
× Failed to download `isaacsim-robot==6.0.1.0`
╰─▶ operation timed out
```

That is a network problem, not a configuration one. The layer already raises
uv's per-request timeout to 600s and caps parallel downloads at 8 (`ARG
UV_HTTP_TIMEOUT` / `UV_CONCURRENT_DOWNLOADS`), and keeps uv's download cache in
a BuildKit cache mount — so **just run the same command again**. Docker discards
the failed layer but the cache mount survives, and the retry resumes from
whatever had already been fetched rather than re-downloading everything. The
earlier layers are cached too, so a re-run restarts at the one that failed.

On a particularly unreliable link, drop the concurrency further:

```bash
DOCKER_BUILD_EXTRA="--build-arg UV_CONCURRENT_DOWNLOADS=4" ./run_env.sh -b ... -I
```

### Running an Isaac Sim image

Isaac Sim needs a GPU and a set of persistent cache directories. Without the
caches it recompiles every shader on each start — the multi-minute "first
launch" that is easily mistaken for a hang.

`run_env.sh -r` detects an Isaac Sim image (from the `ISAACSIM_VERSION`
variable baked into the layer) and wires all of that up for you:

```bash
./run_env.sh -r -i docker_envs:24.04-jazzy-isaacsim6.0.1.0 -w ~/colcon_ws
```

That is the whole command. It adds `--gpus all`, the EULA variables, and mounts
the Omniverse caches under `~/docker/isaac-sim`. Override the cache location
with `STAGES_ISAAC_CACHE_ROOT`, or opt out entirely with `-X`.

Inside the container, Isaac Sim lives in its own virtualenv that is deliberately
kept off `PATH`:

```bash
isaac-activate                          # source /opt/isaac-venv/bin/activate
isaacsim                                # launch the app
python -c "from isaacsim import SimulationApp"
isaaclab -p scripts/tutorials/00_sim/create_empty.py   # if the Isaac Lab layer is present
```

Deactivate (or open a second shell) to get `ros2` and `colcon` back — they run on
the distro interpreter, not the Isaac one.

#### Why the mounts differ from the NVIDIA example

The [official container
instructions](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_container.html)
are written for `nvcr.io/nvidia/isaac-sim`, the **binary** distribution rooted at
`/isaac-sim`:

```bash
# NGC binary image — paths rooted at /isaac-sim
-v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw
-v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw
-e "ACCEPT_EULA=Y"
```

These images install Isaac Sim **from wheels** instead, so Kit resolves those
same directories from `$HOME`. Copying the NGC mounts verbatim would create an
unused `/isaac-sim` directory and leave the real caches unmounted. The paths
below are what this layer needs — the same layout [Isaac Lab's own
`docker-compose.yaml`](https://github.com/isaac-sim/IsaacLab/blob/main/docker/docker-compose.yaml)
uses for its pip container:

| Host (`~/docker/isaac-sim/…`) | Container | Holds |
|---|---|---|
| `cache/ov` | `~/.cache/ov` | Main Omniverse/shader cache |
| `cache/kit` | `$ISAACSIM_ROOT/kit/cache` | Kit SDK cache |
| `cache/glcache` | `~/.cache/nvidia/GLCache` | OpenGL shader cache |
| `cache/computecache` | `~/.nv/ComputeCache` | CUDA compute cache |
| `cache/pip` | `~/.cache/pip` | pip downloads |
| `logs` | `~/.nvidia-omniverse/logs` | Logs |
| `config` | `~/.nvidia-omniverse/config` | User config |
| `data` | `~/.local/share/ov/data` | Application data |
| `documents` | `~/Documents` | Saved stages/projects |

`$ISAACSIM_ROOT` is recorded on the image by `Dockerfile.isaacsim`, so the run
script resolves the Kit path without you knowing the Python version.

The EULA variable also differs: the pip distribution reads
`OMNI_KIT_ACCEPT_EULA` (baked into the image), while the NGC image reads
`ACCEPT_EULA`. Both are set, so the same invocation works if you later swap in
the NGC image.

#### Equivalent raw docker run

If you would rather not use `run_env.sh`, this is what it builds:

```bash
IMAGE=docker_envs:24.04-jazzy-isaacsim6.0.1.0
CACHE=~/docker/isaac-sim
mkdir -p $CACHE/{cache/{ov,kit,glcache,computecache,pip},logs,config,data,documents}

docker run --name isaac-sim -it --rm --network=host --privileged \
    --gpus all \
    -u $(id -u):$(id -g) \
    -e "OMNI_KIT_ACCEPT_EULA=YES" -e "ACCEPT_EULA=Y" -e "PRIVACY_CONSENT=Y" \
    -e "DISPLAY=$DISPLAY" -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    -v $CACHE/cache/ov:/home/admin/.cache/ov:rw \
    -v $CACHE/cache/pip:/home/admin/.cache/pip:rw \
    -v $CACHE/cache/glcache:/home/admin/.cache/nvidia/GLCache:rw \
    -v $CACHE/cache/computecache:/home/admin/.nv/ComputeCache:rw \
    -v $CACHE/cache/kit:/opt/isaac-venv/lib/python3.12/site-packages/isaacsim/kit/cache:rw \
    -v $CACHE/logs:/home/admin/.nvidia-omniverse/logs:rw \
    -v $CACHE/config:/home/admin/.nvidia-omniverse/config:rw \
    -v $CACHE/data:/home/admin/.local/share/ov/data:rw \
    -v $CACHE/documents:/home/admin/Documents:rw \
    -v ~/colcon_ws:/home/admin/colcon_ws:rw \
    $IMAGE bash
```

Run `xhost +local:` first if you want the GUI. Note `-u $(id -u):$(id -g)`:
the host cache directories are created by your user, so the container has to run
as that user to write to them.

### Version lookups

Every version list is resolved when you run the script, never baked into a
Dockerfile:

| Component | Source |
|-----------|--------|
| CUDA | Docker Hub tags for `nvidia/cuda`, filtered to `cudnn-devel-ubuntu<release>` |
| MuJoCo | Release tags of `google-deepmind/mujoco` |
| Isaac Sim | The `isaacsim` project on `pypi.nvidia.com` |
| Isaac Lab | Tags of `isaac-sim/IsaacLab`, plus its `main`, `develop` and `release/*` branches |

Each lookup has a timeout and a built-in fallback version, so selecting versions
still works offline. Building still needs network access for uncached base images,
packages, and source downloads.

## Automated builds on GitHub

ROS images are built and published using the
[`ros2-staged.yml`](../.github/workflows/ros2-staged.yml) workflow. The workflow
creates each layer in a separate job, pushing intermediate images to GHCR so the
next job can consume them. A final `cleanup-intermediates` job then deletes those
intermediate stage packages (`base`, `ros`, `moveit`) only after every required
final job succeeds. Registry caches persist in a separate `buildcache` package;
intermediate-image cleanup does not delete them.

The ROS workflow currently builds `24.04/rolling`, `24.04/kilted`, `24.04/jazzy`,
`22.04/humble`, and `26.04/lyrical`; MoveIt variants are configured for Kilted,
Jazzy, and Humble. ROS + MuJoCo/Nav2, CUDA, Isaac Sim, and Isaac Lab are local
options and are not built by this workflow.

PR validation builds each ROS stack sequentially on one runner using the Docker
driver, so later stages can use local intermediate tags. PyTorch PRs build the
Dockerfile's internal stages with the same Ubuntu base and versions as CI.
Neither PR job logs into GHCR, publishes images, exports registry caches, or runs
cleanup. Publishing runs are serialized within each workflow to protect shared
intermediate tags.

## Build cache and layer validation

Use Docker with the Buildx plugin and BuildKit enabled. The local build helpers
check for Buildx and explicitly enable BuildKit. Keep the default Docker driver
for the local staged builder: each stage must be available in the local image
store for the next stage. The scripts retain their existing options and image
names. All supported creator builds use the repository root as their context;
`.dockerignore` excludes local credentials, Git data, caches, and generated output
while retaining source inputs.

System dependencies precede shell configuration copies. A bashrc edit can reuse
system-package installation in its base stage; later stages inheriting the changed
base still rebuild. Entrypoint edits no longer repeat user setup and CLI
installation. APT indexes and repository installers are removed in the same RUN
that creates them. Zenoh's source, build tree, and logs never enter a committed
layer; its install tree and dependencies remain available.

Zenoh selects the upstream branch matching `ROS_DISTRO`, following the
[upstream source-build instructions](https://github.com/ros2/rmw_zenoh/tree/jazzy#source-installation).
The repository's default branch can require dependencies absent from older ROS
distributions. Override it with `DOCKER_BUILD_EXTRA="--build-arg ZENOH_REF=<branch-or-tag>"`
when building a specific compatible revision.

MuJoCo, PyTorch, and Isaac Lab use BuildKit package cache mounts; Isaac Sim keeps
its uv mount, and Zenoh mounts Cargo's registry and Git caches. These mounts live
in the builder, outside the image. Registry
`cache-to` exports reusable build layers, **not the contents of package cache
mounts**. A new CI runner can reuse a completed installation layer, but a cache
miss may still require downloading packages again. A local retry can reuse
package downloads while its builder cache remains available.

Non-PR CI builds use `type=registry` caches with `mode=max`, one reference per
workflow/stage/matrix under `ghcr.io/<owner>/<repository>/buildcache`. These are
separate from published image tags and excluded from intermediate cleanup. The
first build works without an existing cache. Cache storage can grow; manage its
retention separately from release images. See Docker's
[cache optimization](https://docs.docker.com/build/cache/optimize/) and
[registry cache](https://docs.docker.com/build/cache/backends/registry/) guidance.

Final images still default to root, retain development tools, and provide the
admin account with sudo. Use `docker run --user admin ...` or matching UID/GID
for mounted workspaces. Removing compilers or switching to a minimal runtime base
would change the purpose of these development environments.

For a fresh local build, pull the external base first, then disable instruction
cache reuse. Do not apply `--pull` to every local stage: intermediate images are
local tags, not registry artifacts.

```bash
# Run from the repository root; use the selected NVIDIA tag for a CUDA base.
docker pull ubuntu:24.04
DOCKER_BUILD_EXTRA="--no-cache" creator/scripts/run_env.sh -b -o 24.04 -v jazzy
```

`--no-cache` reruns instructions; `--pull` checks the referenced base for updates.
Neither makes mutable package repositories or remote branches reproducible.
Credentials required by future builds belong in BuildKit secret/SSH mounts,
not ARG, ENV, or copied files. `.dockerignore` is context filtering, not a
replacement for secret mounts.

### Measure a layer change

Record the base image ID, dependency versions, and architecture before comparing
an old checkout with the updated checkout. Use separate validation tags and the
same base for both. For a cold-cache experiment, create a disposable Buildx
builder; do not prune your normal Docker cache.

```bash
docker buildx create --name docker-envs-bench --driver docker-container
docker buildx build --builder docker-envs-bench --load --progress=plain \
  -f creator/common/Dockerfile.base --build-arg BASE_IMAGE=24.04 \
  -t docker-envs-bench:base .
# Repeat the identical command and compare cached instructions and elapsed time.
docker image inspect docker-envs-bench:base --format '{{.Size}}'
docker image history --no-trunc docker-envs-bench:base
# After measurements:
docker buildx rm docker-envs-bench
```

A shell-configuration cache test must change file **contents** in a disposable
checkout; `touch` alone does not invalidate Docker's COPY cache. Confirm that
package RUN instructions remain cached and the COPY reruns. For Zenoh, inspect
saved image layers as well as the merged filesystem: deleting files from the
merged filesystem does not prove their historical bytes are absent. Compare
local image sizes separately from compressed registry sizes; no fixed saving is
guaranteed.

### Repository checks

```bash
python3 -m unittest discover -s tests -v
bash -n creator/scripts/build_image.sh creator/scripts/build_pytorch_env.sh
creator/scripts/run_env.sh -p -o 24.04 -v jazzy -u manipulation
# With actionlint installed:
actionlint -shellcheck= .github/workflows/{ros2-staged,pytorch-staged,docker}.yml
```

The regression tests need Python, PyYAML, and `jq`; they validate PR publication
boundaries, cache separation, cleanup selection, and build-helper failure
handling without contacting a registry. Image smoke checks should additionally
cover ROS package discovery, MuJoCo/PyTorch imports, admin identity, and entrypoint
permissions. Isaac GPU execution requires suitable NVIDIA hardware and is a
separate runtime check.

### Measured validation (2026-09-09)

On Linux/amd64 with Docker 29.8.0 and Buildx 0.37.0, the original Jazzy Dockerfile
at commit `8402cef` and the updated Dockerfile were built against the same local
Ubuntu 24.04 development base. Their `dpkg-query -W` output was identical.

| Jazzy image | `docker image inspect --format '{{.Size}}'` |
|-------------|------------------------------------------------|
| Original Dockerfile | 6,572,967,062 bytes |
| Updated Dockerfile | 6,386,694,040 bytes |
| Reduction | 186,273,022 bytes (177.6 MiB; 2.8%) |

This comparison isolates the ROS layer cleanup; it is not a registry compressed
size measurement or a prediction for other stacks. Both builds encountered a
temporary DNS failure during rosdep initialization and completed on retry using
their cached package-installation layers.

Local smoke checks passed for the base and builder images, Jazzy, MoveIt, MuJoCo
3.12.0/Gymnasium 1.3.0, PyTorch 2.8.0 with TorchVision 0.23.0 and TorchAudio 2.8.0,
and the standalone and ROS user images. The user checks verified UID/GID 1000,
workspace access, executable entrypoint, and the retained root default.

Zenoh built from its Jazzy branch and initialized through `rclpy`. Inspection of
all 12 saved image layers found no Zenoh source/build/log trees or Cargo download
caches; the installed workspace remained intact. Content-only bashrc and
entrypoint edits reused their preceding installation layers. Docker context
filtering, seven regression tests, workflow linting, and shell syntax checks also
passed.

CUDA and Isaac Dockerfiles received build checks, not full GPU runtime tests.
Docker still warns about required `BASE_IMAGE` arguments without defaults in
stage-only Dockerfiles. Registry publication, remote cache reuse, cleanup, and
hosted GitHub Actions execution were not exercised locally.

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
