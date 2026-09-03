# Isaac Sim + ROS 2 Jazzy (compose example)

Isaac Sim installed **from wheels** (`pip`/`uv`) on top of the staged
`ghcr.io/ipa-vsp/docker_envs:24.04-jazzy` image, with a ROS 2 workspace bind
mounted.

For a version-selectable build of the same stack, see
[`creator/scripts/create_env.sh`](../../creator/scripts/create_env.sh); this
directory is a fixed, hand-pinned example.

## Setup

```bash
cp .env.example .env
${EDITOR:-vi} .env          # set LOCAL_UID/LOCAL_GID and HOST_WS
docker compose build        # first build pulls several GB of wheels
docker compose up -d
```

`LOCAL_UID`/`LOCAL_GID` must match your host user (`id -u`, `id -g`) or the
bind-mounted workspace will be read-only inside the container.

> `.env` is required. `HOST_WS` has no default on purpose — compose fails with a
> clear message rather than silently mounting a path that does not exist.

## Using the container

```bash
docker compose exec mp0700-6.0.1 bash
```

The venv is already on `PATH` (`/home/admin/colcon_ws/.venv`), so:

```bash
isaacsim                                       # launch the app
python -c "from isaacsim import SimulationApp" # or drive it from a script
```

For GUI output, allow X access on the host first:

```bash
xhost +local:
```

Tear down with `docker compose down`. The caches survive; add `-v` to drop them
too (see below).

## Caches

Isaac Sim compiles shaders on first launch. Without persistent caches that
happens on **every** container start — several minutes that is easily mistaken
for a hang. The compose file mounts nine named volumes to prevent it:

| Volume | Container path | Holds |
|---|---|---|
| `isaac-cache-ov` | `~/.cache/ov` | Main Omniverse/shader cache |
| `isaac-cache-kit` | `…/.venv/…/isaacsim/kit/cache` | Kit SDK cache |
| `isaac-cache-gl` | `~/.cache/nvidia/GLCache` | OpenGL shader cache |
| `isaac-cache-compute` | `~/.nv/ComputeCache` | CUDA compute cache |
| `isaac-cache-pip` | `~/.cache/pip` | pip downloads |
| `isaac-logs` | `~/.nvidia-omniverse/logs` | Logs |
| `isaac-config` | `~/.nvidia-omniverse/config` | User config |
| `isaac-data` | `~/.local/share/ov/data` | Application data |
| `isaac-docs` | `~/Documents` | Saved stages/projects |

```bash
docker volume ls | grep isaac      # inspect
docker compose down -v             # clear them (forces a full shader rebuild)
```

### Why these paths, and not the ones in the NVIDIA docs

The [official container
instructions](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_container.html)
describe `nvcr.io/nvidia/isaac-sim` — the **binary** distribution, rooted at
`/isaac-sim`:

```bash
# NGC binary image
-v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw
-v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw
-e "ACCEPT_EULA=Y"
```

Installed from wheels, Kit resolves those same directories from `$HOME` instead.
Copying the NGC mounts here would create an unused `/isaac-sim` directory and
leave the real caches unmounted. The `$HOME` layout above is what
[Isaac Lab's own `docker-compose.yaml`](https://github.com/isaac-sim/IsaacLab/blob/main/docker/docker-compose.yaml)
uses for its pip container.

The EULA variable differs too: the pip distribution reads
`OMNI_KIT_ACCEPT_EULA`, the NGC image reads `ACCEPT_EULA`. The compose file sets
both (plus `PRIVACY_CONSENT`) so it keeps working if the image is ever swapped.

### Named volumes, not host bind mounts

The container runs as `admin`, not root, and compose creates a *missing*
bind-mount source directory as **root** — which the container then cannot write,
so the caches would silently stay empty.

Named volumes avoid that, but only with one catch: a named volume inherits
ownership from the image path it covers **and only if that path already exists**.
It does not exist by default, so the Dockerfile pre-creates all nine directories
while running as `${USERNAME}`. Remove that `mkdir` and every cache silently
reverts to root-owned and unwritable — verify with:

```bash
docker compose exec mp0700-6.0.1 touch ~/.cache/ov/.probe
```

`creator/scripts/run_env.sh` takes the other route — host directories under
`~/docker/isaac-sim` — because it can create them as the calling user first.

## Gotchas

**Do not bind-mount the whole `colcon_ws`.** The venv lives at
`/home/admin/colcon_ws/.venv`, so mounting the entire workspace would hide it and
`isaacsim` would vanish. The compose file mounts only `colcon_ws/src` for this
reason. If you need the whole workspace mounted, move the venv out of it first
(e.g. to `/opt/isaac-venv`, which is where the `creator` layer puts it).

**The venv shadows the system Python.** `ENV PATH="$VIRTUAL_ENV/bin:$PATH"` in
the Dockerfile makes `python3` the venv interpreter, which has no ROS 2 packages
— `import rclpy` fails and `colcon build` may pick the wrong interpreter. Source
the ROS environment in a separate shell, or `deactivate`-equivalent by putting
`/usr/bin` first, when doing ROS work. The `creator` Isaac Sim layer avoids this
by keeping its venv off `PATH` behind an `isaac-activate` alias.

**Pinned versions — do not bump individually.** The Dockerfile pins
`torch==2.11.0` (cu130), `mujoco-usd-converter==0.2.0` and
`isaacsim[all,extscache]==6.0.1.0`. Each is constrained by Isaac Sim:

* `isaacsim-core==6.0.1.0` requires **exactly** `mujoco-usd-converter==0.2.0`.
  Installing the newer 0.5.0 from PyPI makes the Isaac Sim resolve fail with
  *"no version of mujoco-usd-converter==0.2.0 ... isaacsim-core cannot be used"*.
* It is installed in its own step, before `isaacsim`, on purpose: uv only
  considers the first index that carries a package, and `pypi.nvidia.com` does
  not publish 0.2.0. Pre-installing it from PyPI satisfies the constraint.
* `torch==2.11.0` lives in the `cu130` wheel index. `cu132` exists for CUDA 13.3
  but ships only torch >= 2.12, so the index is not interchangeable either.

Bump all three together against a known-good Isaac Sim release.
