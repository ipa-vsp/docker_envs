Compose examples
================

``composer/`` holds Docker Compose files that run images from the
:doc:`creator <../_generated/creator>` (or the published images in
``ghcr.io/ipa-vsp/docker_envs``) for specific projects and machines.

Start with the template. The other directories are working examples for
particular robots, networks and host machines: review the hardware, network
and path settings before using one.

Maintained setups
-----------------

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Directory
     - Purpose
   * - :doc:`template <../_generated/composer-template>`
     - Minimal Compose file for any creator image, plus a custom
       ``Dockerfile.dev`` and a ``devcontainer.json``. **Start here.**
   * - :doc:`isaaclab <../_generated/composer-isaaclab>`
     - Persistent Isaac Sim / Isaac Lab service for a creator image, headless
       or with X11 (``compose.yml``, ``compose.x11.yml``).
   * - :doc:`isaacsim <../_generated/composer-isaacsim>`
     - Fixed Isaac Sim 6.0.1 + ROS 2 Jazzy example with its own
       ``Dockerfile``. Not built through the creator.
   * - :doc:`windows <windows>`
     - Services for Windows hosts (Docker Desktop + WSL 2 + WSLg), including
       ``wbcc-zed-windows`` for :doc:`editing with Zed <../usage/zed>`.
   * - ``macos-2``
     - Jazzy services for a macOS host: ``canopen_ws`` draws plain-Qt tools on
       the Mac desktop through XQuartz, and ``canopen_ws_vnc`` runs an X server
       in the container for ``rviz2`` and other OpenGL applications. See
       :ref:`GUI apps on macOS <gui-macos>`.
   * - :doc:`canopen <../_generated/composer-canopen>`
     - CANopen build and validation images for Rolling, Lyrical and Jazzy,
       with ``vcan`` checks and patches
       (:doc:`patch notes <../_generated/composer-canopen-patches>`).

Project and machine examples
----------------------------

These are kept as references. They are tied to specific projects, registries
or networks and may need edits before they run elsewhere.

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Directory
     - Contents
   * - ``coverless``
     - Humble + MoveIt test services (recovery, runtime, robot) on a
       dedicated bridge network, with ``.env`` settings.
   * - ``demo``
     - Humble and Humble + MoveIt demo services from the published images.
   * - ``macos``
     - Rolling and Humble services for a macOS host, a fixed bridge subnet and
       an OPC UA PLC simulator from a private registry. Its X11 settings are
       the Linux ones; for GUI apps follow
       :ref:`GUI apps on macOS <gui-macos>` or use ``macos-2``.
   * - ``mujoco``
     - Jazzy + MuJoCo image built from the local ``Dockerfile`` (PyTorch,
       Gymnasium, Stable-Baselines3, MuJoCo), with Linux and Windows services.
   * - ``rl``
     - Reinforcement-learning variant of the MuJoCo image (``rl-windows``).
   * - ``opcua``
     - Rolling service on a custom network with a published OPC UA port.
   * - ``pf_lidar``
     - Pepperl+Fuchs lidar driver images for Noetic, Humble and Rolling.
   * - ``rqt_gui``
     - Jazzy ``rqt`` GUI service on the host network, plus
       ``build_images.sh``.
   * - ``ur-sim``
     - Universal Robots UR5e simulator (URSim with the External Control URCap)
       and a Jazzy driver container.
   * - ``zenoh``
     - Two ``rmw_zenoh`` routers with their JSON5 session and router configs.
   * - ``rexroth``
     - ctrlX (arm64) runtime and development containers via QEMU, with SDK
       install scripts (:doc:`script notes <../_generated/composer-rexroth-scripts>`).
   * - ``vsp``
     - NGC ``isaac-lab:2.3.2`` and ``isaac-sim:5.1.0`` images, unmodified.
   * - :doc:`isaac <../_generated/composer-isaac>`
     - Legacy NGC Isaac Sim 4.5 reference.

Browse them on GitHub:
`composer/ <https://github.com/ipa-vsp/docker_envs/tree/main/composer>`_.

Conventions
-----------

Most services follow the same pattern as the images they run:

* ``entrypoint: /usr/local/bin/scripts/workspace-entrypoint.sh`` sources ROS
  (and Zenoh, when selected), applies ``WORKSPACE_UMASK`` and then runs the
  command. It never updates packages or changes the host.
* ``command: tail -f /dev/null`` keeps the container running so you can open
  shells with ``docker compose exec <service> bash``.
* ``network_mode: host`` makes ROS 2 discovery work without extra
  configuration. Containers with the same ``ROS_DOMAIN_ID`` see each other's
  topics.
* ``/tmp/.X11-unix`` is bind-mounted for GUI applications. That path only
  exists on Linux hosts — on Windows and macOS the display is wired up
  differently; see :doc:`graphical applications <../usage/gui>`.
* The workspace is bind-mounted at ``/home/admin/colcon_ws``. Ownership is
  never changed; see *Permissions and storage* in the
  :doc:`creator guide <../_generated/creator>`.

.. toctree::
   :hidden:

   ../_generated/composer-canopen-patches
   ../_generated/composer-rexroth-scripts
