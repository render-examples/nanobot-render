# nanobot on Render

Deploy [nanobot](https://github.com/HKUDS/nanobot) — a lightweight, self-hostable AI agent — on Render in one click. Get your own private agent with a browser chat UI, tools, and persistent memory.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/render-examples/nanobot-render)

https://github.com/user-attachments/assets/db936382-2bfa-49cf-a103-ed787b53127e

## What you get

One Render web service running nanobot's `gateway` and its bundled WebUI. You chat with the agent from your browser; it can use tools (web search/fetch, filesystem, shell, MCP servers) and remembers past sessions on a persistent disk. Access is gated by a secret you set.

## Cost expectations

This is not a free deploy. Expect:

- **Render Starter plan** — ~$7/mo for the web service. Runs the core experience well; resource-intensive tasks (npm-based CLI Apps, image rendering) may need a larger plan — see the note under [Deploy](#deploy).
- **1 GB persistent disk** — ~$0.25/mo for sessions and memory.
- **Anthropic API usage** — billed separately by Anthropic based on your agent's LLM calls.

## Deploy

1. **Generate a `NANOBOT_WEB_TOKEN`** — this is the access secret for your WebUI. Create a strong random value with one of:

   ```bash
   openssl rand -hex 32
   # or, if you don't have openssl:
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

   Copy the output — you'll paste it in step 3, and again when you first open the WebUI.
2. Click **Deploy to Render** above (or create a new Blueprint from your fork of this repo). Render reads [`render.yaml`](./render.yaml) and prompts for the environment variables below.
3. Enter your `ANTHROPIC_API_KEY` and the `NANOBOT_WEB_TOKEN` you generated, then **Apply**.
4. Wait for the service to reach **Live**, then open its `onrender.com` URL.
5. The WebUI shows an access prompt — paste the same `NANOBOT_WEB_TOKEN` to sign in. It's stored only in your browser.
6. Send a message. You're talking to your agent.

**Note:** The Starter plan comfortably runs the core experience — chat, web search/fetch, and persistent memory. Resource-intensive actions, such as installing npm-based CLI Apps or generating/rendering images, can briefly overwhelm the small instance and trigger a ~15s restart before it recovers. To run these reliably, upgrade to a larger plan (e.g. **Standard**, 2 GB) under **Settings → Instance Type** in your Render dashboard.

**Note:** If you hit an error like `No space left on device` after performing a resource-intensive task, upgrade your persistent disk size to 5 GB or larger in the **Disk** page in your Render dashboard.

## Environment variables

Render prompts for these on deploy (both are `sync: false`, so no secret is ever committed):

| Variable | What it's for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Powers the agent's LLM calls (default model `anthropic/claude-opus-4-8`). | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `NANOBOT_WEB_TOKEN` | The access secret for the WebUI — the only gate on your public agent. | Generate it yourself (see step 1 above): `openssl rand -hex 32` or `python3 -c "import secrets; print(secrets.token_hex(32))"`. |

`PORT` is set for you in the Blueprint. Configuration lives in [`render-config.json`](./render-config.json); the two secrets are referenced there as `${ANTHROPIC_API_KEY}` and `${NANOBOT_WEB_TOKEN}` and resolved at startup.

## Security note

A deployed nanobot is a capable agent: anyone who gets past `NANOBOT_WEB_TOKEN` can make it run shell commands and use tools **inside its container, with your API key**.
- This template ships hardened defaults (`restrictToWorkspace`, self-modification writes off) and runs as a non-root user in an isolated container — but the token is still your primary defense.
- Rotate the token (and your API key) if you suspect it leaked.

## DEMO mode

DEMO mode lets you host a **public, no-auth demo** of nanobot that anyone can chat with immediately — no `NANOBOT_WEB_TOKEN` prompt. It's what powers the hosted demo of this template.

**Forks default to full auth.** `DEMO` is `false`/unset unless you deliberately turn it on, so forking this template gives you the normal token-gated agent. Only set `DEMO=true` if you actually want an open, locked-down demo.

**How it works.** When `DEMO=true`, [`entrypoint.sh`](./entrypoint.sh) starts the gateway with [`render-demo-config.json`](./render-demo-config.json) instead of `render-config.json`. That config is locked down and the WebSocket channel runs in `demo` mode: the WebUI bootstrap skips the auth gate and mints short-lived anonymous tokens.

**Session isolation.** Because demo mode is unauthenticated, the anonymous token identifies no one — so the server treats it as **no** identity for session access. Each connection gets its own fresh chat (`websocket:{uuid}`, an unguessable id), and the session-browsing API is closed off: `GET /api/sessions` returns an empty list and every per-session read/delete route (`/messages`, `/webui-thread`, `/file-preview`, `/automations`, `/delete`) returns `403`. Visitors can chat in their own session but cannot list, open, or delete anyone else's — demo history is ephemeral and per-connection, never browsable.

**The lockdown (what the demo agent can and can't do).** Chat + web search/fetch only. Everything else is off:

| Capability | Demo | Why |
|---|---|---|
| Web search / fetch | ✅ on | The one useful tool; SSRF-guarded (see below). |
| Shell / exec | ❌ off | Would expose env vars incl. your `ANTHROPIC_API_KEY`. |
| Filesystem (read/write/edit/find) | ❌ off | Would let it read files/config. |
| Subagents (`spawn`) | ❌ off | New `tools.subagent.enable` flag, off in demo. |
| Cron / scheduled tasks | ❌ off | The agent is chat-only, no background work. |
| MCP servers | ❌ off | No external tool servers. |
| Self-modification (`my`) | ❌ off | No runtime config changes. |
| Image generation | ❌ off | Cost control. |

The demo also sets `restrictToWorkspace: true`, `webuiAllowLocalServiceAccess: false`, and a cheaper default model (`anthropic/claude-haiku-4-5`) for cost defense-in-depth. The WebUI hides the settings / apps / automations / skills UI and shows a "Demo mode" banner.

**Abuse / cost limits.** Two env vars bound public usage (they apply **only** when `DEMO=true`):

| Variable | Default | Meaning |
|---|---|---|
| `DEMO_RATE_LIMIT_PER_MINUTE` | `10` | Max messages per minute, per WebSocket connection. |
| `DEMO_MAX_MESSAGES_PER_SESSION` | `30` | Max total messages per browser session. |

When a cap trips, the agent replies "Demo limit reached — deploy your own nanobot to keep chatting." and stops the turn.

**Changing or disabling the limits on your fork.** Set the env vars in `render.yaml` (or the Render dashboard → Environment). Raise them for a busier demo, or set either to **`0`** to disable that limit entirely (unlimited). They have no effect unless `DEMO=true`.

**Security caveats.**
- Web fetch is SSRF-guarded in nanobot core: requests to loopback, link-local (incl. cloud metadata `169.254.169.254`), and RFC1918 private ranges are blocked, and every redirect hop is re-validated (`nanobot/security/network.py`). The demo adds no `ssrf_whitelist`, so nothing is exempted.
- With shell and filesystem tools off, the agent has no way to read the process environment or on-disk config, so the resolved `ANTHROPIC_API_KEY` (in-memory only) is unreachable.
- A demo is still a public LLM on your API key. Keep the limits sane, watch spend in the Anthropic console, and prefer the cheaper default model.

## Configuration & docs

Edit [`render-config.json`](./render-config.json) to change the model, provider, enabled tools, or channels, then redeploy. To use a different provider (OpenAI, etc.), swap the `providers` block and the model, and add the matching key to `render.yaml` as a `sync: false` env var.

For everything nanobot can do — chat channels (Telegram, Discord, Slack, …), MCP, skills, memory — see the upstream project: **[HKUDS/nanobot](https://github.com/HKUDS/nanobot)** and its [docs](https://nanobot.wiki).

## Troubleshooting

Logs live in the Render dashboard → your service → **Logs**. Start there for any failure.

- **Deploy fails or the service won't go Live.** The most common cause is a missing or mistyped `ANTHROPIC_API_KEY`. Check it under the service's **Environment** tab, then trigger a redeploy. The logs also print `[entrypoint] …` lines showing how the container started.
- **Can't sign in to the WebUI.** The token prompt expects the exact `NANOBOT_WEB_TOKEN` you set on deploy — paste it verbatim (no surrounding spaces). If you've lost it, set a new value under **Environment**, redeploy, and sign in with the new one.
- **Chat connects but the agent doesn't respond.** Usually an Anthropic-side issue — an invalid key or exhausted credit. The logs will show the provider error.

## Updating from upstream

This repo is a fork of [HKUDS/nanobot](https://github.com/HKUDS/nanobot). To pull in new nanobot releases:

```bash
git remote add upstream https://github.com/HKUDS/nanobot.git   # once
git fetch upstream
git merge upstream/main
git push                                                       # your fork
```

Render auto-deploys the new commit. If you ever re-sync the Blueprint, confirm the service's **Docker Command** still routes through `/usr/local/bin/entrypoint.sh` — it's defined in [`render.yaml`](./render.yaml), so a clean sync preserves it.

---

Built on [nanobot](https://github.com/HKUDS/nanobot) (MIT). This repo is a Render deploy template — see [`render.yaml`](./render.yaml).
