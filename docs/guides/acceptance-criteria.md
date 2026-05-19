# ClawSeat Acceptance Criteria Authoring Guide

Acceptance criteria govern whether a task can close. The executor (CF042+)
runs mechanical commands, routes reviewer items to the declared reviewer seat,
and batches operator questions for the human operator.

## Three Routes

### mechanical — machine-deterministic shell commands

Each mechanical criterion must be a command the acceptance executor can run and
get a binary pass/fail from the exit code alone. No human interpretation.

```yaml
acceptance_criteria:
  mechanical:
    # String form — simplest
    - "bash -lc 'cd /path && python3 -m pytest tests -q -k \"filter\"'"

    # Dict form — adds description and optional attributes
    - command: "bash -lc 'cd /path && python3 -m pytest tests/focused -q'"
      description: "Focused behavior tests pass."

    # Dict form with diagnostic baseline (see below)
    - command: "bash -lc 'cd /path && python3 -m pytest tests -q'"
      description: "Full-suite baseline probe."
      diagnostic: true
```

**Rule: hard mechanical commands must be machine-deterministic.**
Do not write human OR qualifiers inside mechanical descriptions. The acceptance
executor cannot honor natural-language conditions — only binary exit codes.

```
# WRONG — human qualifier is not enforceable; executor only sees exit code
- "pytest tests -q"   # description with "passes OR planner documents pre-existing failures"

# RIGHT — separate the concerns cleanly
- command: "pytest tests -q -k 'focused_filter'"
  description: "Focused implementation tests pass."
- command: "pytest tests -q"
  description: "Full-suite baseline probe — unrelated pre-existing failures non-blocking."
  diagnostic: true
```

### reviewer — planner or reviewer seat criteria

Reviewer items are dispatched to the team's reviewer seat (or planner self-review
for dev-minimal teams). They remain `PENDING` until the reviewer relays.

```yaml
  reviewer:
    - "Planner confirms the implementation targets framework scope only."
    - "Planner confirms relevant failures still block aggregate acceptance."
```

### operator — human-answered questions

Operator items are batched into a pending-answer file. The human operator
answers them manually before the task can close as PASS.

```yaml
  operator:
    - "Closeout states which paths changed."
    - "Closeout states whether reinstall is recommended."
```

## Diagnostic Baseline (CF043)

A **diagnostic** criterion runs its command and captures output, but a non-zero
exit code is recorded as `diagnostic` (not `fail`) and does NOT cause aggregate
FAIL. Use this for full-suite probes where pre-existing unrelated failures exist.

**Relevant failures must remain non-diagnostic.** Diagnostic is opt-in only.

### Option A: `diagnostic: true` in the brief

```yaml
acceptance_criteria:
  mechanical:
    - command: "bash -lc 'cd /path && python3 -m pytest tests -q -k relevant_filter'"
      description: "Focused implementation tests — relevant failures block."
    - command: "bash -lc 'cd /path && python3 -m pytest tests -q'"
      description: "Full-suite baseline probe — unrelated pre-existing failures non-blocking."
      diagnostic: true
```

### Option B: `--baseline-criteria N` at acceptance-run time

When the brief is already written (memory-owned) and cannot be edited, the
planner can pass criterion indices at run time:

```sh
agent_admin acceptance run \
  --project my-project --team my-team \
  --task-id MY-TASK \
  --actor planner@claude \
  --baseline-criteria 1          # index 1 = full-suite criterion, non-blocking
```

Multiple indices: `--baseline-criteria 1,3`.

### What counts as diagnostic output

In the acceptance log and receipt:
- `result: "diagnostic"` — criterion ran, non-zero exit, non-blocking
- `result: "pass"` — command exited 0 (always a gate regardless of diagnostic flag)
- `result: "fail"` — non-zero exit on a non-diagnostic criterion; blocks aggregate

Aggregate verdict logic:
- `FAIL` if any non-diagnostic mechanical criterion fails
- `PENDING` if mechanical PASS but reviewer/operator items outstanding
- `PASS` only when all three routes are satisfied

## Template Summary

```yaml
acceptance_criteria:
  mechanical:
    # Always: focused, machine-deterministic, binary pass/fail
    - command: "bash -lc 'cd /path && python3 -m pytest tests -q -k \"keyword\"'"
      description: "Focused behavior tests pass — relevant failures block."

    # When needed: baseline probe for full-suite evidence
    - command: "bash -lc 'cd /path && python3 -m pytest tests -q'"
      description: "Full-suite baseline probe."
      diagnostic: true    # non-zero exit → diagnostic, not fail

    # Scope guard (always non-diagnostic)
    - command: "bash -lc 'cd /path && ! git diff --name-only ... | grep product-src'"
      description: "No product source files changed."

  reviewer:
    - "Planner self-review confirms ..."

  operator:
    - "Closeout states ..."
```
