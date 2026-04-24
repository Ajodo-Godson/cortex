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

- [x] Create Python package layout for `cli/`, `core/`, `agents/`, `retrieval/`, `gardener/`, `viewer/`, `tests/`, and `templates/`
- [x] Add packaging and dependency metadata
- [x] Add a `cortex` CLI entry point
- [ ] Add a starter `README.md` in the project root if needed

### Session state

- [x] Define `.cortex/session.lock` JSON schema with PID, start time, repo path, and session log path
- [x] Implement session lock read/write helpers
- [x] Implement active-session detection
- [x] Implement orphan-session detection
- [x] Handle missing or corrupt session lock files gracefully

### `cortex start`

- [x] Detect whether the current directory is a git repo
- [x] Detect whether `.cortex/` exists
- [x] On first run, prompt for bootstrap unless `--no-bootstrap` is set
- [x] On orphaned prior session, offer recovery/distillation
- [x] Support `--dry-run`
- [x] Support `--verbose`
- [x] Support `--boost <domain>`
- [x] Write `CORTEX.md` from a template unless in dry-run mode
- [x] Start an Observer placeholder/background process
- [x] Persist session state to `.cortex/session.lock`
- [x] Print a clear readiness summary

### `cortex stop`

- [x] Detect and handle no-active-session case without crashing
- [x] Stop the Observer using PID from the lock file
- [x] Trigger Distiller placeholder on the session log
- [x] Remove `CORTEX.md`
- [x] Remove or archive session lock cleanly
- [x] Warn clearly if distillation fails

### Supporting CLI commands

- [x] Implement `cortex status`
- [x] Stub `constraints`, `diff`, `show`, `bootstrap`, `distill`, `garden`, and `view`
- [x] Keep output human-readable and stable enough for tests

## P1a: Schema and Distiller

- [x] Build `tests/test_distiller.py` first with 10 ground-truth correction events
- [x] Define the canonical constraint schema
- [x] Implement schema validation
- [x] Implement Distiller input contract
- [x] Implement Distiller output validation
- [x] Ensure Distiller produces operational constraints, not summaries
- [x] Verify that injected output would have prevented the original correction

## P1b: Observer and Hook

- [x] Implement Observer lifecycle management
- [x] Capture session log output to `.cortex/sessions/`
- [x] Integrate local classifier via Ollama/Qwen placeholder
- [x] Apply `0.7` confidence threshold
- [x] Log low-confidence events without promoting them
- [x] Add post-commit or equivalent correction-event hook path

## P1c: Bootstrapper

- [x] Use PyGit2, not GitPython
- [x] Detect revert/fix commit sequences
- [x] Seed inferred constraints from git history
- [x] Support `cortex bootstrap --since <range>`
- [x] Run mining in parallel batches

## P1d: Retrieval Stack

- [x] Implement `retrieval/ast_filter.rs`
- [x] Ensure L1 completes under 10ms
- [x] Implement semantic retrieval placeholder
- [x] Implement schema-aware reranking placeholder
- [x] Select top `N` constraints for session injection
- [x] Render selected constraints into `CORTEX.md`

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

- [x] Runnable local `cortex start`, `stop`, and `status`
- [x] Basic test coverage for session lifecycle
- [x] Generated `CORTEX.md` template path
- [x] Placeholder integration seams for Observer, Distiller, Bootstrapper, and Retriever
