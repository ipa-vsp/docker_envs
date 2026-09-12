# Creator: build and run development images

- Run all commands from the repository root
- Needs Docker Engine, Buildx, Bash, network access for uncached dependencies
- Local staged builds use the Docker driver → each intermediate image feeds the next stage
- End-to-end Isaac guide → [docs/ISAAC_WORKFLOW.md](../docs/ISAAC_WORKFLOW.md)

## Build a stack

### Front ends

| Command | Purpose |
|---|---|
| `creator/scripts/create_env.sh` | interactive stage selection |
| `creator/scripts/create_env.sh --dry-run` | prompts + plan + replay command, no build |
| `creator/scripts/run_env.sh -b ...` | build from flags |
| `creator/scripts/run_env.sh -p ...` | print plan + replay command, no build |
| `creator/scripts/run_env.sh -h` | full CLI reference |

```bash
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -u manipulation
creator/scripts/run_env.sh -p -o 24.04 -v jazzy -c -I -L
```

### Stage order

- base → ROS → MuJoCo → MoveIt/Nav2 → Isaac Sim → Isaac Lab → Zenoh → Gazebo → user
- Each stage builds on its parent and keeps its tools
- Both front ends share `scripts/lib/stages.sh` → identical names and layers

### Build flags

| Selection | Flags |
|---|---|
| Ubuntu / ROS | `-o 22.04\|24.04\|26.04`, `-v <distro>`; defaults `24.04`, `rolling` |
| CUDA + cuDNN development base | `-c [version]` |
| MoveIt / Nav2 | `-u manipulation\|navigation\|both\|skip` |
| MuJoCo + Gymnasium | `-m [version]` |
| Isaac Sim / Isaac Lab | `-I [version]`, `-L [tag-or-branch]` |
| Isaac Lab installation | `-j auto\|python-env\|legacy`, `-e <selectors>` |
| Lab physics / visualization | `-B <physics>`, `-V <visualizer>` |
| Zenoh / Gazebo | `-z`, `-s` |
| Account | `-n <name>`, `-U <uid>`, `-G <gid>`; defaults `admin`, host UID/GID |
| Naming | `-N <namespace>`, `-i <final-image>`; default namespace `docker_envs` |

### Versions

- Version flag without value → latest available version
- Sources:
  - CUDA tags → Docker Hub
  - MuJoCo, Isaac Lab refs → GitHub
  - Isaac Sim versions → NVIDIA Python index
- Lookups offline → built-in fallbacks
- Isaac Lab → tags and branches (e.g. `release/3.0.0`)
- Interactive builder → also offers an RL framework choice
- Mutable branches + package repositories → can change between builds → pin versions
- Ubuntu/ROS combinations → validated; menu notes = CI matrix, not proof of upstream availability
- Publication matrix → [ros2-staged workflow](../.github/workflows/ros2-staged.yml)

### Image names

- Tags accumulate the selected stages:

```text
docker_envs/base:24.04
docker_envs/ros:24.04-jazzy
docker_envs/moveit:24.04-jazzy-moveit
docker_envs:24.04-jazzy-moveit
```

- Docker tag limit → 128 characters → use `-i` for long Isaac stacks
- Local intermediate images → kept
- CI → pushes intermediates between jobs, removes them only after successful final publication
- Registry build caches → `ghcr.io/ipa-vsp/docker_envs/buildcache` (separate)

### Replay a build

- `-p`, `--dry-run` and every build print the pinned replay command
- Final image stores it as label `org.docker_envs.build-command`

```bash
docker image inspect -f '{{index .Config.Labels "org.docker_envs.build-command"}}' <image>
```

## Run a container

### Modes

| Mode | Flag | Behavior |
|---|---|---|
| One-off shell | `-r` | `docker run --rm -it ... bash`; container removed on exit |
| Start | `-S` | background container (`sleep infinity`, `--init`); no-op when already running |
| Enter | `-E` | new shell via `docker exec` through the entrypoint; repeatable from any terminal |
| Stop | `-K` | `docker stop`; container removed |

```bash
mkdir -p "$HOME/colcon_ws/src"
creator/scripts/run_env.sh -S -H -i docker_envs:24.04-jazzy-moveit -w "$HOME/colcon_ws"
creator/scripts/run_env.sh -E -i docker_envs:24.04-jazzy-moveit
creator/scripts/run_env.sh -K -i docker_envs:24.04-jazzy-moveit
# Shared group + cooperative file modes:
creator/scripts/run_env.sh -r -i docker_envs:24.04-jazzy-moveit \
  -w "$HOME/colcon_ws" -a 2000 -M 0002
```

### Run flags

| Flag | Effect |
|---|---|
| `-i <image>` | image to run; required for every container mode |
| `-w <path>` | workspace → `~/colcon_ws`; required for `-r`, `-S`; must exist |
| `-C <name>` | container name; default derived from the image; pass it to `-E`/`-K` too |
| `-H` | `--network host --ipc host` |
| `-g` | all NVIDIA GPUs |
| `-d /dev/<dev>` | one device (repeatable) |
| `-a <gid>` | supplementary device/shared-directory group (repeatable) |
| `-M <umask>` | new-file mask; default `0022`; shared group `0002` |
| `-P` | privileged mode; only for workloads that require it |
| `-X` | skip Isaac auto-setup (GPU, caches, Lab outputs) |
| `-n`, `-U`, `-G` | account path + numeric identity (default host UID/GID) |

### Workspace

- Whole workspace mounted; working directory set to it
- Runs with your UID/GID
- Paths with spaces → supported
- Paths with commas → rejected (Docker mount syntax)
- Missing workspace → error, never created

### Devices and GPU

- No device privileges by default
- GPU support → configured NVIDIA container runtime on the host
- Isaac Sim images → GPU added automatically
- Kit-less Isaac Lab images → pass `-g`

### Display (X11)

- `/tmp/.X11-unix` → mounted read-only
- `DISPLAY` set + `xauth` installed → wildcard-family cookie written to `$XDG_RUNTIME_DIR/docker-envs-xauth-<uid>/xauth` (mode 700)
  - Directory mounted read-only at `/tmp/docker-envs-xauth`
  - Works on bridge networks (hostname mismatch)
  - `-E` refreshes it → GUI keeps working after a new login cookie
- Otherwise → existing `$XAUTHORITY` (fallback `~/.Xauthority`) mounted read-only
- X server access controls → never modified
- Other display setups → configure socket + auth explicitly in Compose

### Network

- Default → Docker bridge network
- `-H` → host network + host IPC → ROS 2 DDS discovery with the host, shared memory

### Entrypoint

- Loads installed ROS and selected Zenoh environments
- Applies `WORKSPACE_UMASK` (default `0022`), also for `-E` shells
- Uses `exec` → signals and exit status preserved
- Never edits `.bashrc`, updates packages, pulls Git content, changes ownership, applies host sysctls
- Interactive ROS shells → load the system configuration also with `docker exec`

## Claude Code and skills

- Final user stage installs Claude Code as the development user → [native installer](https://code.claude.com/docs/en/setup)
  - `curl -fsSL https://claude.ai/install.sh | bash`
  - `~/.local/bin` on `PATH`, also for non-interactive commands
- Build clones `https://github.com/ipa-vsp/.claude.git` → `~/colcon_ws/.claude`
- Existing `.claude` directory → preserved when extending an image
- Host workspace mounted at `~/colcon_ws` → hides the image clone → set it up once inside the container:

```bash
cd ~/colcon_ws
git clone https://github.com/ipa-vsp/.claude.git
```

- Keep an existing `.claude` directory
- Start `claude` from the workspace → follow the sign-in prompts
- Shell startup → no downloads, no workspace changes
- Interactive Bash banner → user, numeric UID/GID, workspace, ROS distro, Claude availability
- Root shells → permissions warning; non-root shells → reminder to match host IDs
- `NO_COLOR=1` → no banner colors

## Isaac Sim and Isaac Lab

### Installation methods

| Method | Flag | Meaning | Docs |
|---|---|---|---|
| Python env with Isaac Sim | `-j python-env` (needs `-I`) | Lab installed into the Sim venv | [upstream](https://isaac-sim.github.io/IsaacLab/release/3.0.0/source/setup/installation/index.html#installation-method-python-env) |
| Legacy / Kit-less | `-j legacy` (no `-I`) | Lab 3.x in its own Python 3.12 venv | [upstream](https://isaac-sim.github.io/IsaacLab/release/3.0.0/source/setup/installation/index.html#installation-legacy-installer) |
| Auto (default) | `-j auto` | `python-env` with `-I`, else `legacy` | |

```bash
# Kit-less Isaac Lab 3.x: no Isaac Sim layer.
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -L release/3.0.0 -j legacy -e 'newton,rl[rsl-rl],visualizer[newton]'

# Full Isaac Sim + Isaac Lab in the same Python environment.
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -I 6.1.0.0 -L release/3.0.0 -j python-env
```

- `create_env.sh` → offers Lab even without Sim; shows the method; replay command includes method, selectors, namespace
- Method + non-default selector hash → part of the image tag → variants never overwrite each other

### Package selectors (`-e`)

| Value | Result |
|---|---|
| `default` | `./isaaclab.sh -i` without selector → core + upstream default optional packages (3.x) |
| `core` | core only |
| custom, e.g. `'newton,rl[rsl-rl]'` | Newton, RL frameworks, visualizers, OV runtimes |

- Isaac Sim → select with `-I`, never with the `isaacsim` selector (keeps version + runtime metadata in the Sim layer)
- Menu `all` framework choice → all four RL frameworks, not every optional feature
- Quote selectors containing brackets or commas

### Physics and visualization (`-B`, `-V`)

| Option | Choices |
|---|---|
| `-B` physics | `default`, `newton`, `ovphysx`, `both` (Newton + OV PhysX), `isaacsim`, `all` |
| `-V` visualization | `default`, `newton`, `rerun`, `viser`, `kit`, `all` (Newton + Rerun + Viser) |

```bash
# Core plus an RL framework, OV PhysX, and the Viser web viewer:
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -L release/3.0.0 \
  -e 'rl[rsl-rl]' -B ovphysx -V viser

# Isaac Sim PhysX and Kit support:
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -I 6.1.0.0 \
  -L release/3.0.0 -e core -B isaacsim -V kit
```

- `isaacsim`/`all` physics and `kit` visualization → require `-I`; menus offer them only with Sim
- Menus target Lab 3.x; Lab 2.x keeps the Sim/Kit installation and package choices
- Backend choices **add** to `-e`; `default` keeps the selection unchanged
- `-e core` → only the selected extras
- Adding to `-e default` or `-e all` → keeps the documented 3.x optional packages first
- Custom `-e` → kept intact
- Summary → shows the effective selectors; image tag hashes them
- These options install support only → choose physics/display at task launch (e.g. `physics=ovphysx`, `--viz viser`)
- GPU and display requirements still apply

### Python environments

- Kit-less builds → Python 3.12 venv at `/opt/isaac-venv`
- Full builds → reuse the Sim venv; Lab 3.x requires Sim 6.x
- Sim install → NVIDIA extra index, `unsafe-best-match`, prereleases enabled
- Torch 2.11.0 + TorchVision 0.26.0 → cu128 on amd64, cu130 on arm64
- CUDA base version → does not select the wheel index
- Fallbacks → Sim `6.1.0.0`, Lab `release/3.0.0`
- Lab 2.x tags → still available with a compatible Sim layer and old selectors (`none`, `rsl_rl`, ...); Kit-less needs 3.x
- Python installs → `/opt/uv/python` (readable by the non-root account)
- Neither venv replaces ROS's distribution Python

```bash
isaac-activate
cd /opt/IsaacLab
# Full Sim verification (requires a compatible GPU/display):
isaaclab -p scripts/tutorials/00_sim/create_empty.py --viz kit
# Return to the ROS interpreter:
deactivate
```

### Persistent Isaac data (automatic in `-r`/`-S`)

- Triggered by image metadata (`ISAACSIM_VERSION`, `ISAACLAB_DIR`) → no flag needed
- `-X` → disables it
- Directories → created by the calling user; must be writable by the container IDs
- Preparation fails → launch fails
- Isaac Sim cache root → `~/docker/isaac-sim` (override `STAGES_ISAAC_CACHE_ROOT`)
- Isaac Lab output root → `~/docker/isaac-lab` (override `STAGES_ISAACLAB_OUTPUT_ROOT`)
- Path list shared by launcher, image and Compose → [`creator/common/isaac-cache-dirs.txt`](common/isaac-cache-dirs.txt)

| Host subdirectory | Container destination |
|---|---|
| `isaac-sim/cache/ov` | `~/.cache/ov` |
| `isaac-sim/cache/pip` | `~/.cache/pip` |
| `isaac-sim/cache/glcache` | `~/.cache/nvidia/GLCache` |
| `isaac-sim/cache/computecache` | `~/.nv/ComputeCache` |
| `isaac-sim/logs`, `isaac-sim/config` | `~/.nvidia-omniverse/logs`, `~/.nvidia-omniverse/config` |
| `isaac-sim/data`, `isaac-sim/documents` | `~/.local/share/ov/data`, `~/Documents` |
| `isaac-sim/cache/kit/<Sim version>` | `$ISAACSIM_ROOT/kit/cache` (one per Sim version) |
| `isaac-lab/logs`, `isaac-lab/data_storage` | `$ISAACLAB_DIR/logs`, `$ISAACLAB_DIR/data_storage` |

- Wheel-installation paths; the NGC binary image uses a different layout
- Final image pre-creates all of them as the account → empty named volumes are writable
- EULA/consent variables passed automatically → use under the applicable NVIDIA license
- Kit cache moved to per-version folders → first start after upgrading recompiles once
- Isaac Lab source → `/opt/IsaacLab`; keep other training output in your workspace or home
- Compose alternative with named volumes → [composer/isaaclab](../composer/isaaclab/README.md)

## Permissions and storage

### Rules

- Native Linux without user-namespace translation → container UID/GID = bind-mount ownership
- Bind mount → hides image files at the target; keeps host ownership and modes
- Use existing host directories; Compose `bind.create_host_path: false` → no root-owned surprises
- Reference → [bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
- Local builds → personalize only the final account layer
- Published images → `admin`, UID/GID `1000:1000`
- Runtime `--user` → aligns source ownership, but no passwd entry and no writable foreign home
- Named account/home with other IDs → rebuild the final user stage:

```bash
docker build -f creator/common/Dockerfile.user \
  --build-arg BASE_IMAGE=ghcr.io/ipa-vsp/docker_envs:24.04-jazzy \
  --build-arg ROS_DISTRO=jazzy \
  --build-arg USER_UID="$(id -u)" --build-arg USER_GID="$(id -g)" \
  -t docker_envs:jazzy-local .
```

### Account setup (build time only)

- Reuses an existing numeric group
- Replaces Ubuntu's default UID 1000 `ubuntu` login; rejects other occupied UIDs
- Rejects root UID/GID
- Never deletes arbitrary system accounts
- Invoke the builder without `sudo` → default IDs match your login

### Volumes vs binds

- Binds → source + host-visible output
- Named volumes → container-owned caches + application data
- Empty named volume → inherits pre-created image directory ownership on first use
- Existing volume → keeps old ownership after a rebuild; changing the image UID does not migrate it
- Inspect a volume before migrating its ownership; never recursively repair a mounted repository

### Shared group output

- Host directory → shared GID + group permissions
- setgid directory → new children keep the group
- Umask `0002` → keeps group write when the application requests it
- `--group-add` / Compose `group_add` → supplementary membership
- Umask → does not grant access to existing files
- Reference → [Compose services](https://docs.docker.com/reference/compose-file/services/)

### Diagnose

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

- Also check → parent traversal (`namei -l`), ACLs (`getfacl`), SELinux labels
- Bind mounts → no `uid=`/`gid=` remapping option
- Never use `chmod 777` or privileged mode to hide an identity mismatch

### Platform notes

- Rootless Docker / `userns-remap` → IDs translated; equal numbers ≠ same host identity
- Docker Desktop (macOS/Windows) → extra VM file sharing
- WSL → keep source in the Linux filesystem (`~/colcon_ws`); `/mnt/c` has Windows semantics
- Test ownership on your actual platform
- Large workspaces exhausting inotify watches → raise host limits deliberately; startup no longer changes host sysctls

### uv sync: Permission denied

- Symptom → `uv sync` cannot write `~/colcon_ws/src/<project>/uv.lock`
- Cause → existing root-owned file or `.venv`; a writable directory + matching UID is not enough
- Inspect inside the container:

```bash
cd ~/colcon_ws/src/<project>
id
stat -c '%u:%g %a %n' . uv.lock .venv
find .venv -xdev -uid 0 -gid 0 -print
```

- Repair (personal project, confirmed accidental root-owned files, run as `admin` with IDs matching the host owner):

```bash
sudo chown --no-dereference --from=0:0 "$(id -u):$(id -g)" uv.lock
sudo find .venv -xdev -uid 0 -gid 0 \
  -exec chown --no-dereference "$(id -u):$(id -g)" {} +
uv sync
```

- No `.venv` → skip the `.venv` command
- Shared files / other owner → decide the intended owner first
- Changes also affect host files (bind mount); contents and the rest of the repository untouched
- Rebuilding the image or container → cannot repair existing bind-mount contents
- Prevent it:
  - Build with your host IDs
  - Clone, generate and `uv sync` as the development account
  - `COPY --chown` for project files in a custom Dockerfile
  - Never `sudo uv sync` (creates more root-owned files)
  - Keep system packages and project commands under their users → [custom Compose example](../composer/template/README.md#6-extend-the-image-custom-dockerfile)
- Isaac Lab projects:
  - Editable installs regenerate metadata under `$ISAACLAB_DIR` (`/opt/IsaacLab`)
  - Final user layer owns that tree, including existing `.egg-info`
  - `$ISAAC_VENV` also owned by the account → `uv run --active` can update it
  - Base Python + unrelated system paths keep their ownership
  - Older image with permission errors → rerun the saved build command, rebuild custom Compose images, recreate the service
  - First rebuild of an older Isaac image → several minutes + a large layer (venv copied on ownership change); later builds reuse it

### uv: project env or active Isaac env

| Goal | Commands | Effect |
|---|---|---|
| Project `.venv` (isolated) | `uv run python scripts/list_envs.py --show_presets` | Isaac env unchanged |
| Image Isaac env | `isaac-activate` → `uv run --active python scripts/list_envs.py --show_presets` | syncs project deps into `$VIRTUAL_ENV` |
| Deps already installed | `isaac-activate` → `python scripts/list_envs.py --show_presets` | no sync |

- `--active` → may replace image package versions; needs write access to the whole venv incl. `*.dist-info`
- Reference → [uv run](https://docs.astral.sh/uv/reference/cli/#uv-run)
- Compose `user:` or `HOME` changes → do not transfer ownership of installed files
- Keep runtime IDs = built account; mount only the workspace, never the whole home
- Runtime package changes → survive restarts, lost on recreation → put them in a custom Dockerfile
- Directory name ≠ write access → a root-owned venv under `/home/admin` fails the same way
- Custom install paths → install there from the start; update source references + cache mounts
- Never move an existing venv (absolute interpreter paths) → [venv docs](https://docs.python.org/3/library/venv.html)

## Build cache and layer validation

- Stable dependency installs before frequently edited configuration
- Clean package indexes + downloads in the same `RUN` that creates them
- `COPY --chown` / `--chmod` for copied files
- Shell configuration → read-only for the account; startup scripts executable
- Build-only helpers → bind-mounted into their `RUN`, not copied
- MuJoCo, PyTorch, Isaac, Zenoh → BuildKit cache mounts for downloads (outside image layers)
- Registry cache exports → reuse layers, not cache-mount contents
- `.dockerignore` → excludes credentials, editor/assistant state, generated output
- Credentials → BuildKit secret or SSH mounts
- Reference → [build best practices](https://docs.docker.com/build/building/best-practices/)
- Production apps → separate build stage, copy only runtime artifacts, fixed non-root identity
- Refresh dependencies (never `--pull` local intermediate tags):

```bash
docker pull ubuntu:24.04
DOCKER_BUILD_EXTRA="--no-cache" creator/scripts/run_env.sh -b -o 24.04 -v jazzy
```

- Zenoh → branch matching `ROS_DISTRO`; override `DOCKER_BUILD_EXTRA="--build-arg ZENOH_REF=<ref>"`
- Compare builds → image IDs/digests + pinned dependencies
- Inspect → `docker image history <image>`, `docker image inspect <image>`
- Unchanged rebuild → should reuse every cached instruction
- Test `COPY` invalidation → change file contents, not timestamps

## Checks

```bash
python3 -m unittest discover -s tests -v
creator/scripts/run_env.sh -p -o 24.04 -v jazzy -u manipulation
pre-commit run --all-files
```

- Covers → CI publication boundaries, cache separation, cleanup selection, build failure propagation, launcher modes and permissions, entrypoint, Isaac cache-path sync
- Needs Python, PyYAML, `jq`; no Docker
- Image permission test (CI builds UID 12345 / GID 23456):

```bash
docker build -f creator/common/Dockerfile.user \
  --build-arg USER_UID=12345 --build-arg USER_GID=23456 \
  -t docker-envs-permissions:test .
DOCKER_ENVS_TEST_IMAGE=docker-envs-permissions:test \
  python3 -m unittest discover -s tests -p 'test_image_permissions.py' -v
```

- Full-stack smoke check:
  - `id`, `$HOME` writable
  - Create a bind-mounted file → check host ownership
  - Command exit status preserved
  - ROS package discovery / Python imports for the changed stack
  - Isaac → compatible NVIDIA GPU + driver

## VS Code

- Minimal `.devcontainer/devcontainer.json` for an image built with your IDs:

```json
{
  "name": "ROS 2",
  "image": "docker_envs:24.04-jazzy-moveit",
  "remoteUser": "admin",
  "workspaceFolder": "/home/admin/colcon_ws",
  "workspaceMount": "source=${localWorkspaceFolder},target=/home/admin/colcon_ws,type=bind"
}
```

- Add only the display mounts, devices and network settings you need
- Matching account → no post-create ownership repair
