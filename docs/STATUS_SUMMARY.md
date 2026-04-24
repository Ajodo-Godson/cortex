# CORTEX Status Summary

## Current State

- `P0` is working:
  - `cortex start/stop/status`
  - `CORTEX.md` generation and cleanup
  - session lock handling
  - stale/orphan recovery
- `P1a` is mostly in place:
  - real schema models
  - deterministic Distiller
  - 10 Distiller fixtures
  - YAML constraint storage in `.cortex/constraints/`
- `P1b` is partially scaffolded:
  - observer writes structured session logs
  - queued correction events can be ingested
  - sample observer signals can be classified into correction events

## Main Test Commands

```bash
# Reinstall local package
python -m pip install -e .

# Basic lifecycle
cortex start --dry-run --no-bootstrap
cortex start --no-bootstrap
cortex status
cortex stop

# Manual correction-event path
cortex start --no-bootstrap
cortex record --sample
cortex distill
cortex constraints
cortex show db-transaction-payload-001
cortex stop

# Observer queue path
cortex start --no-bootstrap
cortex record --sample --queue
sleep 2
cortex stop
cortex constraints

# Observer signal classification path
cortex start --no-bootstrap
cortex signal --sample token_refresh
sleep 2
cortex stop
cortex constraints

# Retrieval check
cortex start --dry-run --boost auth --verbose
```

## What’s Next

- finish `P1b` properly:
  - confidence scoring
  - threshold handling
  - low-confidence skip/log path
  - real observer signal sources
