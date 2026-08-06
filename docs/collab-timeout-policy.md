# Collab timeout policy

Status: Confirmed for implementation on 2026-08-06.

## Goal

Let collaboration turns share the Agent workflow's total wall-clock budget instead
of terminating otherwise-active review and revision turns at arbitrary default
phase limits. Keep deterministic protection against a silent or globally expired
run, and retain optional phase caps for explicit cost control.

## Budget hierarchy

The task and Pier continue to own the outer budget:

```text
Pier hard Agent timeout
  = task.agent.timeout_sec * agent_timeout_multiplier

Runtime soft deadline
  = Pier hard Agent timeout - cleanup_reserve_seconds
```

For the current DeepSWE tasks, the defaults remain:

- task Agent timeout: 5400 seconds;
- Agent timeout multiplier: 1.0;
- cleanup reserve: 300 seconds;
- runtime soft deadline: 5100 seconds;
- event-silence timeout: 600 seconds;
- minimum remaining time to start a turn: 120 seconds;
- strict mode: false.

Collab mode does not automatically increase the Agent timeout multiplier.

## Default turn limits

Initial modification, review, revision, and final revision have no independent
wall-clock cap by default. Each attempt receives the workflow's remaining soft
deadline:

```text
effective turn timeout = remaining workflow time
```

This is not an unbounded run. Pier's hard timeout, the runtime soft deadline, the
event-silence watchdog, and the minimum-turn admission threshold remain active.

Attempts continue to be controlled by `maxAgentAttempts` (default 2). The value is
an upper bound: a new attempt is not started when less than `minTurnSeconds`
remains.

## Optional phase caps

`--reviewer-timeout-seconds` and `--revision-timeout-seconds` remain available as
collab-only options, but have no default value. When explicitly provided:

```text
effective turn timeout = min(explicit phase cap, remaining workflow time)
```

The explicit values are absolute seconds and are not scaled by
`agent_timeout_multiplier`.

Validation rules:

- the options are rejected for single-Agent workflows;
- zero and negative values are invalid;
- an explicit phase cap must be at least `minTurnSeconds`;
- a missing or null plan field means no independent phase cap.

Existing job artifacts and manifests are historical records and are not migrated.

## Timeout classification

The runtime records the first locally triggered timeout source independently of
the adapter's terminal status:

- `total_deadline`: the workflow's remaining soft deadline was exhausted;
- `stage_timeout`: an explicit review or revision cap was exhausted;
- `event_silence`: no adapter event arrived for the configured silence interval.

All three map to the existing top-level `degradedReason = "timeout"`. The detailed
`timeoutKind` is preserved in the turn result, round metadata, orchestrator trace,
and runtime cleanup event. Adapter `done.status` remains diagnostic evidence but
does not determine whether the runtime-triggered abort was a timeout.

Ordinary adapter/process failures remain `reviewer_failed` or `revision_failed`.
Invalid review JSON remains `invalid_review_output`.

## Delivery semantics

Delivery behavior does not change:

- after a trusted checkpoint, timeout with `strict=false` produces a degraded but
  deliverable result;
- with `strict=true`, a degraded result is not deliverable;
- an initial modifier timeout before a trusted patch is not deliverable;
- a revision timeout rolls back to and delivers the previous trusted checkpoint;
- a reviewer timeout cannot produce a review, so no revision is started.

## Non-goals

This change does not modify task TOML files, Pier, cligent, Agent profiles, the
cleanup reserve, or the event-silence timeout. It also does not add a separate
initial-modifier timeout or automatically reserve time for later collab phases.

## Acceptance criteria

- A default review can run beyond the previous 600-second cap while events
  continue and total workflow time remains.
- A default revision can run beyond the previous 900-second cap under the same
  conditions.
- Event silence still aborts the attempt after 600 seconds by default.
- Explicit review and revision caps still terminate their respective attempts.
- `total_deadline`, `stage_timeout`, and `event_silence` are classified accurately,
  including when an adapter reports `done.status = "error"` after abort.
- Retries follow `maxAgentAttempts` while respecting the total deadline and
  `minTurnSeconds`.
- Single-Agent runs reject collab-only phase timeout options.
- Existing strict/degraded delivery semantics remain covered by tests.
