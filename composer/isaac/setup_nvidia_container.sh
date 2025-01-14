#!/bin/bash

# Configure the repository
echo "Configuring NVIDIA container repository..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update

# Install the NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
echo "Configuring NVIDIA runtime for Docker..."
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify the setup
echo "Verifying NVIDIA Container Toolkit installation..."
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
