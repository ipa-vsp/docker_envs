#!/usr/bin/env bash
# Build-time install of Node.js for the npm-distributed agent tooling (REA,
# OmniRoute) that Dockerfile.user adds after Claude Code.
#
# The official release tarball is used instead of the distribution package:
# Ubuntu's nodejs is older than the Node 22.19+/24.x those tools require, and
# the tarball works the same on every base image (ROS, CUDA, Isaac).
# NODE_MAJOR selects the release line; the latest release in it is installed
# and verified against the line's published SHA-256 checksums.
set -euo pipefail
: "${NODE_MAJOR:=24}"

if command -v node >/dev/null 2>&1 && \
        [[ "$(node -p 'process.versions.node.split(".")[0]')" == "$NODE_MAJOR" ]]; then
    echo "Reusing Node.js $(node --version)"
    exit 0
fi

case "$(dpkg --print-architecture)" in
    amd64) arch=x64 ;;
    arm64) arch=arm64 ;;
    *) echo "Unsupported Node.js architecture: $(dpkg --print-architecture)" >&2; exit 1 ;;
esac

base="https://nodejs.org/dist/latest-v${NODE_MAJOR}.x"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

curl -fsSL "$base/SHASUMS256.txt" -o "$workdir/SHASUMS256.txt"
tarball="$(awk -v suffix="-linux-${arch}.tar.gz" \
    'substr($2, length($2) - length(suffix) + 1) == suffix { print $2 }' "$workdir/SHASUMS256.txt")"
if [[ -z "$tarball" ]]; then
    echo "No linux-${arch} tarball listed in $base/SHASUMS256.txt" >&2
    exit 1
fi
curl -fsSL "$base/$tarball" -o "$workdir/$tarball"
(cd "$workdir" && awk -v t="$tarball" '$2 == t' SHASUMS256.txt | sha256sum -c -)

# node, npm and npx land in /usr/local/bin, ahead of any distribution copy.
tar -xzf "$workdir/$tarball" -C /usr/local --strip-components=1 --no-same-owner \
    --exclude='*/CHANGELOG.md' --exclude='*/README.md' --exclude='*/LICENSE'
echo "Installed Node.js $(node --version), npm $(npm --version)"
