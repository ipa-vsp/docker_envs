# Building and running development images

Run commands below from the repository root. Docker Engine, Buildx, Bash, and
network access for uncached dependencies are required. The local staged builder
uses the Docker driver so each intermediate image is available to the next stage.

## Build a stack

```bash
creator/scripts/create_env.sh             # interactive selection
creator/scripts/create_env.sh --dry-run   # prompts and plan only
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -u manipulation
creator/scripts/run_env.sh -p -o 24.04 -v jazzy -c -I -L
creator/scripts/run_env.sh -h             # complete CLI reference
```

Both front ends share `scripts/lib/stages.sh`. Stages run in this order:
base → ROS → MuJoCo → MoveIt/Nav2 → Isaac Sim → Isaac Lab → Zenoh → Gazebo → user.
These are dependent development images; each retains its parent's tools.

| Selection | Flags |
|---|---|
| Ubuntu / ROS | `-o 22.04\|24.04\|26.04`, `-v <distro>`; defaults: `24.04`, `rolling` |
| CUDA + cuDNN development base | `-c [version]` |
| MoveIt / Nav2 | `-u manipulation\|navigation\|both\|skip` |
| MuJoCo + Gymnasium | `-m [version]` |
| Isaac Sim / Isaac Lab | `-I [version]`, `-L [tag-or-branch]` |
| Isaac Lab installation | `-j auto\|python-env\|legacy`, `-e <selectors>` |
| Lab physics / visualization | `-B <physics>`, `-V <visualizer>` |
| Zenoh / Gazebo | `-z`, `-s` |
| Account | `-n <name>`, `-U <uid>`, `-G <gid>`; defaults: admin, host UID/GID |
| Naming | `-N <namespace>`, `-i <final-image>`; default namespace: `docker_envs` |

Version flags without a value resolve the latest available version. CUDA tags
come from Docker Hub, MuJoCo and Isaac Lab refs from GitHub, and Isaac Sim
versions from NVIDIA's Python index. Lookups have offline fallbacks; pin versions
for repeatable selections. Isaac Lab accepts tags and branches such as
`release/3.0.0`; the interactive builder also offers an RL framework selection.
Mutable branches and package repositories can still change between builds.

The builder validates Ubuntu/ROS combinations. Menu annotations describe the
configured CI matrix, not proof of upstream package availability or build success.
See the [workflow](../.github/workflows/ros2-staged.yml) for the publication matrix.

Tags accumulate the selected stages, for example:

```text
docker_envs/base:24.04
docker_envs/ros:24.04-jazzy
docker_envs/moveit:24.04-jazzy-moveit
docker_envs:24.04-jazzy-moveit
```

Local intermediate images are retained. CI pushes intermediate images between
jobs and removes them only after successful final publication. Registry build
caches live separately under `ghcr.io/ipa-vsp/docker_envs/buildcache`.

## Run a workspace

```bash
mkdir -p "$HOME/colcon_ws/src"
creator/scripts/run_env.sh -r -i docker_envs:24.04-jazzy-moveit -w "$HOME/colcon_ws"
# Additional shared group and cooperative file modes:
creator/scripts/run_env.sh -r -i docker_envs:24.04-jazzy-moveit \
  -w "$HOME/colcon_ws" -a 2000 -M 0002
```

The launcher requires an existing directory, mounts the whole workspace, sets it
as the working directory, and runs with your UID/GID. Use `-n`, `-U`, and `-G` to
override the account path and numeric identity. Paths with spaces are supported;
paths containing commas are rejected because of Docker's mount syntax.

No device privileges are enabled by default. `-g` selects all NVIDIA GPUs;
`-d /dev/ttyUSB0` exposes one device. `-a <gid>` adds a supplementary device or
shared-directory group and can be repeated. `-P` explicitly enables privileged
mode for a workload that requires it. GPU support requires a configured NVIDIA
container runtime on the host.

For X11, the launcher mounts the socket and existing `$XAUTHORITY` file (falling
back to `~/.Xauthority`) read-only. It does not modify X server access controls.
Cookie validity depends on your desktop session. For other display setups,
configure the appropriate socket and authentication explicitly in Compose.

The entrypoint loads installed ROS and selected Zenoh environments, applies
`WORKSPACE_UMASK` (default `0022`), and uses `exec` to preserve signals and exit
status. It never edits `.bashrc`, updates packages, pulls Git content, changes
ownership, or applies host sysctls. Interactive ROS shells also load the
system configuration when started with `docker exec`.

## Permissions and storage

On native Linux without user namespace translation, the container process's
numeric UID/GID determine bind-mount ownership. A bind mount hides the image's
files at its target and preserves the host files' existing ownership and modes.
Use existing host directories and Compose `bind.create_host_path: false` to
avoid accidental root-owned directory creation. See Docker's
[bind-mount reference](https://docs.docker.com/engine/storage/bind-mounts/).

Local builds personalize only the final account layer; published images use
`admin` with UID/GID `1000:1000`. Runtime `--user` aligns source-file ownership,
but does not create a passwd entry or make another account's home writable.
For software requiring a named account/home, rebuild the final user stage:

```bash
docker build -f creator/common/Dockerfile.user \
  --build-arg BASE_IMAGE=ghcr.io/ipa-vsp/docker_envs:24.04-jazzy \
  --build-arg ROS_DISTRO=jazzy \
  --build-arg USER_UID="$(id -u)" --build-arg USER_GID="$(id -g)" \
  -t docker_envs:jazzy-local .
```

Account setup runs only during the build. It reuses an existing numeric group,
handles Ubuntu's default UID 1000 login, and rejects other occupied UIDs. Root
UID/GID are rejected for development account creation. It does not delete
arbitrary system accounts. Avoid invoking the builder through sudo if you want
the default IDs to match your normal login.

Use binds for source and host-visible output; use named volumes for
container-owned caches and application data. Empty named volumes can inherit
pre-created image directory ownership on first use. Existing volumes retain
old ownership after a rebuild: changing the image UID does not migrate them.
Inspect a dedicated volume before deliberately migrating its ownership; never
apply automatic recursive ownership repair to a mounted repository.

For shared output, the host directory needs the shared GID and appropriate group
permissions. A setgid directory preserves that group on new children; `0002`
keeps group write permission when the application requests it. `--group-add`
and Compose `group_add` supply supplementary membership. Umask does not grant
access to existing files. See the [Compose service reference](https://docs.docker.com/reference/compose-file/services/).

Diagnose a failure by comparing host and container identities and mounts:

```bash
id
stat -c '%u:%g %a %n' "$HOME/colcon_ws"
# Inside the container:
id
stat -c '%u:%g %a %n' "$HOME/colcon_ws"
cat /proc/self/uid_map /proc/self/gid_map
# On the host, with the container name:
docker inspect <container> --format '{{json .Mounts}}'
```

Check parent-directory traversal permissions (`namei -l`), ACLs (`getfacl`), and
SELinux labels when applicable. Bind mounts have no generic `uid=`/`gid=`
ownership remapping option. Do not use `chmod 777` or privileged mode to hide an
identity mismatch.

Rootless Docker and `userns-remap` translate IDs: identical numbers inside and
outside do not necessarily represent the same host identity. Docker Desktop
adds VM file sharing on macOS/Windows. For WSL Linux workflows, keep source in
the distribution filesystem (for example `~/colcon_ws`); `/mnt/c` has Windows
filesystem permission semantics. Test ownership on your actual platform.

If large workspaces exhaust inotify watches, inspect the limits on the host and
adjust the host configuration deliberately. Container startup no longer writes
host-wide kernel settings.

## Isaac Sim and Isaac Lab

The creator supports both documented source-installation paths:
[legacy installer](https://isaac-sim.github.io/IsaacLab/release/3.0.0/source/setup/installation/index.html#installation-legacy-installer)
and [Python environment with Isaac Sim](https://isaac-sim.github.io/IsaacLab/release/3.0.0/source/setup/installation/index.html#installation-method-python-env).

```bash
# Kit-less Isaac Lab 3.x: no Isaac Sim layer.
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -L release/3.0.0 -j legacy -e 'newton,rl[rsl-rl],visualizer[newton]'

# Full Isaac Sim + Isaac Lab in the same Python environment.
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -I 6.1.0.0 -L release/3.0.0 -j python-env
```

`-j auto` (the default) chooses `python-env` when `-I` is selected and `legacy`
otherwise. The interactive `create_env.sh` offers Lab even if Sim was skipped,
shows the resulting method, and includes method, selectors, and namespace in
its reproducible command. Installation method and non-default selector hashes
are part of image tags so package variants do not overwrite each other.

`-e default` runs `./isaaclab.sh -i` without a selector. For 3.x, this installs
the core and upstream default optional packages. `-e core` installs core only;
custom selectors can request Newton, RL frameworks, visualizers, or OV runtimes.
Select Sim through `-I`, not the `isaacsim` package selector, to keep its version
and runtime metadata in the separate Sim layer.
The menu's `all` framework choice selects all four RL frameworks explicitly,
not every optional feature. Quote selectors containing brackets or commas.

The interactive creator also asks which physics and visualization support to
include. Equivalent command-line options are:

| Option | Choices |
|---|---|
| `-B` physics | `default`, `newton`, `ovphysx`, `both` (Newton + OV PhysX), `isaacsim`, `all` |
| `-V` visualization | `default`, `newton`, `rerun`, `viser`, `kit`, `all` (Newton + Rerun + Viser) |

Physics `isaacsim`/`all` and visualization `kit` require `-I`; the interactive
menus only offer them when Sim is selected. These menus target Lab 3.x. For 2.x,
the creator retains the existing Sim/Kit installation and package choices.

```bash
# Core plus an RL framework, OV PhysX, and the Viser web viewer:
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -L release/3.0.0 \
  -e 'rl[rsl-rl]' -B ovphysx -V viser

# Isaac Sim PhysX and Kit support:
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -I 6.1.0.0 \
  -L release/3.0.0 -e core -B isaacsim -V kit
```

Backend choices **add** to `-e`; `default` keeps the package selection unchanged.
Use `-e core` to avoid the upstream default optional packages. Adding to
`-e default` or `-e all` preserves their documented Lab 3.x optional packages
before appending the requested selectors. Custom `-e` choices also remain intact.
The summary shows the effective selectors passed to Docker, and image tags hash
that effective package selection.

These options install support, not a task's default physics or display. Select
those when launching the task (for example `physics=ovphysx` or `--viz viser`,
where supported by the task). GPU and display requirements still apply.

Kit-less builds create Python 3.12 under `/opt/isaac-venv`. Full builds reuse the
Sim venv and require Sim 6.x for Lab 3.x. Sim is installed with NVIDIA's extra
index, `unsafe-best-match`, and prereleases enabled; Torch 2.11.0 and TorchVision
0.26.0 use cu128 on amd64 and cu130 on arm64. The CUDA base version does not
select the wheel index. The old independent converter pin has been removed.
The current Sim fallback is 6.1.0.0; the Lab fallback is `release/3.0.0`.
Explicit 2.x tags remain available with a compatible Sim layer and their older
selectors (`none`, `rsl_rl`, etc.); Kit-less mode requires 3.x.

Python installations live under `/opt/uv/python` so the non-root development
account can access them. Neither venv replaces ROS's distribution Python:

```bash
isaac-activate
cd /opt/IsaacLab
# Full Sim verification (requires a compatible GPU/display):
isaaclab -p scripts/tutorials/00_sim/create_empty.py --viz kit
# Return to the ROS interpreter:
deactivate
```

Isaac Lab lives under `/opt/IsaacLab`. Keep writable training output in your
workspace or home and select an output directory supported by the training
script. Run the final image name printed by the builder with `run_env.sh -r`.
For Kit-less GPU workloads, pass `-g` explicitly; automatic GPU/cache setup is
triggered only by an Isaac Sim layer.

The launcher detects `ISAACSIM_VERSION` in a local image and adds GPU access and
persistent host directories under `~/docker/isaac-sim`. Override the root with
`STAGES_ISAAC_CACHE_ROOT`; `-X` disables automatic Isaac setup. Directories are
created by the calling user and must be writable by the selected container IDs.
The launcher fails if cache preparation fails.

| Host subdirectory | Container destination |
|---|---|
| `cache/ov` | `~/.cache/ov` |
| `cache/glcache` | `~/.cache/nvidia/GLCache` |
| `cache/computecache` | `~/.nv/ComputeCache` |
| `cache/pip` | `~/.cache/pip` |
| `cache/kit` | `$ISAACSIM_ROOT/kit/cache` from image metadata |
| `logs`, `config` | `~/.nvidia-omniverse/logs`, `~/.nvidia-omniverse/config` |
| `data`, `documents` | `~/.local/share/ov/data`, `~/Documents` |

These are wheel-installation paths; the NGC binary distribution uses a different
layout. Automatic setup passes the configured EULA/consent variables; use the
software under its applicable NVIDIA license. The
[fixed Compose example](../composer/isaacsim/README.md) uses named volumes instead.

## Build cache and layer validation

Keep stable dependency installation before frequently edited configuration. Clean
package indexes and temporary downloads in the instruction that creates them;
deleting them in a later layer does not remove their historical bytes. Use
`COPY --chown`/`--chmod` for copied files. Shell configuration is read-only to the
development account; startup scripts are executable. Build-only account setup
is bind-mounted into its RUN instruction instead of copied into the image.

MuJoCo, PyTorch, Isaac, and Zenoh builds use BuildKit caches for package or
compiler downloads. Those caches stay outside image layers. Registry cache
exports reuse completed layers, but do not transfer package-cache mount contents
to a fresh runner. `.dockerignore` excludes credentials, local editor/assistant
state, and generated output. Use BuildKit secret or SSH mounts for credentials.
See Docker's [build guidance](https://docs.docker.com/build/building/best-practices/).

These are development environments: compilers, headers, and source needed for
development remain available. For a production application, build in a separate
stage and copy only its required runtime artifacts into a smaller image with a
fixed non-root identity.

To refresh local dependencies, pull the external base and disable instruction
cache reuse. Do not apply `--pull` to local intermediate tags:

```bash
docker pull ubuntu:24.04
DOCKER_BUILD_EXTRA="--no-cache" creator/scripts/run_env.sh -b -o 24.04 -v jazzy
```

Zenoh defaults to the branch matching `ROS_DISTRO`. Override with
`DOCKER_BUILD_EXTRA="--build-arg ZENOH_REF=<ref>"` for a compatible specific ref.
Use image IDs/digests and pinned dependencies when comparing builds. Inspect
`docker image history <image>` and `docker image inspect <image>` for layer and
size changes. Repeating an unchanged build should reuse cached instructions;
change file contents, not just timestamps, when testing COPY invalidation.

## Checks

```bash
python3 -m unittest discover -s tests -v
creator/scripts/run_env.sh -p -o 24.04 -v jazzy -u manipulation
pre-commit run --all-files
```

Regression checks cover CI publication boundaries, cache separation, cleanup
selection, build failure propagation, launcher permissions, and entrypoint
behavior. They require Python, PyYAML, and `jq` and do not need Docker.

CI also builds the standalone user image with UID 12345/GID 23456 and runs
`test_image_permissions.py` against it. To reproduce locally:

```bash
docker build -f creator/common/Dockerfile.user \
  --build-arg USER_UID=12345 --build-arg USER_GID=23456 \
  -t docker-envs-permissions:test .
DOCKER_ENVS_TEST_IMAGE=docker-envs-permissions:test \
  python3 -m unittest discover -s tests -p 'test_image_permissions.py' -v
```

For an image smoke check of a full stack, run `id`, check `$HOME` is writable, create a disposable
bind-mounted file and inspect its host ownership, and verify command exit status.
Test actual ROS package discovery or Python imports for the stack being changed.
Full Isaac execution additionally requires a compatible NVIDIA GPU and driver.

## VS Code

A minimal `.devcontainer/devcontainer.json` using an image built for your IDs:

```json
{
  "name": "ROS 2",
  "image": "docker_envs:24.04-jazzy-moveit",
  "remoteUser": "admin",
  "workspaceFolder": "/home/admin/colcon_ws",
  "workspaceMount": "source=${localWorkspaceFolder},target=/home/admin/colcon_ws,type=bind"
}
```

Add only the display mounts, devices, and network settings your project needs.
No post-create ownership repair is required for a matching account.
