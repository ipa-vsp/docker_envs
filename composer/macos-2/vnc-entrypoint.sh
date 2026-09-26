#!/usr/bin/env bash
# Start an in-container X server and export it over VNC, then hand over to the
# image's own entrypoint so ROS and WORKSPACE_UMASK are set up as usual.
#
# Tunables (all optional):
#   VNC_DISPLAY     X display to create              (default :99)
#   VNC_GEOMETRY    framebuffer size                 (default 1600x1000)
#   VNC_DEPTH       colour depth                     (default 24)
#   VNC_PORT        RFB port inside the container     (default 5901)
#   VNC_PASSWORD    when set, require it on connect   (default: no password)
set -e

display="${VNC_DISPLAY:-:99}"
geometry="${VNC_GEOMETRY:-1600x1000}"
depth="${VNC_DEPTH:-24}"
port="${VNC_PORT:-5901}"

# GLX and RENDER are what Ogre asks for; -noreset keeps the server up when the
# last client exits, so closing rviz2 does not tear the display down.
Xvfb "$display" -screen 0 "${geometry}x${depth}" +extension GLX +extension RENDER -noreset \
    >/tmp/xvfb.log 2>&1 &

# Wait for the server to accept connections rather than sleeping blindly.
for _ in $(seq 1 50); do
    if xdpyinfo -display "$display" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done
if ! xdpyinfo -display "$display" >/dev/null 2>&1; then
    echo "vnc-entrypoint: Xvfb did not come up on $display" >&2
    cat /tmp/xvfb.log >&2 || true
    exit 1
fi

vnc_args=(-display "$display" -rfbport "$port" -forever -shared -quiet)
if [[ -n "${VNC_PASSWORD:-}" ]]; then
    mkdir -p "$HOME/.vnc"
    x11vnc -storepasswd "$VNC_PASSWORD" "$HOME/.vnc/passwd" >/dev/null 2>&1
    vnc_args+=(-rfbauth "$HOME/.vnc/passwd")
else
    # The port is only published to the Mac's loopback interface by Compose.
    vnc_args+=(-nopw)
fi
x11vnc "${vnc_args[@]}" >/tmp/x11vnc.log 2>&1 &

export DISPLAY="$display"
# XQuartz is out of the picture, but there is still no GPU: render in software.
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"

echo "vnc-entrypoint: $display served on port $port; connect to vnc://localhost:${VNC_HOST_PORT:-$port}"
exec /usr/local/bin/scripts/workspace-entrypoint.sh "$@"
