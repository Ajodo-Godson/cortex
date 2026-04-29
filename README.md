# Cortex

**A persistent constraint layer for AI coding agents.**

Cortex watches your coding sessions, learns from every correction you make, and silently injects the right rules into the next session before mistakes happen again.

---

## What it does

When you correct an AI agent — reverting a commit, fixing a bug it introduced, or overriding a bad pattern — Cortex:

1. **Observes** the correction event in real time
2. **Distills** it into a structured constraint ("never do X because Y; instead do Z")
3. **Retrieves** the most relevant constraints at the start of each new session
4. **Injects** them into `CORTEX.md`, which agents read as part of their context

Over time, your agent stops repeating the same classes of mistakes.

---

## Architecture

```
cortex start
    └── Observer (background)        watches the session log
    └── Retriever (L1 → L2 → L3)     selects top-N constraints → CORTEX.md

coding session
    └── Agent reads CORTEX.md        before every response
    └── You correct a mistake        → correction event logged

cortex stop
    └── Distiller                    converts events → new constraints
    └── CORTEX.md removed
```

**Three retrieval layers:**

| Layer | What it does | Latency |
|-------|-------------|---------|
| L1 – AST filter | Matches `ast_triggers` against recently-touched files (Rust) | < 10 ms |
| L2 – Semantic | Token overlap between branch context and constraint text | < 1 ms |
| L3 – Reranker | Source, confidence, and scope-aware final ranking | < 1 ms |

**Supporting agents:**

- **Bootstrapper** — mines git history (revert/fix sequences) to seed initial constraints
- **Gardener** — detects contradictions between constraints and reconciles them
- **Decay** — lowers confidence on constraints whose code anchors have drifted away
- **MCP server** — `cortex_flag` tool lets agents self-write constraints mid-session

---

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[anthropic]"   # or [openai] or [all]

cp .env.example .env
# edit .env with your API key

cd your-project
cortex start
# run your AI coding session
cortex stop
```

On first run, Cortex bootstraps from your git history and creates `.cortex/` in your repo.

---

## Configuration

Cortex is model-agnostic. Set these in `.env` or your shell:

| Variable | Default | Description |
|----------|---------|-------------|
| `CORTEX_MODEL` | `claude-opus-4-7` | Any model string |
| `CORTEX_API_KEY` | — | Overrides provider-specific key |
| `CORTEX_BASE_URL` | — | OpenAI-compatible base URL (NVIDIA NIM, Ollama, etc.) |
| `ANTHROPIC_API_KEY` | — | Anthropic key (used when model starts with `claude-`) |
| `ANTHROPIC_BASE_URL` | — | Custom Anthropic-compatible base URL |
| `OPENAI_API_KEY` | — | OpenAI key (used for all other models) |

**Examples:**

```env
# Anthropic
CORTEX_MODEL=claude-opus-4-7
ANTHROPIC_API_KEY=sk-ant-...

# NVIDIA NIM
CORTEX_MODEL=meta/llama-3.1-70b-instruct
CORTEX_API_KEY=nvapi-...
CORTEX_BASE_URL=https://integrate.api.nvidia.com/v1

# Local Ollama
CORTEX_MODEL=llama3
CORTEX_BASE_URL=http://localhost:11434/v1
```

---

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

---

## Installation

**Core only (no LLM distillation):**
```bash
pip install -e .
```

**With Anthropic SDK:**
```bash
pip install -e ".[anthropic]"
```

**With OpenAI-compatible SDK (NVIDIA NIM, Ollama, Azure, etc.):**
```bash
pip install -e ".[openai]"
```

**With MCP server support:**
```bash
pip install -e ".[mcp]"
```

**Everything:**
```bash
pip install -e ".[all]"
```

---

## Constraint schema

Each constraint is a YAML file in `.cortex/constraints/`:

```yaml
constraint_id: avoid-commit-inside-loop-001
context: "Avoid committing inside a retry loop"
never_do:
  - "Never call git commit from inside a loop that retries on failure"
because: "Creates orphan commits and corrupts history on retry"
instead: "Stage all changes, exit the loop, then commit once"
scope:
  services: []
  ast_triggers: ["git commit", "retry", "for", "while"]
  error_codes: []
confidence: 0.85
source: observed
meta_type: operational_constraint
```

---

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| P0 | CLI skeleton | ✅ done |
| P1a | Schema and Distiller | ✅ done |
| P1b | Observer and hook | ✅ done |
| P1c | Bootstrapper | ✅ done |
| P1d | Retrieval stack | ✅ done |
| P2 | Agent self-writing (MCP) | ✅ done |
| P3 | Gardener | ✅ done |
| P4 | Constraint decay | ✅ done |
| P7 | Coverage map | ✅ done |
| P5 | Cross-repo inheritance | 🔲 open |
| P6 | Incident feed | 🔲 open |
| P8 | Impact scoring | 🔲 open |
| P9 | Viewer | 🔲 open |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Open issues are labeled `help wanted`.

---

## License

MIT
