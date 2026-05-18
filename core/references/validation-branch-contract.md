# Validation Branch Contract

Reference for planners when merging approved task work into the operator-validation branch.
See also: `core/lib/validation_branch.py` for the importable contract and helpers.

## Cartooner Configuration

- **Validation branch**: `review/latest`
- **Main protected**: yes — never merges directly; requires operator sign-off on `review/latest` first
- **Local validation port**: `15173`

## Local-First Validation (cf025)

`review/latest` is the **local operator validation branch**. Remote push to GitHub is **not required** for operator testing — the operator validates locally against the merged `review/latest` branch.

- Planner merges accepted task work to local `review/latest` and reports the commit hash.
- Operator runs Cartooner locally on port `15173` and validates the feature.
- Remote push of `review/latest` to GitHub happens only when explicitly requested (e.g. for CI, backup, or cross-machine handoff).
- `main` is only updated (by memory) after operator sign-off — remote push of `main` always requires explicit operator request.

**Dirty-worktree awareness**: When the operator reports unexpected behavior in local validation, first check `git status` on the `review/latest` branch — staged or unstaged changes may be influencing the local build without appearing in the merge commit.

## Required Delivery Fields

When relaying final delivery to memory, planner must include a `## Validation Branch` section with:

| Field | Required | Notes |
|-------|----------|-------|
| `branch` | yes | e.g. `review/latest` |
| `commit_hash` | yes | commit merged onto the validation branch |
| `ci_status` | yes | `pass`, `fail`, `no_log_startup_failure`, `billing_failure`, `skipped`, or `unknown` |
| `tests_run` | recommended | list of test commands/suites confirmed passing |
| `conflict_files` | when conflicts | list of files with merge conflicts — must resolve before sign-off |
| `unresolved_risks` | when present | items that must be addressed before `main` |

## CI Failure Classification

Not all CI failures are equal. The following are **non-blocking** for pre-main operator validation:

- `no_log_startup_failure` — no log available, workflow startup failure
- `billing_failure` — GitHub Actions billing/usage limit
- `skipped` — CI was not triggered
- `unknown` — CI status unresolved

When CI is non-blocking, the operator proceeds with local validation on `review/latest` without waiting for GitHub CI. `main` remains protected and only accepts the merge after operator sign-off.

A `fail` status (real test failures) and `pass` are the only statuses that represent a definitive CI outcome.

## Importable Helpers

```python
from validation_branch import (
    ValidationBranchContract,
    classify_ci_status,
    is_ci_nonblocking_for_premerge,
    build_delivery_guidance,
)

# Build a contract after merging to review/latest
contract = ValidationBranchContract(
    branch="review/latest",
    commit_hash="abc123",
    tests_run=["pytest tests/ -q", "cd apps/web && pnpm test"],
    ci_status="no_log_startup_failure",
)

# Validate required fields
ok, missing = contract.validate()

# Check if CI blocks
if not contract.is_ci_nonblocking:
    # wait for CI
    pass

# Generate DELIVERY.md section
guidance = build_delivery_guidance(contract)
```
