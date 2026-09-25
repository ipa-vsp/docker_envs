Legacy and auxiliary directories
================================

These directories are kept for reference. New work goes through
``creator/`` and ``composer/``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Path
     - Contents
   * - ``creator/_deprecated/``
     - Earlier KUKA ROS 2 (``kuka_ros2``) and RHEL 9 (``rhel9``) images.
   * - ``creator/pytorch/``
     - Stand-alone PyTorch image, still built and published by
       ``pytorch-staged.yml``. ``creator/scripts/build_pytorch_env.sh``
       builds it locally.
   * - ``creator/cuda/12.8.0/``
     - Pinned CUDA 12.8 base used before the staged CUDA layer.
   * - ``dockerhub/``
     - Older Docker Hub recipes: PyTorch 1.10, PyTorch 2.0.1 and a ROS 2 CI
       build image.
   * - ``builder/``
     - Minimal ``FROM scratch`` image carrying ``workspace.bash``, built by
       ``docker.yml``.
   * - ``snapcraftor/``
     - Snapcraft experiment packaging ROS 2 Rolling as a snap.
   * - ``format.sh``
     - ``clang-format`` helper for a fixed list of packages.
