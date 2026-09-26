Graphical applications
======================

``rviz2``, ``rqt``, ``gz sim`` and the MuJoCo viewer run **inside** the
container but draw **on your desktop**. In X11 terms the container is the
client and your machine runs the server, so three things have to line up:

#. a **route** from the container to an X server,
#. **permission** for the container to use that server,
#. a **renderer** the server accepts.

How the route is made differs per host, and that is where most failures come
from.

.. list-table::
   :header-rows: 1
   :widths: 14 30 56

   * - Host
     - Route
     - ``DISPLAY``
   * - Linux
     - Bind-mount ``/tmp/.X11-unix``
     - ``$DISPLAY`` from the host (usually ``:0``)
   * - Windows
     - Bind-mount the WSLg socket directory
     - ``:0`` — see :doc:`Windows hosts <../composer/windows>`
   * - macOS, plain Qt
     - XQuartz listening on **TCP**
     - ``host.docker.internal:0``
   * - macOS, OpenGL
     - X server **inside** the container, exported over VNC
     - ``:99`` — XQuartz cannot serve these; see :ref:`gui-macos-vnc`

Linux
-----

Mount the socket and pass the display through:

.. code-block:: yaml

   environment:
     DISPLAY: "${DISPLAY:?Set DISPLAY}"
     QT_X11_NO_MITSHM: "1"
   volumes:
     - /tmp/.X11-unix:/tmp/.X11-unix:ro

Most services in ``composer/`` already do this. If the container is refused
with ``Authorization required``, the server is using an authority cookie the
container cannot read. Either allow local clients for the session:

.. code-block:: bash

   xhost +local:

or hand the container a wildcard cookie, which is what
``composer/isaaclab/compose.x11.yml`` does with ``XAUTH_DIR``:

.. code-block:: bash

   mkdir -p /tmp/docker-envs-xauth
   xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' \
     | xauth -f /tmp/docker-envs-xauth/xauth nmerge -
   export XAUTH_DIR=/tmp/docker-envs-xauth

For hardware OpenGL add the GPU (``-g`` in ``run_env.sh``, or ``deploy``
reservations in Compose). Without a GPU, set
``LIBGL_ALWAYS_SOFTWARE=1`` so Mesa's software renderer is used instead of
failing on a missing driver.

Windows
-------

Docker Desktop with the WSL 2 backend exposes the WSLg X11, Wayland and
PulseAudio sockets, so GUI windows appear as ordinary Windows windows with no
extra server to install. The settings and the caveat about ``/tmp`` are in
:doc:`Windows hosts <../composer/windows>`.

.. _gui-macos:

macOS
-----

macOS has no X server and **no ``/tmp/.X11-unix``**, and Docker Desktop runs
containers inside a Linux VM, so a mounted socket can never work. Install
XQuartz, make it listen on TCP, and point the container at the Mac over the
network.

1. Install XQuartz
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   brew install --cask xquartz     # or the installer from xquartz.org

Log out and back in once after the first install, so ``/opt/X11/bin`` lands on
your ``PATH``. Check that both halves are present — the command line tools and
the application:

.. code-block:: bash

   ls /opt/X11/bin/Xquartz
   ls -d /Applications/Utilities/XQuartz.app

If ``/opt/X11`` exists but the ``.app`` does not, the install is broken: X will
never start and ``open -a XQuartz`` fails with *Unable to find application
named 'XQuartz'*. Reinstall with ``brew reinstall --cask xquartz``.

2. Let it listen on TCP
^^^^^^^^^^^^^^^^^^^^^^^

XQuartz ships with TCP turned off, which blocks the container from connecting
at all:

.. code-block:: bash

   defaults write org.xquartz.X11 nolisten_tcp 0

``defaults write org.xquartz.X11 enable_iglx -bool true`` turns on indirect
GLX. It is worth setting, but be aware it is **not** enough for ``rviz2`` or
``gz sim`` (:ref:`gui-macos-vnc`).

Quit XQuartz completely and start it again; the settings are only read at
startup.

.. code-block:: bash

   open -a XQuartz
   lsof -nP -iTCP:6000 | grep LISTEN     # must print a line

Display ``:0`` is TCP port ``6000``. No listener means XQuartz is not running,
or it started before the ``defaults write``.

3. Allow the container in
^^^^^^^^^^^^^^^^^^^^^^^^^

``host.docker.internal`` resolves to an **IPv6** address inside the container
(something like ``fdc4:f303:9324::254``), and Docker Desktop's user-mode network
stack delivers the connection to the Mac from the IPv6 loopback, ``::1``. So
authorize that, not ``127.0.0.1``:

.. code-block:: bash

   xhost + ::1

``xhost + 127.0.0.1`` adds only ``INET:localhost`` and leaves the container
refused with ``Authorization required, but no authorization protocol
specified``. Check which entries are actually in place:

.. code-block:: bash

   xhost
   # access control enabled, only authorized clients can connect
   # INET6:localhost      <- this is the one that matters
   # INET:localhost

This is per XQuartz session — repeat it after every restart. ``xhost +`` on its
own also works but accepts every host that can reach port ``6000``, including
other machines on your network.

4. Point the container at the Mac
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

   environment:
     - DISPLAY=host.docker.internal:0
     - QT_X11_NO_MITSHM=1
     - LIBGL_ALWAYS_SOFTWARE=1

Do **not** mount ``/tmp/.X11-unix`` and do **not** forward the host's
``$DISPLAY``: on a Mac that variable holds a launchd socket path such as
``/var/run/com.apple.launchd.RYIevVJz1l/org.xquartz:0``, which is meaningless
inside Linux. ``host.docker.internal`` resolves under both bridge and
``network_mode: host``.

This gets plain-Qt applications such as ``rqt`` onto the Mac desktop. It does
**not** get ``rviz2``, ``gz sim`` or the MuJoCo viewer there — see
:ref:`gui-macos-vnc` for those.

``composer/macos-2/docker-compose.yml`` has this as the ``canopen_ws``
service:

.. code-block:: bash

   cd composer/macos-2
   docker compose up -d canopen_ws
   docker compose exec canopen_ws bash
   rqt

5. Check it before blaming the app
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Two tools in the images test the path without any of ROS's complexity:

.. code-block:: bash

   xdpyinfo | head -3      # connection and screen geometry
   xmessage hello          # a window actually opens

If ``xdpyinfo`` works and ``rviz2`` does not, the problem is GL, not the
display.

.. _gui-macos-vnc:

rviz2, Gazebo and MuJoCo on macOS: use VNC instead
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

XQuartz gets OpenGL applications no further than a connection. Ogre — the
renderer behind ``rviz2``, ``gz sim`` and the MuJoCo viewer — asks for a GLX
framebuffer configuration that XQuartz does not provide, even with
``enable_iglx`` on, and Mesa gives up:

.. code-block:: text

   No matching fbConfigs or visuals found
   glx: failed to create drisw screen
   [ERROR] [rviz2]: Unable to create the rendering window after 100 tries

That is a limit of XQuartz's GLX, not a configuration mistake, and no
``LIBGL_*`` setting works around it. The fix is to stop involving XQuartz:
run a real X server **in the container**, render into it with Mesa's
``llvmpipe``, and export that framebuffer over VNC. macOS has a VNC client
built in, so nothing needs installing on the Mac.

``composer/macos-2`` has this ready as the ``canopen_ws_vnc`` service:

.. code-block:: bash

   cd composer/macos-2
   docker compose up -d --build canopen_ws_vnc
   open vnc://localhost:5901          # or Finder → Go → Connect to Server
   docker compose exec canopen_ws_vnc bash
   rviz2                              # window appears in the VNC session

The pieces, if you are adding this to another service:

* ``Dockerfile.vnc`` installs ``xvfb`` and ``x11vnc`` on top of any
  ``docker_envs`` image.
* ``vnc-entrypoint.sh`` starts ``Xvfb`` with ``+extension GLX`` and
  ``-noreset``, waits for it with ``xdpyinfo`` rather than a blind ``sleep``,
  starts ``x11vnc``, then chains to the image's own
  ``workspace-entrypoint.sh`` so ROS and ``WORKSPACE_UMASK`` are set up as
  usual. Tunables: ``VNC_DISPLAY``, ``VNC_GEOMETRY``, ``VNC_DEPTH``,
  ``VNC_PORT``, ``VNC_PASSWORD``.
* ``DISPLAY=:99`` is set in the service's ``environment``, not only exported by
  the entrypoint, because ``docker compose exec`` does **not** run the
  entrypoint — without it every shell you open is missing ``DISPLAY``.
* The service does not use ``network_mode: host``. On Docker Desktop the "host"
  network is the Linux VM's, so the Mac cannot reach a port there and
  ``ports:`` is ignored. Containers on the bridge network still discover each
  other's ROS 2 topics.
* The port is published as ``127.0.0.1:5901:5901``, so it is not exposed to
  your network and ``x11vnc`` can run without a password. Set ``VNC_PASSWORD``
  if you widen that binding.

Rendering is software, so expect a busy ``rviz2`` scene to feel sluggish; a
smaller ``VNC_GEOMETRY`` helps.

Qt's own VNC server
^^^^^^^^^^^^^^^^^^^

For plain-Qt tools only, Qt can serve its window directly with no extra
packages:

.. code-block:: yaml

   ports:
     - "127.0.0.1:5900:5900"
   environment:
     - QT_QPA_PLATFORM=vnc

This is enough for ``rqt``. It does **not** help ``rviz2``: Qt reports
``QVncServer created on port 5900`` and Ogre then still fails with
``Couldn't open X display``, because it opens the X display itself. Use the
``Xvfb`` service above for anything OpenGL.

Troubleshooting
---------------

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - Symptom
     - Cause and fix
   * - ``could not connect to display /var/run/com.apple.launchd.*/org.xquartz:0``
     - The Mac's ``$DISPLAY`` was forwarded into the container. Use
       ``DISPLAY=host.docker.internal:0`` (:ref:`macOS <gui-macos>`).
   * - ``could not connect to display host.docker.internal:0``
     - XQuartz is not running, or not listening on TCP. Check
       ``lsof -nP -iTCP:6000``, then ``nolisten_tcp 0`` and restart it.
   * - ``Authorization required, but no authorization protocol specified``
     - The server answered and refused the client — TCP is fine, the ACL is
       not. On macOS ``xhost + ::1`` (the connection arrives over IPv6
       loopback, so ``127.0.0.1`` does not cover it); on Linux
       ``xhost +local:`` or a wildcard cookie.
   * - ``Could not load the Qt platform plugin "xcb"``
     - Almost always the display above, not a missing plugin — Qt reports the
       connection failure first, then this. Fix the display.
   * - ``RenderingAPIException: Couldn't open X display`` from ``rviz2``
     - Ogre could not reach X at all. Confirm the display with ``xdpyinfo``.
       Common cause on macOS: ``QT_QPA_PLATFORM=vnc``, which serves Qt but
       leaves Ogre with no display.
   * - ``No matching fbConfigs or visuals found`` / ``failed to create drisw
       screen`` / ``Unable to create the rendering window after 100 tries``
     - The display works but its GLX cannot satisfy Ogre. On macOS this is
       XQuartz's limit; switch to the VNC service (:ref:`gui-macos-vnc`). On
       Linux, install Mesa or pass the GPU through.
   * - Windows open but are slow or blank
     - Software rendering over the network. Reduce the window size, or on
       Linux pass the GPU through instead.
