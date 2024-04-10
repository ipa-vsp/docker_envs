#!/bin/bash

snapcraft clean --destructive-mode
snapcraft  --destructive-mode --target-arch=amd64

# --target-arch=arm64
