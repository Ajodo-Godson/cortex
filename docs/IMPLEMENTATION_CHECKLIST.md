# CORTEX Implementation Checklist

This checklist translates `docs/CORTEX_README_v3.md` into an execution-oriented build plan. It is ordered to match the README's required build sequence.

## Ground Rules

- [ ] Do not deviate from phase order without explicitly revisiting the architecture
- [ ] Build each phase to work on at least 10 real examples before moving on
- [ ] Never put code in `constraint` fields
- [ ] Never skip the Distiller eval harness
- [ ] Keep L1 retrieval in Rust
- [ ] Mark bootstrapped constraints as `source: "inferred"` with max confidence `0.7`
- [ ] Use synthetic cases for Gardener duels
- [ ] Never silently lose a session log
- [ ] Build P2 before P3

## P0: CLI Skeleton

### Package and repo setup

- [ ] Create Python package layout for `cli/`, `core/`, `agents/`, `retrieval/`, `gardener/`, `viewer/`, `tests/`, and `templates/`
- [ ] Add packaging and dependency metadata
- [ ] Add a `cortex` CLI entry point
- [ ] Add a starter `README.md` in the project root if needed

### Session state

- [ ] Define `.cortex/session.lock` JSON schema with PID, start time, repo path, and session log path
- [ ] Implement session lock read/write helpers
- [ ] Implement active-session detection
- [ ] Implement orphan-session detection
- [ ] Handle missing or corrupt session lock files gracefully

### `cortex start`

- [ ] Detect whether the current directory is a git repo
- [ ] Detect whether `.cortex/` exists
- [ ] On first run, prompt for bootstrap unless `--no-bootstrap` is set
- [ ] On orphaned prior session, offer recovery/distillation
- [ ] Support `--dry-run`
- [ ] Support `--verbose`
- [ ] Support `--boost <domain>`
- [ ] Write `CORTEX.md` from a template unless in dry-run mode
- [ ] Start an Observer placeholder/background process
- [ ] Persist session state to `.cortex/session.lock`
- [ ] Print a clear readiness summary

### `cortex stop`

- [ ] Detect and handle no-active-session case without crashing
- [ ] Stop the Observer using PID from the lock file
- [ ] Trigger Distiller placeholder on the session log
- [ ] Remove `CORTEX.md`
- [ ] Remove or archive session lock cleanly
- [ ] Warn clearly if distillation fails

### Supporting CLI commands

- [ ] Implement `cortex status`
- [ ] Stub `constraints`, `diff`, `show`, `bootstrap`, `distill`, `garden`, and `view`
- [ ] Keep output human-readable and stable enough for tests

## P1a: Schema and Distiller

- [ ] Build `tests/test_distiller.py` first with 10 ground-truth correction events
- [ ] Define the canonical constraint schema
- [ ] Implement schema validation
- [ ] Implement Distiller input contract
- [ ] Implement Distiller output validation
- [ ] Ensure Distiller produces operational constraints, not summaries
- [ ] Verify that injected output would have prevented the original correction

## P1b: Observer and Hook

- [ ] Implement Observer lifecycle management
- [ ] Capture session log output to `.cortex/sessions/`
- [ ] Integrate local classifier via Ollama/Qwen placeholder
- [ ] Apply `0.7` confidence threshold
- [ ] Log low-confidence events without promoting them
- [ ] Add post-commit or equivalent correction-event hook path

## P1c: Bootstrapper

- [ ] Use PyGit2, not GitPython
- [ ] Detect revert/fix commit sequences
- [ ] Seed inferred constraints from git history
- [ ] Support `cortex bootstrap --since <range>`
- [ ] Run mining in parallel batches

## P1d: Retrieval Stack

- [ ] Implement `retrieval/ast_filter.rs`
- [ ] Ensure L1 completes under 10ms
- [ ] Implement semantic retrieval placeholder
- [ ] Implement schema-aware reranking placeholder
- [ ] Select top `N` constraints for session injection
- [ ] Render selected constraints into `CORTEX.md`

## P2: Agent Self-Writing

- [ ] Design `cortex_flag` MCP tool contract
- [ ] Accept code context, error context, and learned rule
- [ ] Trigger Distiller immediately on candidate constraints
- [ ] Store real-time constraints with correct provenance

## P3: Gardener

- [ ] Implement conflict detection
- [ ] Generate synthetic duel cases
- [ ] Run reconciliation logic outside the live codebase
- [ ] Generate meta-constraints

## P4: Constraint Decay

- [ ] Detect refactors affecting `ast_triggers` and scoped services
- [ ] Flag potentially stale constraints
- [ ] Decrease confidence proportionally to code drift
- [ ] Route flagged constraints into Gardener review

## P5: Cross-Repo Inheritance

- [ ] Create `.cortex/shared/` namespace support
- [ ] Detect repeated patterns across repos
- [ ] Promote shared constraints
- [ ] Check shared constraints during retrieval before local ones

## P6: Incident Feed

- [ ] Design incident ingestion command surface
- [ ] Add at least one source integration such as Linear or PagerDuty
- [ ] Create incident-specific Distiller prompt flow
- [ ] Preserve direct evidence chain to incident references

## P7: Coverage Map

- [ ] Log retrieval hits into `.cortex/coverage.json`
- [ ] Aggregate untouched or unconstrained areas
- [ ] Build file-tree heat map inputs for the Viewer

## P8: Impact Scoring

- [ ] Track when a constraint is injected
- [ ] Track whether relevant code was touched
- [ ] Track whether a correction event still occurred
- [ ] Compute per-constraint effectiveness metrics

## P9: Viewer

- [ ] Build graph dashboard
- [ ] Add growth timeline
- [ ] Add coverage heat map
- [ ] Add impact score views
- [ ] Keep Viewer secondary to core system reliability

## Initial Deliverables

- [ ] Runnable local `cortex start`, `stop`, and `status`
- [ ] Basic test coverage for session lifecycle
- [ ] Generated `CORTEX.md` template path
- [ ] Placeholder integration seams for Observer, Distiller, Bootstrapper, and Retriever
