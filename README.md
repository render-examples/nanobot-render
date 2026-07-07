# nanobot on Render

Deploy [nanobot](https://github.com/HKUDS/nanobot) — a lightweight, self-hostable AI agent — on Render in one click. Get your own private agent with a browser chat UI, tools, and persistent memory.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Ho1yShif/nanobot)

## What you get

One Render web service running nanobot's `gateway` and its bundled WebUI. You chat with the agent from your browser; it can use tools (web search/fetch, filesystem, shell, MCP servers) and remembers past sessions on a persistent disk. Access is gated by a secret you set.

## Deploy

1. Click **Deploy to Render** above (or create a new Blueprint from your fork of this repo).
2. Render reads [`render.yaml`](./render.yaml) and prompts for two environment variables (below).
3. Wait for the service to reach **Live**, then open its `onrender.com` URL.
4. The WebUI shows an access prompt — paste your `NANOBOT_WEB_TOKEN` to sign in. It's stored only in your browser.
5. Send a message. You're talking to your agent.

## Environment variables

Render prompts for these on deploy (both are `sync: false`, so no secret is ever committed):

| Variable | What it's for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Powers the agent's LLM calls (default model `anthropic/claude-opus-4-5`). | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `NANOBOT_WEB_TOKEN` | The access secret for the WebUI — the only gate on your public agent. | Generate a strong random value, e.g. `openssl rand -hex 32`. |

`PORT` is set for you in the Blueprint. Configuration lives in [`render-config.json`](./render-config.json); the two secrets are referenced there as `${ANTHROPIC_API_KEY}` and `${NANOBOT_WEB_TOKEN}` and resolved at startup.

## Security note — read this

A deployed nanobot is a capable agent: anyone who gets past `NANOBOT_WEB_TOKEN` can make it run shell commands and use tools **inside its container, with your API key**.

- **Keep `NANOBOT_WEB_TOKEN` secret and strong.** It's the only thing standing between the internet and your agent.
- This template ships hardened defaults (`restrictToWorkspace`, self-modification writes off) and runs as a non-root user in an isolated container — but the token is still your primary defense.
- Rotate the token (and your API key) if you suspect it leaked.

## Configuration & docs

Edit [`render-config.json`](./render-config.json) to change the model, provider, enabled tools, or channels, then redeploy. To use a different provider (OpenAI, etc.), swap the `providers` block and the model, and add the matching key to `render.yaml` as a `sync: false` env var.

For everything nanobot can do — chat channels (Telegram, Discord, Slack, …), MCP, skills, memory — see the upstream project: **[HKUDS/nanobot](https://github.com/HKUDS/nanobot)** and its [docs](https://nanobot.wiki).

---

Built on [nanobot](https://github.com/HKUDS/nanobot) (MIT). This repo is a Render deploy template — see [`render.yaml`](./render.yaml).
