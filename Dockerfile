FROM node:24-bookworm-slim AS webui-builder

WORKDIR /app
COPY webui/package.json webui/package-lock.json ./webui/
WORKDIR /app/webui
RUN npm ci
COPY webui/ ./
RUN mkdir -p /app/nanobot/web && npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git bubblewrap openssh-client libmagic1 && \
    rm -rf /var/lib/apt/lists/*

# Node.js + npm at runtime so npm-based CLI Apps (e.g. hyperframes) can install.
# Reuse the exact toolchain from the webui-builder stage instead of pulling a
# second copy. Without this, `npm install -g` fails with "npm is not installed".
COPY --from=webui-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=webui-builder /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    node --version && npm --version

WORKDIR /app

# Install Python dependencies first (cached layer). Hatch reads the custom build
# hook from hatch_build.py even for this metadata-only install.
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md hatch_build.py ./
RUN mkdir -p nanobot && touch nanobot/__init__.py && \
    NANOBOT_SKIP_WEBUI_BUILD=1 uv pip install --system --no-cache ".[whatsapp]" && \
    rm -rf nanobot

# Copy the full source and install
COPY nanobot/ nanobot/
COPY --from=webui-builder /app/nanobot/web/dist/ nanobot/web/dist/
RUN NANOBOT_SKIP_WEBUI_BUILD=1 uv pip install --system --no-cache ".[whatsapp]"

# Render deploy template: committed gateway config that wires secrets through
# ${ANTHROPIC_API_KEY} / ${NANOBOT_WEB_TOKEN} env vars (resolved at startup).
# Lives in the code dir (/app), not the data dir, so a mounted disk won't shadow it.
# render-demo-config.json is the locked-down config the entrypoint selects when DEMO=true.
COPY render-config.json render-demo-config.json ./

# Create non-root user and config directory. The npm global prefix lives under
# the nanobot home (writable by the non-root runtime user) so `npm install -g`
# from the CLI Apps UI succeeds; its bin dir is added to PATH below so the
# installed CLIs resolve via shutil.which().
RUN useradd -m -u 1000 -s /bin/bash nanobot && \
    mkdir -p /home/nanobot/.nanobot /home/nanobot/.npm-global/bin && \
    chown -R nanobot:nanobot /home/nanobot /app

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

# Start as root so the entrypoint can chown the freshly-mounted (root-owned)
# Render disk, then it drops to the non-root nanobot user via setpriv.
USER root
ENV HOME=/home/nanobot
# Route npm global installs to a user-writable prefix and expose its bin on PATH.
ENV NPM_CONFIG_PREFIX=/home/nanobot/.npm-global \
    PATH=/home/nanobot/.npm-global/bin:$PATH
# Ensure crash output reaches Render logs (app output is otherwise swallowed on
# non-graceful exit). Baked in so it survives Blueprint syncs.
ENV PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1

# Gateway health endpoint and optional WebUI/WebSocket channel ports
EXPOSE 18790 8765

ENTRYPOINT ["entrypoint.sh"]
CMD ["status"]
