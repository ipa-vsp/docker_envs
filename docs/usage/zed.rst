Using Zed with a container
==========================

`Zed <https://zed.dev>`_ cannot attach to a running Docker container directly.
Instead it connects through its **SSH remote development** feature: the
container runs an SSH server, and Zed opens the workspace over SSH. The editor
UI runs on your machine; the language servers, terminal and builds run inside
the container.

The ``wbcc-zed-windows`` service in ``composer/windows/docker-compose.yaml`` is
set up for this. It is the same as ``wbcc-windows`` with two additions:

* **Build time** (``composer/windows/Dockerfile.zed``): installs
  ``openssh-server``, creates the host keys and disables password logins, root
  logins and ``StrictModes``. ``StrictModes`` is off because keys mounted from
  Windows show loose permissions. It works on top of any creator image passed
  as ``BASE_IMAGE``.
* **Run time** (the service): mounts your public key as ``admin``'s
  ``~/.ssh/authorized_keys`` and starts ``sshd`` on port ``2222`` (change it
  with ``ZED_SSH_PORT``). Before that, it writes the container environment
  (``ROS_DISTRO``, ``DISPLAY``, ``ROS_DOMAIN_ID``, ``PATH``, …) to
  ``/etc/environment``. SSH logins start with an empty environment, so this
  gives the Zed terminal the same variables as ``docker exec``.

.. code-block:: yaml

   wbcc-zed-windows:
     image: docker_envs:wbcc-zed
     build:
       context: .
       dockerfile: Dockerfile.zed
       args:
         BASE_IMAGE: docker_envs:24.04-cuda13.3.1-jazzy-...
     user: root              # sshd starts as root; logins are admin
     volumes:
       - ${ZED_SSH_PUBKEY:-${USERPROFILE}/.ssh/id_ed25519.pub}:/home/admin/.ssh/authorized_keys:ro
     command: >-
       sh -c "env | grep -vE '^(HOME|HOSTNAME|PWD|SHLVL|USER|_)=' > /etc/environment
       && exec /usr/sbin/sshd -D -e -p ${ZED_SSH_PORT:-2222}"

``HOME`` and ``USER`` are filtered out because the command runs as root;
passing them on would give ``admin`` root's home directory.

.. note::

   The tabs below use `sphinx-design <https://sphinx-design.readthedocs.io>`_
   (``tab-set`` / ``tab-item``). Selecting an OS in one tab set switches all of
   them.


1. Prerequisites
----------------

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      * Docker Desktop with the WSL 2 backend and NVIDIA GPU support.
      * **Host networking enabled**: *Docker Desktop → Settings → Resources →
        Network → Enable host networking* (Docker Desktop 4.34 or newer).
        Without it, ``network_mode: host`` binds to Docker's internal VM and
        port ``2222`` is not reachable from Windows. See
        :ref:`zed-proxycommand` for a setup that does not need it.
      * The OpenSSH client (built into Windows 10/11; check with
        ``ssh -V``).
      * Zed for Windows.

   .. tab-item:: macOS
      :sync: macos

      * Docker Desktop 4.34 or newer with **host networking enabled**:
        *Settings → Resources → Network → Enable host networking*. Or use
        :ref:`zed-proxycommand`.
      * Zed for macOS. The OpenSSH client ships with macOS.
      * Macs have no NVIDIA GPU. Remove the ``runtime: nvidia`` and ``deploy:``
        blocks from the service, and use an image built for your architecture.

   .. tab-item:: Linux
      :sync: linux

      * Docker Engine with the NVIDIA Container Toolkit.
        ``network_mode: host`` works natively, so port ``2222`` on the host is
        the container's SSH server.
      * The OpenSSH client (``sudo apt install openssh-client`` on
        Debian/Ubuntu).
      * Zed for Linux.
      * The ``/run/desktop/mnt/host/wslg`` volume is Windows-only. Replace it
        with ``/tmp/.X11-unix:/tmp/.X11-unix`` and set ``DISPLAY=$DISPLAY``.


2. Create an SSH key
--------------------

Skip this step if you already have ``~/.ssh/id_ed25519.pub``.

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      .. code-block:: powershell

         ssh-keygen -t ed25519
         Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub

   .. tab-item:: macOS
      :sync: macos

      .. code-block:: bash

         ssh-keygen -t ed25519
         cat ~/.ssh/id_ed25519.pub

   .. tab-item:: Linux
      :sync: linux

      .. code-block:: bash

         ssh-keygen -t ed25519
         cat ~/.ssh/id_ed25519.pub

.. warning::

   The key file must exist **before** starting the container. If it is
   missing, Docker creates an empty directory in its place, and every login
   fails with ``Permission denied (publickey)``.


3. Start the container
----------------------

By default the service mounts ``%USERPROFILE%\.ssh\id_ed25519.pub``. Set
``ZED_SSH_PUBKEY`` to use a different key, and ``ZED_SSH_PORT`` to use a
different port.

The first ``up`` builds ``docker_envs:wbcc-zed`` from ``Dockerfile.zed``
(about a minute). Later starts reuse it. Rebuild with ``--build`` after the
base image changes.

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      .. code-block:: powershell

         cd composer\windows
         docker compose up -d wbcc-zed-windows
         docker compose logs wbcc-zed-windows   # expect: Server listening on 0.0.0.0 port 2222

      Different key or port:

      .. code-block:: powershell

         $env:ZED_SSH_PUBKEY = "$env:USERPROFILE\.ssh\id_rsa.pub"
         $env:ZED_SSH_PORT = "2223"
         docker compose up -d wbcc-zed-windows

   .. tab-item:: macOS
      :sync: macos

      ``USERPROFILE`` is not set on macOS, so always pass the key path:

      .. code-block:: bash

         cd composer/windows
         ZED_SSH_PUBKEY=~/.ssh/id_ed25519.pub docker compose up -d wbcc-zed-windows
         docker compose logs wbcc-zed-windows   # expect: Server listening on 0.0.0.0 port 2222

   .. tab-item:: Linux
      :sync: linux

      ``USERPROFILE`` is not set on Linux, so always pass the key path:

      .. code-block:: bash

         cd composer/windows
         ZED_SSH_PUBKEY=~/.ssh/id_ed25519.pub docker compose up -d wbcc-zed-windows
         docker compose logs wbcc-zed-windows   # expect: Server listening on 0.0.0.0 port 2222


4. Add an SSH host entry
------------------------

Add a ``wbcc`` host to your SSH config so both ``ssh`` and Zed can use a short
name.

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      Edit ``%USERPROFILE%\.ssh\config`` (create it if needed):

      .. code-block:: powershell

         notepad $env:USERPROFILE\.ssh\config

      .. code-block:: text

         Host wbcc
             HostName localhost
             Port 2222
             User admin
             IdentityFile ~/.ssh/id_ed25519

   .. tab-item:: macOS
      :sync: macos

      .. code-block:: bash

         mkdir -p ~/.ssh && chmod 700 ~/.ssh
         cat >> ~/.ssh/config <<'EOF'
         Host wbcc
             HostName localhost
             Port 2222
             User admin
             IdentityFile ~/.ssh/id_ed25519
         EOF
         chmod 600 ~/.ssh/config

   .. tab-item:: Linux
      :sync: linux

      .. code-block:: bash

         mkdir -p ~/.ssh && chmod 700 ~/.ssh
         cat >> ~/.ssh/config <<'EOF'
         Host wbcc
             HostName localhost
             Port 2222
             User admin
             IdentityFile ~/.ssh/id_ed25519
         EOF
         chmod 600 ~/.ssh/config

If the container runs on another machine, set ``HostName`` to that machine's
address.

Check the connection. It should print ``admin`` and the ROS distro:

.. code-block:: bash

   ssh wbcc 'whoami && echo $ROS_DISTRO'


5. Open the workspace in Zed
----------------------------

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      1. Open the command palette with :kbd:`Ctrl+Shift+P` and run
         ``projects: open remote``.
      2. Choose **Connect New Server**, enter ``wbcc`` and press
         :kbd:`Enter`.
      3. Open ``/home/admin/colcon_ws``.

   .. tab-item:: macOS
      :sync: macos

      1. Open the command palette with :kbd:`Cmd+Shift+P` and run
         ``projects: open remote``.
      2. Choose **Connect New Server**, enter ``wbcc`` and press
         :kbd:`Enter`.
      3. Open ``/home/admin/colcon_ws``.

      Or from a terminal (requires *Zed → Install CLI*):

      .. code-block:: bash

         zed ssh://wbcc/home/admin/colcon_ws

   .. tab-item:: Linux
      :sync: linux

      1. Open the command palette with :kbd:`Ctrl+Shift+P` and run
         ``projects: open remote``.
      2. Choose **Connect New Server**, enter ``wbcc`` and press
         :kbd:`Enter`.
      3. Open ``/home/admin/colcon_ws``.

      Or from a terminal:

      .. code-block:: bash

         zed ssh://wbcc/home/admin/colcon_ws

On the first connection Zed downloads its remote server into
``~/.zed_server`` inside the container. The container needs internet access
for this. The server is lost when the container is recreated and is downloaded
again on the next connection.

The server is saved in Zed's ``settings.json`` under ``ssh_connections``, so
later you can reopen it from ``projects: open remote``.


6. Zed settings (optional)
--------------------------

Save the connection
~~~~~~~~~~~~~~~~~~~

Adding the connection to your **user** settings gives it a name and pins the
project, so it appears in ``projects: open remote`` with one click. Open the
file with ``zed: open settings`` in the command palette, or edit it directly:

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      ``%APPDATA%\Zed\settings.json``

   .. tab-item:: macOS
      :sync: macos

      ``~/.config/zed/settings.json``

   .. tab-item:: Linux
      :sync: linux

      ``~/.config/zed/settings.json``

.. code-block:: json

   {
     "ssh_connections": [
       {
         "host": "wbcc",
         "nickname": "wbcc (FR3 demo)",
         "args": ["-o", "ServerAliveInterval=30"],
         "projects": [{ "paths": ["/home/admin/colcon_ws"] }]
       },
       {
         "host": "rsi",
         "nickname": "rsi",
         "projects": [{ "paths": ["/home/admin/colcon_ws"] }]
       }
     ]
   }

* ``host`` is the alias from step 4. Port, user and key come from your SSH
  config, so they are not repeated here.
* ``args`` are extra ``ssh`` arguments. ``ServerAliveInterval`` keeps the
  connection open while the container is idle.
* Add ``"upload_binary_over_ssh": true`` when the container has no internet
  access. Zed then downloads its remote server on your machine and copies it
  over SSH.

Project settings for a colcon workspace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Settings in ``.zed/settings.json`` inside the workspace apply only to that
project and run on the container side.

``/home/admin/colcon_ws/.zed/settings.json``:

.. code-block:: json

   {
     "file_scan_exclusions": ["**/.git", "build", "install", "log"],
     "terminal": { "detect_venv": "off" },
     "lsp": {
       "clangd": {
         "binary": {
           "arguments": [
             "--compile-commands-dir=build",
             "--background-index",
             "--header-insertion=never"
           ]
         }
       }
     }
   }

* ``file_scan_exclusions`` hides colcon's ``build``, ``install`` and ``log``
  folders from search and the project panel. It replaces Zed's default list,
  so ``**/.git`` is repeated.
* ``detect_venv: off`` stops Zed from activating a ``.venv`` in the terminal.
  The image already activates ``/opt/venv``.
* ``clangd`` reads ``build/compile_commands.json``. colcon writes one file per
  package, so build with compile commands on and merge them:

  .. code-block:: bash

     colcon build --symlink-install --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
     python3 - <<'PY'
     import glob, json
     cmds = []
     for f in glob.glob("build/*/compile_commands.json"):
         cmds += json.load(open(f))
     json.dump(cmds, open("build/compile_commands.json", "w"), indent=1)
     PY

For Python, put a ``pyrightconfig.json`` next to it. Zed's Python language
server reads it, so imports from ``/opt/venv``, ROS and your built packages
resolve:

.. code-block:: json

   {
     "venvPath": "/opt",
     "venv": "venv",
     "extraPaths": ["/opt/ros/jazzy/lib/python3.12/site-packages"]
   }

With ``--symlink-install``, your own Python packages resolve to their sources
in ``src/``.

.. note::

   ``wbcc-zed-windows`` mounts only ``src/`` from the host. Files created at
   the workspace root (``.zed/``, ``pyrightconfig.json``, ``build/``) are lost
   when the container is recreated. Keep a copy in your repository and copy it
   in, or mount the whole workspace instead of ``src/``.


.. _zed-proxycommand:

Alternative: connect without host networking
--------------------------------------------

If port ``2222`` is not reachable (for example, host networking is disabled in
Docker Desktop), SSH can tunnel through ``docker exec`` instead of the
network. This starts a one-off ``sshd`` in inetd mode for each connection, so
it works with any running container that has ``openssh-server`` installed,
including ``wbcc-zed-windows``.

Look up the container name first:

.. code-block:: bash

   docker ps --format '{{.Names}}'   # e.g. windows-wbcc-zed-windows-1

Then use this host entry instead of the one in step 4:

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      .. code-block:: text

         Host wbcc
             User admin
             IdentityFile ~/.ssh/id_ed25519
             ProxyCommand docker exec -i -u root windows-wbcc-zed-windows-1 /usr/sbin/sshd -i

   .. tab-item:: macOS
      :sync: macos

      .. code-block:: text

         Host wbcc
             User admin
             IdentityFile ~/.ssh/id_ed25519
             ProxyCommand docker exec -i -u root windows-wbcc-zed-windows-1 /usr/sbin/sshd -i

   .. tab-item:: Linux
      :sync: linux

      .. code-block:: text

         Host wbcc
             User admin
             IdentityFile ~/.ssh/id_ed25519
             ProxyCommand docker exec -i -u root windows-wbcc-zed-windows-1 /usr/sbin/sshd -i

      If your user is not in the ``docker`` group, the ``docker exec``
      needs ``sudo``. Add yourself to the group instead
      (``sudo usermod -aG docker $USER``, then log in again).

.. note::

   On Windows, use the built-in OpenSSH client
   (``C:\Windows\System32\OpenSSH\ssh.exe``), which is what Zed uses. The
   ``ssh`` bundled with Git Bash closes the connection immediately with this
   ``ProxyCommand``.


Running several containers at once
----------------------------------

Every container has its own ``/etc/passwd``, home directory, host keys and
``sshd``. Two containers that both have an ``admin`` user are separate accounts
that happen to share a name, and they do not interfere with each other. Zed
tells them apart by the SSH **host alias**, not by the user name.

The only thing they can share is the **port**. With ``network_mode: host``,
every container uses the host's network, so two ``sshd`` processes cannot both
listen on ``2222``. The second one fails with ``Address already in use`` and
its container exits.

Give each container its own port and its own host entry:

.. code-block:: text

   Host wbcc
       HostName localhost
       Port 2222
       User admin

   Host rsi
       HostName localhost
       Port 2223
       User admin

``ZED_SSH_PORT`` applies to the whole ``docker compose`` command, so start each
service separately with its own port. A second service needs the same SSH setup
as ``wbcc-zed-windows``: the ``build:`` (with its own ``BASE_IMAGE`` and
``image:`` name), ``user: root``, the key mount and the ``command:`` line.

.. code-block:: bash

   ZED_SSH_PORT=2222 docker compose up -d wbcc-zed-windows
   ZED_SSH_PORT=2223 docker compose up -d rsi-zed-windows

Other things to know:

* Host keys are recorded per ``host:port`` in ``known_hosts`` (for example
  ``[localhost]:2222``), so different ports do not trigger host-key warnings.
* Zed's remote server lives in each container's ``~/.zed_server``, so each
  container gets its own copy.
* With :ref:`zed-proxycommand` there are no ports at all. Each host entry
  names a different container in its ``docker exec``, so any number of
  containers can run side by side.
* ``ROS_DOMAIN_ID`` is **shared** under host networking. Containers with the
  same domain ID see each other's ROS topics. That is unrelated to SSH, but
  give them different IDs if they should stay isolated.


Troubleshooting
---------------

``Connection refused`` on port 2222
   The container is not running, ``sshd`` failed to start, or host networking
   is disabled in Docker Desktop. Check ``docker compose logs
   wbcc-zed-windows``, or use :ref:`zed-proxycommand`.

``Permission denied (publickey)``
   The mounted key does not match your private key. Check what the container
   has with ``docker exec windows-wbcc-zed-windows-1 cat
   /home/admin/.ssh/authorized_keys``, then recreate the container with the
   right ``ZED_SSH_PUBKEY``.

``REMOTE HOST IDENTIFICATION HAS CHANGED``
   Host keys are created when the image is built, so rebuilding it gives new
   keys. Remove the old entry: ``ssh-keygen -R "[localhost]:2222"``. With
   :ref:`zed-proxycommand`, remove the ``wbcc`` entry instead.

``authorized_keys`` is a directory
   The key file did not exist when the container started, so Docker created a
   directory. Create the key (step 2), run ``docker compose rm -sf
   wbcc-zed-windows``, and start it again.

ROS or Python environment missing in the Zed terminal
   The variables come from ``/etc/environment``, written when the container
   starts. Run ``cat /etc/environment`` in the Zed terminal to check them, and
   ``source /opt/ros/$ROS_DISTRO/setup.bash`` if your shell does not source
   it through ``~/.bashrc``.
