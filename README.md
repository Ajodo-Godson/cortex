# Cortex

A persistent constraint layer for AI coding agents. Cortex watches your sessions, learns from every correction, and injects the right rules into the next session before the same mistake happens again.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/Ajodo-Godson/cortex/main/setup.sh | bash
```

Then edit `~/.cortex-src/.env` to add your API key.

<details>
<summary>Manual install</summary>

**Requirements:** Python 3.11+, git, Rust (for the AST filter — `curl https://sh.rustup.rs | sh`)

```bash
# Install pipx if you don't have it
brew install pipx && pipx ensurepath

# Clone and install
git clone https://github.com/Ajodo-Godson/cortex
cd cortex
pipx install -e ".[anthropic]"   # or [openai] or [all]
cp .env.example .env             # add your API key

# If you plan to use the MCP server with Codex or Claude Code
pipx inject cortex "mcp>=1.0"

# Add the provider SDK matching your CORTEX_MODEL
pipx inject cortex "anthropic>=0.50"   # for claude-* models
# or
pipx inject cortex "openai>=1.0"       # for all other models (NVIDIA NIM, Ollama, etc.)
```

The `cortex` command is now available in any directory.

</details>

## Quickstart

```bash
cd your-project
cortex start
# open Claude Code or Codex and work as normal
cortex stop
```

`cortex start` injects your constraints into `CLAUDE.md` (Claude Code) and `AGENTS.md` (Codex) automatically. Both files are cleaned up on `cortex stop`. On first run, Cortex bootstraps from your git history and creates `.cortex/` in your repo.

## Agent setup

### Claude Code

Register the Cortex MCP server once:

```bash
claude mcp add --transport stdio cortex -- cortex mcp
```

During a session, Claude Code can call `cortex_flag` to self-write a constraint the moment it recognises a correction pattern — no manual step required.

### Codex CLI

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.cortex]
command = "cortex"
args = ["mcp"]
```

Codex will call `cortex_flag` the same way during sessions.

### What gets captured automatically

| Signal | How |
|--------|-----|
| `git revert` during a session | Observer (GitWatcher) |
| Commit with `fix:` / `hotfix:` prefix | Observer (GitWatcher) |
| Pytest failures | Observer (FailureWatcher) |
| Chat-level correction (agent redoes work) | Agent calls `cortex_flag` via MCP |

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
Phase P0–P4, P7 | CLI, Distiller, Observer, Bootstrapper, Retrieval, MCP, Gardener, Decay, Coverage are implemented already. 

P5 (Cross-repo inheritance), P6 (Incident feed) , P8 (Impact scoring) , P9(Viewer) are yet to be

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). P5, P6, P8, and P9 are open for contributors.
