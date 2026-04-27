# Federated KB Schema

ClawSeat uses a federated knowledge model: each seat owns its domain KB, and Memory reads those KBs directly to synthesize cross-seat knowledge. Memory is not the sole store of project knowledge.

## Path Conventions

Seat KBs live under the project registry home:

```text
~/.agents/projects/<project>/<seat>-kb/
├── builder-kb/decisions.jsonl
├── planner-kb/decisions.jsonl
├── reviewer-kb/observations.jsonl
├── qa-kb/doc_code_alignment.jsonl
├── qa-kb/test_results.jsonl
├── qa-kb/task_commit_gaps.jsonl
└── qa-kb/summary.json
```

Concrete paths:

- `~/.agents/projects/<project>/builder-kb/decisions.jsonl`
- `~/.agents/projects/<project>/planner-kb/decisions.jsonl`
- `~/.agents/projects/<project>/reviewer-kb/observations.jsonl`
- `~/.agents/projects/<project>/qa-kb/doc_code_alignment.jsonl`
- `~/.agents/projects/<project>/qa-kb/test_results.jsonl`
- `~/.agents/projects/<project>/qa-kb/task_commit_gaps.jsonl`
- `~/.agents/projects/<project>/qa-kb/summary.json`

Project identity and repo location come from `~/.clawseat/projects.json`. When a seat needs repo files, resolve the project through its `repo_path` field, then read project-local docs and code from that repo.

## Public Fields

Every JSONL record must include these fields:

```json
{
  "ts": "ISO8601",
  "task_id": "string",
  "project": "string",
  "seat": "builder|planner|reviewer|qa|memory",
  "title": "string",
  "detail": "string"
}
```

Seat-specific records may add fields. Recommended additions:

- Builder: `decision_type`, `files_affected[]`, `constraints[]`
- Planner: `decision_type`, `alternatives_considered[]`, `priority_reason`
- Reviewer: `risk_type`, `severity`, `status`
- QA: `issue_id`, `doc_file`, `code_file`, `issue_type`, `severity`, `status`, `first_seen`, `last_seen`, `resolved_at`, `model`

## Memory Read Protocol

- Memory reads seat KB files directly from disk.
- There is no message protocol for KB reads.
- Memory resolves project paths through `projects.json` and then reads `~/.agents/projects/<project>/<seat>-kb/`.
- Memory does not write into another seat's KB.
- When Memory synthesizes cross-seat conclusions, it writes only to its own Memory KB or event log.
- If a seat KB file is missing, Memory treats that as `not_in_federated_kb` for that seat, not as a fatal error.

## Retention Rules

- JSONL files are append-only.
- Do not delete historical observations.
- Resolved or completed facts are represented with status fields such as `resolved`, `completed`, or `superseded`.
- `summary.json` may be overwritten and only needs to contain the latest aggregate snapshot.
- If a known issue is seen again, append or update according to the owning seat's documented rule, but preserve the original `first_seen` timestamp.

## Ownership

- Builder owns implementation decisions and technical constraints.
- Planner owns dispatch, priority, and alternative-selection decisions.
- Reviewer owns review observations and recurring risk patterns.
- QA owns doc-code alignment, task-commit gaps, and test results.
- Memory owns orphan knowledge: cross-seat synthesis, north-star drift judgment, user clarification records, and major event chains.
