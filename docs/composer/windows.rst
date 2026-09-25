Windows hosts
=============

``composer/windows/docker-compose.yaml`` runs creator images on Windows with
Docker Desktop (WSL 2 backend). GUI apps show on the Windows desktop through
WSLg, and the NVIDIA GPU is passed through.

Prerequisites
-------------

* Windows 10 21H2+ or Windows 11 with WSL 2 and WSLg.
* Docker Desktop with the WSL 2 backend.
* An NVIDIA driver for Windows. No driver inside WSL is needed; check with
  ``docker run --rm --gpus all ubuntu nvidia-smi``.
* The image used by the services. The ``docker_envs:24.04-cuda13.3.1-...``
  tags are local builds; build them with the
  :doc:`Windows image builder <../_generated/creator>` (``create_env.bat``)
  or change ``image:`` to a published tag.

Services
--------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Service
     - Purpose
   * - ``coverless-machine``
     - Published ``ghcr.io/ipa-vsp/docker_envs:jazzy`` image.
   * - ``wbcc-windows``
     - CUDA + Jazzy + MuJoCo + Isaac Lab image with ``../../../rox_fr3_demo``
       mounted at ``~/colcon_ws/src``.
   * - ``rsi-windows``
     - Same image with ``../../../rsi`` mounted at ``~/colcon_ws/rsi``.
   * - ``wbcc-zed-windows``
     - ``wbcc-windows`` plus an SSH server on port ``2222`` for
       :doc:`Zed <../usage/zed>` or any other SSH client.

Workspace paths are relative to ``composer/windows``, so
``../../../rox_fr3_demo`` is a folder next to the ``docker_envs`` checkout.

Usage
-----

.. code-block:: powershell

   cd composer\windows
   docker compose up -d wbcc-windows
   docker compose exec wbcc-windows bash
   docker compose down

How the display works
---------------------

Every service mounts ``/run/desktop/mnt/host/wslg`` at ``/tmp`` and sets:

.. code-block:: yaml

   DISPLAY: ":0"
   WAYLAND_DISPLAY: wayland-0
   XDG_RUNTIME_DIR: /tmp/runtime-dir
   PULSE_SERVER: /tmp/PulseServer

That path is where Docker Desktop exposes the WSLg X11, Wayland and
PulseAudio sockets, so ``rviz2``, ``gz sim`` and MuJoCo viewers open as
normal Windows windows. Because ``/tmp`` is the WSLg mount, do not keep
files there.

Host networking
---------------

``network_mode: host`` on Docker Desktop shares the network of Docker's VM.
Containers on the host network reach each other, which is what ROS 2
discovery needs. To reach a container port **from Windows** (for example
``localhost:2222`` for SSH), turn on *Docker Desktop → Settings → Resources →
Network → Enable host networking* (Docker Desktop 4.34+).

``composer/windows/Dockerfile``
-------------------------------

A standalone image recipe (PyTorch for CUDA 12.6, Gymnasium,
Stable-Baselines3, MuJoCo) on top of any ``BASE_IMAGE``. None of the
services above build it. To use it:

.. code-block:: powershell

   docker build -f composer\windows\Dockerfile `
     --build-arg BASE_IMAGE=ghcr.io/ipa-vsp/docker_envs:24.04-jazzy `
     --build-arg ROS_DISTRO=jazzy -t docker_envs:jazzy-rl composer\windows
