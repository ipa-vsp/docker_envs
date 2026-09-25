docker_envs
===========

Docker development environments for ROS 2, PyTorch, MuJoCo and NVIDIA Isaac
Sim / Isaac Lab.

* **Creator** builds images from stacked layers: pick an Ubuntu base, a ROS 2
  distribution, and optional CUDA, MuJoCo, Isaac Sim, Isaac Lab, cuRobo and
  application layers.
* **Composer** holds Docker Compose files that run those images for specific
  projects and machines.
* The **GUI** is a desktop front end that runs the same builder.

.. grid:: 1 2 2 3
   :gutter: 2

   .. grid-item-card:: Get started
      :link: _generated/overview
      :link-type: doc

      Requirements, quick start, daily loop and published images.

   .. grid-item-card:: Build images
      :link: _generated/creator
      :link-type: doc

      Build and run flags, versions, permissions, caching, Isaac options.

   .. grid-item-card:: Isaac Sim + Lab
      :link: _generated/isaac-workflow
      :link-type: doc

      End-to-end workflow from host setup to training runs.

   .. grid-item-card:: Compose examples
      :link: composer/index
      :link-type: doc

      Every service in ``composer/`` and what it is for.

   .. grid-item-card:: Edit with Zed
      :link: usage/zed
      :link-type: doc

      Open a container workspace in Zed over SSH on Windows, macOS or Linux.

   .. grid-item-card:: Contribute
      :link: development/index
      :link-type: doc

      Tests, pre-commit hooks, CI workflows and building these docs.

.. toctree::
   :caption: Getting started
   :maxdepth: 2
   :hidden:

   _generated/overview
   _generated/isaac-workflow

.. toctree::
   :caption: Building images
   :maxdepth: 2
   :hidden:

   _generated/creator
   _generated/gui

.. toctree::
   :caption: Running containers
   :maxdepth: 2
   :hidden:

   composer/index
   _generated/composer-template
   _generated/composer-isaaclab
   _generated/composer-isaacsim
   composer/windows
   _generated/composer-canopen
   _generated/composer-isaac

.. toctree::
   :caption: Editors
   :maxdepth: 2
   :hidden:

   usage/zed

.. toctree::
   :caption: Development
   :maxdepth: 2
   :hidden:

   development/index
   development/legacy
