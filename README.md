# nanobot on Render

Deploy [nanobot](https://github.com/HKUDS/nanobot) — a lightweight, self-hostable AI agent — on Render in one click. Get your own private agent with a browser chat UI, tools, and persistent memory.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Ho1yShif/nanobot)

## What you get

One Render web service running nanobot's `gateway` and its bundled WebUI. You chat with the agent from your browser; it can use tools (web search/fetch, filesystem, shell, MCP servers) and remembers past sessions on a persistent disk. Access is gated by a secret you set.

## Cost expectations

This is not a free deploy. Expect:

- **Render Starter plan** — ~$7/mo for the web service.
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

## Environment variables

Render prompts for these on deploy (both are `sync: false`, so no secret is ever committed):

| Variable | What it's for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Powers the agent's LLM calls (default model `anthropic/claude-opus-4-8`). | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `NANOBOT_WEB_TOKEN` | The access secret for the WebUI — the only gate on your public agent. | Generate it yourself (see step 1 above): `openssl rand -hex 32` or `python3 -c "import secrets; print(secrets.token_hex(32))"`. |

`PORT` is set for you in the Blueprint. Configuration lives in [`render-config.json`](./render-config.json); the two secrets are referenced there as `${ANTHROPIC_API_KEY}` and `${NANOBOT_WEB_TOKEN}` and resolved at startup.

## Security note — read this

A deployed nanobot is a capable agent: anyone who gets past `NANOBOT_WEB_TOKEN` can make it run shell commands and use tools **inside its container, with your API key**.

- **Keep `NANOBOT_WEB_TOKEN` secret and strong.** It's the only thing standing between the internet and your agent.
- This template ships hardened defaults (`restrictToWorkspace`, self-modification writes off) and runs as a non-root user in an isolated container — but the token is still your primary defense.
- Rotate the token (and your API key) if you suspect it leaked.

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
