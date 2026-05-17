# Acceptance Mechanical Command Contract

Reference for memory/planner when authoring `acceptance_criteria.mechanical` commands.
See also: `core/lib/acceptance_criteria.py` for runtime validation (cf015/cf016).

## Scope-Guard (Forbidden-File Guard)

When a brief must verify that no forbidden files are edited, use the **portable Python-filter form**:

```
cd {repo_root} && git diff --name-only origin/main...HEAD | python3 -c "
import sys
forbidden_suffixes = ('tasks.queue.jsonl', 'QUALITY.md', 'WORKSPACE_CONTRACT.toml',
                      'project.toml', 'TEAM_OWNERSHIP.md')
bad = []
for line in sys.stdin:
    p = line.strip()
    if not p:
        continue
    if '/handoffs/' in p or '/secrets/' in p or any(p.endswith(f) for f in forbidden_suffixes):
        bad.append(p)
print('\n'.join(bad))
raise SystemExit(1 if bad else 0)
"
```

Key requirements for this pattern:
- **Explicit range**: `origin/main...HEAD` scopes the diff to the task branch. A bare `git diff --name-only` compares working tree vs. index and picks up unrelated dirty state.
- **Python filtering**: `python3 -c` is POSIX-portable. A pipe followed by `!` is not valid POSIX sh syntax and is fragile in bash.

The importable constant `SCOPE_GUARD_PORTABLE_TEMPLATE` in `core/lib/acceptance_criteria.py` provides a parameterised version of this pattern.

## Shell Portability Rules for Mechanical Commands

| Pattern | Status | Portable Alternative |
|---------|--------|----------------------|
| `cmd \| ! grep X` | Invalid POSIX | `cmd \| grep -v X` |
| `cmd \| ! rg X` | Invalid POSIX | `cmd \| rg -v X` |
| `git diff --name-only \| …` | Scans working tree | `git diff origin/main...HEAD --name-only \| …` |
| `git diff --name-only` alone | Scans working tree | `git diff origin/main...HEAD --name-only` |

## Validation

`core/lib/acceptance_criteria.py` enforces these rules at brief-queue time:
- `brief_acceptance_ready()` returns `(False, reason)` when either forbidden pattern is detected.
- `run_mechanical()` auto-normalises pipe-negation and fails bare-diff commands with a diagnostic.
