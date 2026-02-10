# openclaw-cli

CLI utilities for [OpenClaw](https://github.com/openclaw/openclaw) — tail logs, inspect sessions, and more.

## Install

```bash
# Run directly (no install needed)
uvx openclaw-cli tail

# Or install globally
uv tool install openclaw-cli
```

## Commands

### `ocli tail`

Tail session logs across all agents in real time. Shows user and assistant messages with agent ID, model, cost, and message text.

```bash
ocli tail                      # Tail all agents, live
ocli tail -a main              # Tail only the "main" agent
ocli tail -n 20                # Show last 20 messages, then follow
ocli tail -n 10 --no-follow    # Show last 10 messages and exit
ocli tail --deleted             # Include deleted sessions
```

**Output format:**

```
14:23:01 [main] (b80790f1) USER  what's the weather like?
14:23:05 [main] (b80790f1) AI(claude-sonnet-4-20250514) $0.0032 It's currently 65°F and sunny...
```

Each line shows:
- **Timestamp** — local time
- **Agent** — which agent (e.g. `main`, `penny`)
- **Session** — first 8 chars of the session ID
- **Role** — `USER` or `AI(model)`
- **Cost** — per-response cost (assistant only)
- **Text** — message content (collapsed to one line)

## Development

```bash
# Clone and set up
git clone https://github.com/openclaw/openclaw-cli.git
cd openclaw-cli
uv sync

# Run locally
uv run ocli tail -n 5 --no-follow

# Lint
uv run ruff check src/
```

## License

MIT
