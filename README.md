# Cortex

A persistent constraint layer for AI coding agents. Cortex watches your sessions, learns from every correction, and injects the right rules into the next session before the same mistake happens again.

## Installation

**Requirements:** Python 3.11+, git, Rust (for the AST filter — `curl https://sh.rustup.rs | sh`)

```bash
git clone https://github.com/Ajodo-Godson/cortex
cd cortex
python -m venv .venv && source .venv/bin/activate
pip install -e ".[anthropic]"   # or [openai] or [all]
cp .env.example .env            # add your API key
```

The `cortex` command is now available in your shell.

## Quickstart

```bash
cd your-project
cortex start
# run your AI coding session
cortex stop
```

On first run, Cortex bootstraps from your git history and creates `.cortex/` in your repo.

## CLI reference

```
cortex start [--dry-run] [--boost <domain>] [--no-bootstrap]
cortex stop
cortex status
cortex constraints [--filter <text>]
cortex show <constraint-id>
cortex bootstrap [--since <days>]
cortex distill [--log <path>] [--sample]
cortex record --sample | --event-file <path> [--queue]
cortex signal --sample deadlock|token_refresh|webhook_signature
cortex garden [--auto] [--deep]
cortex decay [--apply]
cortex coverage [--json]
cortex mcp [--transport stdio|sse]
```

## Configuration

| Variable | Description |
|----------|-------------|
| `CORTEX_MODEL` | Model to use (default: `claude-opus-4-7`) |
| `ANTHROPIC_API_KEY` | Required for `claude-*` models |
| `OPENAI_API_KEY` | Required for other models |
| `CORTEX_API_KEY` | Overrides either key above |
| `CORTEX_BASE_URL` | OpenAI-compatible base URL (NVIDIA NIM, Ollama, etc.) |

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| P0–P4, P7 | CLI, Distiller, Observer, Bootstrapper, Retrieval, MCP, Gardener, Decay, Coverage | ✅ |
| P5 | Cross-repo inheritance | 🔲 |
| P6 | Incident feed | 🔲 |
| P8 | Impact scoring | 🔲 |
| P9 | Viewer | 🔲 |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). P5, P6, P8, and P9 are open for contributors.
