#!/bin/bash

# Define a list of VSCode extensions to install
extensions=(
    "ms-python.python"
    "ms-vscode.cpptools"
    "ms-vscode.cpptools"
    "ms-vscode.cpptools-themes"
    "ms-azuretools.vscode-docker",
    "ms-vscode.cpptools-extension-pack"
    "donjayamanne.python-extension-pack"
    "josetr.cmake-language-support-vscode"
    "visualstudioexptteam.vscodeintellicod"
    "visualstudioexptteam.intellicode-api-usage-examples"
    "ms-vscode.cmake-tools"
    "twxs.cmake"
    "ms-iot.vscode-ros"
    "github.copilot"
    "github.copilot-chat"
)

# Loop over the extensions and install each one
for ext in "${extensions[@]}"; do
    code --install-extension $ext
done

echo "Extensions installed successfully!"
