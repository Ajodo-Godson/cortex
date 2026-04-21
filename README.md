# CORTEX

Implementation scaffold for the CORTEX system described in [docs/CORTEX_README_v3.md](docs/CORTEX_README_v3.md).

## Current status

This repo currently provides:

- A starter project layout
- A minimal `cortex` CLI
- Session lock management
- Placeholder hooks for retrieval, observation, distillation, and bootstrap

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cortex start --dry-run
cortex status
```
