#!/bin/bash

snapcraft clean --destructive-mode
snapcraft  --destructive-mode --target-arch=arm64
