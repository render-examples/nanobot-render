#!/bin/sh
# Prepares the (possibly root-owned, freshly-mounted) data disk and runs the app
# as the non-root nanobot user when the platform allows it, falling back to root
# only when privilege-dropping is not permitted. Logs each decision so a failed
# start is diagnosable in the platform's logs instead of a silent exit.
echo "[entrypoint] starting as $(id)"

# Pick the gateway config. DEMO=true/1 runs the locked-down, unauthenticated
# hosted demo (chat-only, rate/session capped); anything else keeps full auth.
# render.yaml passes only `gateway` as the command, so the entrypoint owns the
# --config selection here.
CONFIG="/app/render-config.json"
case "$DEMO" in
    true|TRUE|True|1)
        CONFIG="/app/render-demo-config.json"
        echo "[entrypoint] DEMO mode enabled — using $CONFIG"
        ;;
    *)
        echo "[entrypoint] normal mode — using $CONFIG"
        ;;
esac

dir="$HOME/.nanobot"
mkdir -p "$dir" || echo "[entrypoint] warning: mkdir $dir failed"

# Copy the selected config onto the mounted disk so nanobot's data_dir
# (config_path.parent) resolves under the mount. Otherwise data_dir is /app —
# baked into the image and wiped every deploy — which loses the WebUI display
# transcripts (webui/), cron, media and logs even though session files persist.
# The committed template is the source of truth, so overwrite on every boot;
# secrets stay as ${VAR} placeholders in the file and are interpolated in memory
# at load time, so nothing secret is written to disk.
RUNTIME_CONFIG="$dir/config.json"
cp "$CONFIG" "$RUNTIME_CONFIG" || echo "[entrypoint] warning: cp $CONFIG -> $RUNTIME_CONFIG failed"

if [ "$(id -u)" != "0" ]; then
    # Already non-root (platform forced a user). Can't chown; just run.
    echo "[entrypoint] not root — running app as $(id -un)"
    exec nanobot "$@" --config "$RUNTIME_CONFIG"
fi

# Running as root: make the mounted disk (incl. the copied config) writable and
# readable by the app user.
chown -R nanobot:nanobot "$dir" || echo "[entrypoint] warning: chown $dir failed"

# Drop to the non-root user if the runtime grants the capability to do so
# (setpriv needs CAP_SETUID/CAP_SETGID). Otherwise stay root so the app can
# still write the root-owned disk.
if setpriv --reuid=nanobot --regid=nanobot --init-groups true 2>/dev/null; then
    echo "[entrypoint] dropping privileges to nanobot via setpriv"
    exec setpriv --reuid=nanobot --regid=nanobot --init-groups nanobot "$@" --config "$RUNTIME_CONFIG"
fi

echo "[entrypoint] setpriv privilege-drop not permitted — running app as root"
exec nanobot "$@" --config "$RUNTIME_CONFIG"
