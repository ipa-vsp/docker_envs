# Use a creator image with Compose

- Docker / Compose commands → on the host
- Project commands (`uv sync`, `colcon build`) → inside the container, as the development user
- GPU / Isaac → use [composer/isaaclab](../isaaclab/README.md) instead

## 1. Build the base image

- From the `docker_envs` root, interactive:

```bash
creator/scripts/create_env.sh
```

- Keep account name `admin`
- IDs → values of `id -u` / `id -g` on the host (defaults)
- Final image name → short, e.g. `docker_envs:my-stack`
- Run as your normal login, not `sudo`
- Non-interactive equivalent:

```bash
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -n admin -U "$(id -u)" -G "$(id -g)" -i docker_envs:my-stack
```

- Isaac Lab → select it in the creator → [Isaac build options](../../creator/README.md#isaac-sim-and-isaac-lab)
- Use the **final** image (has the account), never `/base`, `/ros`, `/isaaclab` intermediates

## 2. Prepare the host

```bash
mkdir -p "$HOME/colcon_ws/src"
export HOST_WS="$HOME/colcon_ws"
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
export IMAGE=docker_envs:my-stack
```

## 3. Write `compose.yml`

- Any directory of your choice:

```yaml
services:
  dev:
    image: ${IMAGE:?Set IMAGE to your final creator image}
    user: "${LOCAL_UID:?Export LOCAL_UID}:${LOCAL_GID:?Export LOCAL_GID}"
    working_dir: /home/admin/colcon_ws
    init: true
    stdin_open: true
    tty: true
    environment:
      HOME: /home/admin
      WORKSPACE_UMASK: "0022"
    volumes:
      - type: bind
        source: ${HOST_WS:?Set HOST_WS to an existing absolute workspace path}
        target: /home/admin/colcon_ws
        bind:
          create_host_path: false
    command: sleep infinity
```

- Other account name → replace `/home/admin`
- ROS 2 with host nodes → add `network_mode: host` and `ipc: host`

## 4. Start, enter, stop

| Action | Command |
|---|---|
| Validate | `docker compose config --quiet` |
| Start | `docker compose up -d` |
| Shell | `docker compose exec dev bash` |
| Stop + remove | `docker compose down` |

- Workspace → stays on the host
- Other container changes → lost on recreation unless in a volume or Dockerfile

## 5. Work inside the container

```bash
id
cd ~/colcon_ws/src/my-project
# uv project (image with uv installed):
uv sync
uv run python --version
```

- Clone / generate projects as this user
- `sudo` → only for system packages
- `uv sync` → lockfile + environment must be writable → [uv syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- Existing permission failure → [repair steps](../../creator/README.md#uv-sync-permission-denied)
- Isaac images:
  - `isaac-activate` + `uv run --active ...` → image Isaac env (may update its packages)
  - plain `uv run ...` → project `.venv`
  - Details → [environment choice](../../creator/README.md#uv-project-env-or-active-isaac-env)

## 6. Extend the image (custom Dockerfile)

- Save [Dockerfile.dev](Dockerfile.dev) next to `compose.yml` → adds `tmux`, restores the account
- Replace `image:` in the `dev` service with:

```yaml
    image: my-project:dev
    pull_policy: never
    build:
      context: .
      dockerfile: Dockerfile.dev
      args:
        BASE_IMAGE: ${BASE_IMAGE:?Set BASE_IMAGE to your final creator image}
```

- Build + recreate:

```bash
export BASE_IMAGE=docker_envs:my-stack
docker compose build dev
docker compose up -d --force-recreate dev
docker compose exec dev bash
```

| Key | Meaning |
|---|---|
| `BASE_IMAGE` | existing creator image |
| `image:` | name of your custom result |
| `context` | relative to the Compose directory |
| `dockerfile` | relative to `context` |
| `pull_policy: never` | use the local build; build before starting |

- Reference → [Compose build](https://docs.docker.com/reference/compose-file/build/)
- Same extension as an override from the repository root:

```bash
export BASE_IMAGE=docker_envs:my-stack
export DEV_IMAGE=my-project:dev
docker compose -f composer/template/docker-compose.yml \
  -f composer/template/compose.build.yml build ros
docker compose -f composer/template/docker-compose.yml \
  -f composer/template/compose.build.yml run --rm ros
```

- Rules for a custom Dockerfile:
  - Project installs → after `USER ${USERNAME}`
  - Copied source → `COPY --chown=${USER_UID}:${USER_GID} my-project/ ./src/my-project/`
  - Source → inside the build context
  - Plain `COPY` → root-owned files even after `USER` → [COPY --chown](https://docs.docker.com/reference/dockerfile/#copy---chown---chmod)
  - Bind mount → hides copied files; cannot repair host `uv.lock` / `.venv`

## One-off shell with the repository template

```bash
docker compose -f composer/template/docker-compose.yml run --rm ros
```

- Service name → `ros`
- Other account name → export `CONTAINER_USER`
- Runtime IDs → must match the built account for a writable home
- Runtime `user:` → does not recreate the image account
