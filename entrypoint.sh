#!/bin/sh
# Prepares the (possibly root-owned, freshly-mounted) data disk and runs the app
# as the non-root nanobot user when the platform allows it, falling back to root
# only when privilege-dropping is not permitted. Logs each decision so a failed
# start is diagnosable in the platform's logs instead of a silent exit.
echo "[entrypoint] starting as $(id)"

dir="$HOME/.nanobot"
mkdir -p "$dir" || echo "[entrypoint] warning: mkdir $dir failed"

if [ "$(id -u)" != "0" ]; then
    # Already non-root (platform forced a user). Can't chown; just run.
    echo "[entrypoint] not root — running app as $(id -un)"
    exec nanobot "$@"
fi

# Running as root: make the mounted disk writable by the app user.
chown -R nanobot:nanobot "$dir" || echo "[entrypoint] warning: chown $dir failed"

# Drop to the non-root user if the runtime grants the capability to do so
# (setpriv needs CAP_SETUID/CAP_SETGID). Otherwise stay root so the app can
# still write the root-owned disk.
if setpriv --reuid=nanobot --regid=nanobot --init-groups true 2>/dev/null; then
    echo "[entrypoint] dropping privileges to nanobot via setpriv"
    exec setpriv --reuid=nanobot --regid=nanobot --init-groups nanobot "$@"
fi

echo "[entrypoint] setpriv privilege-drop not permitted — running app as root"
exec nanobot "$@"
