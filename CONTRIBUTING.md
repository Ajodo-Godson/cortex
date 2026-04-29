# Contributing to Cortex

Thanks for your interest. This document covers how to get set up and what's open for contribution.

## Setup

```bash
git clone https://github.com/your-username/cortex
cd cortex
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
cp .env.example .env
# edit .env with your API key
```

Run the test suite:

```bash
python -m pytest tests/
```

All 90 tests should pass with no external dependencies required (LLM calls are not made during tests).

## Project layout

```
agents/         Distiller, Bootstrapper, Retriever, Decay, MCP server
cli/            Click commands and entry point
core/           Schema, storage, session, events, coverage, LLM client
gardener/       Conflict detection and reconciliation
retrieval/      L1 AST filter (Rust), L2 semantic, L3 reranker
tests/          pytest suite
templates/      CORTEX.md template
```

## Build sequence

Cortex is built in phases. Do not skip phases or change their order without opening an issue first.

See [docs/IMPLEMENTATION_CHECKLIST.md](docs/IMPLEMENTATION_CHECKLIST.md) for the full plan.

## Open issues

The following phases are open for contributors:

| Phase | Description | Label |
|-------|-------------|-------|
| P5 | Cross-repo constraint inheritance | `help wanted` |
| P6 | Incident feed (Linear, PagerDuty) | `help wanted` |
| P8 | Impact scoring per constraint | `help wanted` |
| P9 | Viewer (graph dashboard, heat map) | `help wanted` |

Pick one of these or open an issue to propose something else before starting work.

## Ground rules

- Never put code in `constraint` fields
- Keep L1 retrieval in Rust
- Mark bootstrapped constraints `source: "inferred"` with max confidence `0.7`
- Build each phase against at least 10 real examples before marking done
- Never silently lose a session log

## Pull requests

- One logical change per PR
- Tests required for new behavior
- Run `python -m pytest tests/` before pushing — CI will reject failures
- Keep commit messages short and in the present tense

## Questions

Open a GitHub Discussion or file an issue.
