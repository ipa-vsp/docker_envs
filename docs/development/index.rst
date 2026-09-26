Development
===========

Run the checks below from the repository root before opening a pull request.

Tests
-----

The regression suite in ``tests/`` uses ``unittest`` and needs no Docker
daemon. It stubs ``docker`` and checks the build planner, the runtime flags,
both Isaac Lab install paths, the cuRobo layer and the GUI.

.. code-block:: bash

   python3 -m pip install PyYAML          # needed by the Linux suite
   python3 -m unittest discover -s tests -v

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Module
     - Covers
   * - ``test_build_pipeline.py``
     - Publication boundaries and failure handling of local builds.
   * - ``test_runtime.py``
     - ``run_env.sh`` runtime arguments and container startup behavior.
   * - ``test_isaaclab_installation.py``
     - The ``python-env`` and ``legacy`` Isaac Lab installation paths.
   * - ``test_curobo_installation.py``
     - cuRobo build-plan rules and CUDA extra selection.
   * - ``test_windows_builder.py``
     - The native Windows builder and its parity with the Bash planner. Run on
       Windows for full coverage; Linux with ``pwsh`` runs the parity checks.
   * - ``test_gui_bridge.py``
     - ``query.sh``, the machine-readable front end to ``stages.sh``.
   * - ``test_gui_model.py``, ``test_gui_docker.py``
     - The GUI's pure-Python layer and its Images/Containers tabs.
   * - ``test_gui_smoke.py``
     - Headless form checks. Skipped when PySide6 is not installed.
   * - ``test_image_permissions.py``
     - Optional Docker smoke checks against a built image (used in CI).

Run one module with ``-p``, for example
``python3 -m unittest discover -s tests -p test_runtime.py -v``.

Pre-commit hooks
----------------

``.pre-commit-config.yaml`` runs whitespace and YAML checks, ``black``
(line length 99), ``pyupgrade``, ``clang-format``, ``codespell`` and, for
these docs, ``doc8`` and the reStructuredText pygrep hooks.

.. code-block:: bash

   pip install pre-commit
   pre-commit install            # run on every commit
   pre-commit run --all-files

Continuous integration
----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Workflow
     - What it does
   * - ``build-validation.yml``
     - Unit tests on Linux and Windows, shell syntax checks, build-plan
       previews and permission smoke checks on a freshly built image.
   * - ``ros2-staged.yml``
     - Builds and publishes the ROS 2 and ROS 2 + MoveIt images to
       ``ghcr.io/ipa-vsp/docker_envs``.
   * - ``pytorch-staged.yml``
     - Builds and publishes the PyTorch image from ``creator/pytorch``.
   * - ``gui-appimage.yml``
     - GUI tests and the AppImage release build (on ``v*`` tags).
   * - ``docs.yml``
     - Builds this site with warnings as errors and, on ``main``, deploys it to
       GitHub Pages. See *Publishing* below.
   * - ``format.yml``
     - Runs the pre-commit hooks.
   * - ``docker.yml``
     - Builds the ``builder/`` CI image.
   * - ``ghcr-cleanup.yml``
     - Manual cleanup of old registry versions.

Documentation
-------------

These docs are built with Sphinx, MyST, sphinx-design and the Furo theme.

.. tab-set::

   .. tab-item:: Windows
      :sync: windows

      .. code-block:: powershell

         python -m pip install -r docs\requirements.txt
         docs\make.bat html
         start docs\_build\html\index.html

   .. tab-item:: macOS
      :sync: macos

      .. code-block:: bash

         python3 -m pip install -r docs/requirements.txt
         make -C docs html
         open docs/_build/html/index.html

   .. tab-item:: Linux
      :sync: linux

      .. code-block:: bash

         python3 -m pip install -r docs/requirements.txt
         make -C docs html
         xdg-open docs/_build/html/index.html

``make -C docs strict`` treats warnings as errors, and ``make -C docs live``
rebuilds on save (needs ``sphinx-autobuild``).

How the pages are assembled:

* The Markdown guides next to the code (``README.md``, ``creator/README.md``,
  ``gui/README.md``, ``composer/*/README.md``, ``docs/ISAAC_WORKFLOW.md``) stay
  the single source. ``docs/conf.py`` copies them into ``docs/_generated/``
  at build time. Links between guides become cross-references, and links to
  other files point at GitHub. **Edit the original guide, never
  ``_generated/``.**
* Pages that exist only in the docs are reStructuredText under ``docs/``
  (``index.rst``, ``composer/``, ``usage/``, ``development/``).
* To publish a new guide, add it to ``GUIDES`` in ``docs/conf.py`` and to a
  ``toctree``.

Publishing
^^^^^^^^^^

``.github/workflows/docs.yml`` builds the site on every pull request and push
that touches ``docs/``, any ``README.md`` or the workflow itself.

* It runs ``make -C docs clean strict``, so a broken cross-reference, a page
  left out of every ``toctree`` or a guide ``conf.py`` cannot read fails the
  job rather than shipping a broken page. Reproduce a CI failure locally with
  the same command.
* Every run uploads the rendered site as the ``docs-html`` artifact, so a
  reviewer can download and open a pull request's docs.
* Pushes to ``main`` (and manual runs) deploy to GitHub Pages through
  ``actions/deploy-pages``; the run summary links the published URL. Pull
  requests from forks never deploy.

The deployment needs *Settings → Pages → Build and deployment → Source:
**GitHub Actions*** once per repository. Until that is set, the ``build`` job
passes and the ``deploy`` job fails with a missing-Pages-site error.
