---
name: creative-patrol
description: >
  Deprecated creative patrol reference retained only for backward compatibility
  with older ClawSeat creative workflows. Use when reading legacy
  documentation, migrating old creative-patrol mentions, or understanding why
  creative-designer now owns creative review and scoring. Also use when
  preserving historical handoff context during compatibility cleanup. Covers
  legacy passive scoring semantics and migration notes. Do NOT use for new
  creative reviews, new scoring work, active dispatch, implementation, or any
  task that can use creative-designer.
deprecated: true
superseded_by: creative-designer
---

> **⚠ DEPRECATED**: This skill has been superseded by `creative-designer`, which now handles both creative review and quality assessment. Do not use in new projects.

# Creative Patrol

For new projects, use `creative-designer`. `creative-patrol` is retained for historical reference only.
Writing boundaries: see [`core/references/seat-ownership.md`](../../references/seat-ownership.md).

`creative-patrol` was the passive scoring specialist in the ClawSeat creative chain. It is no longer dispatched in new workflows. All scoring (cs-score) and review capabilities now live in `creative-designer`.

## Capability Skill Refs

- **[cs-score](../cs-score/SKILL.md)** — 主要能力：rubric 评分（deliverable_path + brief_path → score.json + report.md）；默认 rubric、CONTRACT / ACCEPTANCE 定义在此
