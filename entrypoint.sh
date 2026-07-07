#!/bin/sh
# Runs as root so we can fix ownership of a freshly-mounted persistent disk
# (Render mounts new disks root-owned) before dropping to the non-root app user.
dir="$HOME/.nanobot"
mkdir -p "$dir"
chown -R nanobot:nanobot "$dir"

# Drop privileges to the non-root user and exec the app as PID 1 so signals
# (SIGTERM / graceful shutdown) reach it directly.
exec setpriv --reuid=nanobot --regid=nanobot --init-groups nanobot "$@"
