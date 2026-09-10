#!/usr/bin/env bash
# Build-time account setup only; never run this against mounted host data.
set -euo pipefail

: "${USERNAME:=admin}" "${USER_UID:=1000}" "${USER_GID:=1000}"
[[ "$USERNAME" =~ ^[a-z_][a-z0-9_-]*$ && "$USERNAME" != root ]] || {
    echo "USERNAME must be a non-root Linux account name" >&2; exit 1;
}
for value in "$USER_UID" "$USER_GID"; do
    [[ "$value" =~ ^[1-9][0-9]*$ && ${#value} -le 10 && "$value" -le 4294967294 ]] || {
        echo "USER_UID and USER_GID must be positive numeric IDs below 4294967295" >&2; exit 1;
    }
done

previous_gid=""
if id "$USERNAME" >/dev/null 2>&1; then
    account_home="$(getent passwd "$USERNAME" | cut -d: -f6)"
    if [[ "$account_home" != "/home/$USERNAME" ]]; then
        echo "Refusing to modify account $USERNAME with home $account_home" >&2; exit 1
    fi
    previous_gid="$(id -g "$USERNAME")"
fi

owner="$(getent passwd "$USER_UID" | cut -d: -f1 || true)"
if [[ -n "$owner" && "$owner" != "$USERNAME" ]]; then
    # Ubuntu's default login is the only account we replace automatically.
    if [[ "$owner" == ubuntu && "$USER_UID" == 1000 ]]; then
        userdel ubuntu
    else
        echo "UID $USER_UID is already assigned to $owner" >&2; exit 1
    fi
fi
if ! getent group "$USER_GID" >/dev/null; then
    if getent group "$USERNAME" >/dev/null; then
        groupmod --gid "$USER_GID" "$USERNAME"
    else
        groupadd --gid "$USER_GID" "$USERNAME"
    fi
fi
if id "$USERNAME" >/dev/null 2>&1; then
    usermod --uid "$USER_UID" --gid "$USER_GID" "$USERNAME"
else
    useradd --no-log-init --uid "$USER_UID" --gid "$USER_GID" \
        --create-home --home-dir "/home/$USERNAME" --shell /bin/bash "$USERNAME"
fi
# usermod adjusts home file UIDs; restrict any GID repair to the image home.
if [[ -n "$previous_gid" && "$previous_gid" != "$USER_GID" ]]; then
    find "/home/$USERNAME" -xdev -uid "$USER_UID" -gid "$previous_gid" \
        -exec chgrp "$USER_GID" {} +
fi
install -d -o "$USER_UID" -g "$USER_GID" \
    "/home/$USERNAME/colcon_ws" "/home/$USERNAME/colcon_ws/src" "/home/$USERNAME/workspace"
usermod -aG sudo,video "$USERNAME"
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$USERNAME" > "/etc/sudoers.d/$USERNAME"
chmod 0440 "/etc/sudoers.d/$USERNAME"
