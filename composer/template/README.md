# Use a creator image with Compose

Run Docker and Compose commands on the host. Run project commands such as
`uv sync` inside the container as the development user.

## Build the base image

From the `docker_envs` repository root, run the interactive image creator:

```bash
creator/scripts/create_env.sh
```

The image creator is named `create_env.sh` in this repository. Select your
stack, keep `admin` as the account name, and use the values printed by the host's
`id -u` and `id -g` for its IDs. Give the final image a convenient name such as
`docker_envs:my-stack`. Run the builder as your normal host login.

For example, the equivalent non-interactive ROS build is:

```bash
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -n admin -U "$(id -u)" -G "$(id -g)" -i docker_envs:my-stack
```

Select Isaac Lab in the creator if your project needs it; see the
[Isaac build options](../../creator/README.md#isaac-sim-and-isaac-lab).
Use the final image, which includes the development account, rather than an
intermediate `/base`, `/ros`, or `/isaaclab` stage.

## Write a Compose file

Create the host workspace and export its path and your IDs:

```bash
mkdir -p "$HOME/colcon_ws/src"
export HOST_WS="$HOME/colcon_ws"
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
export IMAGE=docker_envs:my-stack
```

Save this as `compose.yml` in a directory of your choice:

```yaml
services:
  dev:
    image: ${IMAGE:?Set IMAGE to your final creator image}
    user: "${LOCAL_UID:?Export LOCAL_UID}:${LOCAL_GID:?Export LOCAL_GID}"
    working_dir: /home/admin/colcon_ws
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

In that directory, start the service and open a shell:

```bash
docker compose config --quiet
docker compose up -d
docker compose exec dev bash
```

Inside the container, check the identity and use your project:

```bash
id
cd ~/colcon_ws/src/my-project
# For a uv project, using an image with uv installed:
uv sync
uv run python --version
```

Clone or generate projects as this user. Use `sudo` only for operations that
require it, such as installing system packages. `uv sync` updates the project's
lockfile and environment; both must be writable. See
[uv's syncing reference](https://docs.astral.sh/uv/concepts/projects/sync/) and
[repairing an existing permission failure](../../creator/README.md#uv-sync-permission-denied).

For an Isaac image, `isaac-activate` followed by `uv run --active ...` selects
the image's Isaac environment and may update its installed packages. New creator
builds make that environment writable by the development account. Plain
`uv run ...` uses the project's `.venv` instead. See the
[environment examples](../../creator/README.md#use-the-project-environment-or-the-active-isaac-environment).

Run `exit` to leave the shell and `docker compose down` on the host to remove
the container. The bind-mounted workspace stays on the host. Changes elsewhere
in the container require a volume or a Dockerfile to survive recreation.

For a one-off shell using this repository's existing template (service `ros`):

```bash
docker compose -f composer/template/docker-compose.yml run --rm ros
```

If you chose a different account name, update `/home/admin` in your Compose
file, or export `CONTAINER_USER` when using the repository template. Numeric
runtime IDs must also match the built account for a writable home. A runtime
`user:` setting does not recreate the image account.

## Use a custom Dockerfile

Save [Dockerfile.dev](Dockerfile.dev) next to your `compose.yml`. It extends the
selected creator image with `tmux`, then restores the inherited development
user. Add this configuration to the `dev` service above, replacing its `image:`:

```yaml
    image: my-project:dev
    pull_policy: never
    build:
      context: .
      dockerfile: Dockerfile.dev
      args:
        BASE_IMAGE: ${BASE_IMAGE:?Set BASE_IMAGE to your final creator image}
```

Build and recreate the service from that directory:

```bash
export BASE_IMAGE=docker_envs:my-stack
docker compose build dev
docker compose up -d --force-recreate dev
docker compose exec dev bash
```

`BASE_IMAGE` is the existing creator image; `image:` names your custom result.
`context` is relative to the Compose directory, and `dockerfile` is relative
to that context. `pull_policy: never` uses the locally built result. Build it
explicitly before starting. See the
[Compose build reference](https://docs.docker.com/reference/compose-file/build/).

The repository provides the same extension as an override. From its root:

```bash
export BASE_IMAGE=docker_envs:my-stack
export DEV_IMAGE=my-project:dev
docker compose -f composer/template/docker-compose.yml \
  -f composer/template/compose.build.yml build ros
docker compose -f composer/template/docker-compose.yml \
  -f composer/template/compose.build.yml run --rm ros
```

Keep project installation commands after `USER ${USERNAME}` in a custom
Dockerfile. If copying source into an image, set its ownership explicitly, for
example `COPY --chown=${USER_UID}:${USER_GID} my-project/ ./src/my-project/`.
The source must be within the build context. Ordinary `COPY` creates root-owned
files even after `USER`; see the
[Dockerfile reference](https://docs.docker.com/reference/dockerfile/#copy---chown---chmod).
A bind mount hides copied files and preserves host ownership, so image build
instructions cannot repair an existing host lockfile or `.venv`.

## GPU workloads

The generic example above has no GPU or display configuration. For Isaac Sim,
use the [Isaac Compose example](../isaacsim/README.md) for GPU access and cache
volumes, or launch your creator image with `creator/scripts/run_env.sh -r`.
The launcher detects the Isaac Sim layer and configures its GPU and caches.
