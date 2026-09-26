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
   * - macOS
     - XQuartz listening on **TCP**
     - ``host.docker.internal:0``

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

2. Let it listen on TCP, and allow indirect GL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

XQuartz ships with TCP turned off, and with indirect GLX turned off — the
first blocks the container from connecting at all, the second blocks
``rviz2`` and ``gz sim`` once it does.

.. code-block:: bash

   defaults write org.xquartz.X11 nolisten_tcp 0
   defaults write org.xquartz.X11 enable_iglx -bool true

Quit XQuartz completely and start it again; the settings are only read at
startup.

.. code-block:: bash

   open -a XQuartz
   lsof -nP -iTCP:6000 | grep LISTEN     # must print a line

Display ``:0`` is TCP port ``6000``. No listener means XQuartz is not running,
or it started before the ``defaults write``.

3. Allow the container in
^^^^^^^^^^^^^^^^^^^^^^^^^

Connections from Docker Desktop reach the Mac through its user-mode network
stack, so they arrive from the loopback address:

.. code-block:: bash

   xhost + 127.0.0.1

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

``LIBGL_ALWAYS_SOFTWARE=1`` matters because XQuartz offers the container no
hardware GL. With it, Mesa's ``llvmpipe`` renders in the container and X only
carries the finished pixels — slower, but it works on Apple silicon and Intel
alike.

``composer/macos-2/docker-compose.yml`` is a ready-made service with all of
this set:

.. code-block:: bash

   cd composer/macos-2
   docker compose up -d
   docker compose exec canopen_ws bash
   rviz2

5. Check it before blaming the app
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Two tools in the images test the path without any of ROS's complexity:

.. code-block:: bash

   xdpyinfo | head -3      # connection and screen geometry
   xmessage hello          # a window actually opens

If ``xdpyinfo`` works and ``rviz2`` does not, the problem is GL, not the
display.

Qt-only fallback: no XQuartz at all
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Qt can serve its own window over VNC, which needs nothing installed on the
Mac — macOS Screen Sharing is built in:

.. code-block:: yaml

   ports:
     - "5900:5900"
   environment:
     - QT_QPA_PLATFORM=vnc

Then connect to ``vnc://localhost:5900``.

This works for plain-Qt tools such as ``rqt`` and ``rqt_graph``. It does
**not** work for ``rviz2``, ``gz sim`` or the MuJoCo viewer: those render with
OpenGL through Ogre, which opens the X display itself and fails with
``Couldn't open X display`` no matter what Qt is doing. For those, XQuartz is
the only route.

Note that ``ports:`` is ignored under ``network_mode: host``; either drop host
networking for this service (losing cross-container ROS 2 discovery) or turn on
*Docker Desktop → Settings → Resources → Network → Enable host networking*.

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
     - The server refused the client. ``xhost + 127.0.0.1`` on macOS,
       ``xhost +local:`` or a wildcard cookie on Linux.
   * - ``Could not load the Qt platform plugin "xcb"``
     - Almost always the display above, not a missing plugin — Qt reports the
       connection failure first, then this. Fix the display.
   * - ``RenderingAPIException: Couldn't open X display`` from ``rviz2``
     - Ogre could not reach X. Confirm with ``xdpyinfo``; on macOS also set
       ``enable_iglx`` and ``LIBGL_ALWAYS_SOFTWARE=1``.
   * - Windows open but are slow or blank
     - Software rendering over the network. Reduce the window size, or on
       Linux pass the GPU through instead.
