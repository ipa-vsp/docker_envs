FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04
# FROM nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y \
	python3-opencv vim-tiny ca-certificates python3-dev git wget sudo ninja-build
RUN ln -sv /usr/bin/python3 /usr/bin/python

COPY dockerhub/pytorch_2_0_1/bashrc /etc/bash.bashrc
RUN chmod a+rwx /etc/bash.bashrc

# create a non-root user
# ARG USER_ID=1000
# RUN useradd -m --no-log-init --system  --uid ${USER_ID} torchuser -g sudo
# RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
RUN useradd -ms /bin/bash torchuser
USER torchuser
WORKDIR /home/torchuser

ENV PATH="/home/torchuser/.local/bin:${PATH}"
RUN wget https://bootstrap.pypa.io/pip/3.6/get-pip.py && \
	python3 get-pip.py --user && \
	rm get-pip.py

# install dependencies
# See https://pytorch.org/ for other options if you use a different version of CUDA
RUN pip3 install --upgrade pip
RUN pip3 install --user tensorboard cmake   # cmake from apt-get is too old
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

RUN pip3 install --user 'git+https://github.com/facebookresearch/fvcore'

# set FORCE_CUDA because during `docker build` cuda is not accessible
ENV FORCE_CUDA="1"
# This will by default build detectron2 for all common cuda architectures and take a lot more time,
# because inside `docker build`, there is no way to tell which architecture will be used.
ARG TORCH_CUDA_ARCH_LIST="Kepler;Kepler+Tesla;Maxwell;Maxwell+Tegra;Pascal;Volta;Turing"
ENV TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST}"

RUN pip3 install scikit-image matplotlib imageio plotly opencv-python
RUN pip3 install black usort flake8 flake8-bugbear flake8-comprehensions
# RUN pip3 install "git+https://github.com/facebookresearch/pytorch3d.git@v0.7.4"

RUN pip3 install --user jupyter numpy pandas matplotlib pillow plotly scikit-learn seaborn wandb albumentations

# Set a fixed model cache directory.
ENV FVCORE_CACHE="/tmp"
