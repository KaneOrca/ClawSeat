# Fix-Up Delivery: Mapping Assertions and Scan Smoke Triage

## Files Changed

- `tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py`
- `tests/test_seat_template_populated_after_profile_create.py`
- `.agent/ops/install-nonint/DELIVERY-FIXUP-MAPPING-AND-SCAN.md`

## Lane A: Mapping Test Updates

Updated the two mapping tests to match the current dedicated role-skill model from
`core/scripts/seat_skill_mapping.py` instead of the old placeholder assumption.

Changes made:

- reviewer sandbox skill-set now expects:
  - `reviewer`
  - `clawseat`
  - `gstack-harness`
  - `tmux-basics`
- template population test now checks dedicated role skills for:
  - `builder`
  - `reviewer`
  - `qa`
  - `designer`
- ancestor / planner / memory expectations remain aligned with the existing template-copy design

Lane A verification:

```bash
pytest -q \
  tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py \
  tests/test_seat_template_populated_after_profile_create.py
```

Result:

- `7 passed in 0.70s`

## Lane B: Scan Smoke Triage

Triage target:

```bash
pytest -vv \
  tests/test_scan_project_smoke.py::test_clawseat_shallow_scan \
  tests/test_scan_project_smoke.py::test_query_integration_dev_env
```

Result:

- `2 failed in 0.14s`

Classification:

- `test_clawseat_shallow_scan`: pre-existing unrelated
- `test_query_integration_dev_env`: pre-existing unrelated

Reasoning:

- Both failures are the same root cause: the test hardcodes `CLAWSEAT_REPO = /Users/ywf/.clawseat` and expects that path to scan as a Python repo.
- On this machine, `/Users/ywf/.clawseat` currently contains only:
  - `machine.toml`
- So the scanner correctly produces `python=False`, which makes both `...["python"] is True` assertions fail.
- This does not look like a round-3/4/5 regression in `scan_project.py`; it is an environment/test-contract mismatch.
- Because the requested rule was “if pre-existing unrelated -> document only”, no patch was applied for Lane B.

Failure summary:

- `tests/test_scan_project_smoke.py::test_clawseat_shallow_scan`
  - `assert data["python"] is True`
  - actual: `False`
- `tests/test_scan_project_smoke.py::test_query_integration_dev_env`
  - `assert facts[0]["data"]["python"] is True`
  - actual: `False`

## Final Test Results

- Lane A mapping tests:
  - `7 passed in 0.70s`
- Lane B triage targets:
  - `2 failed in 0.14s`

No commit was created.
