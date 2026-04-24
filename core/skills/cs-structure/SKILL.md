---
name: cs-structure
description: Capability skill for structural planning — world-building, architecture documents, global outlines, and per-unit briefs. Interface contract only; tool-agnostic.
---

# CS-Structure — Structural Planning Capability

**Design principle**: Skill = WHAT (interface contract), not HOW (tool or executor).
The executor (creative-planner, engineering planner, etc.) adapts this contract to its runtime.

## CONTRACT

### INPUT (passed via TODO objective)

| Field | Type | Description |
|-------|------|-------------|
| `brief_path` | path | Project brief file; canonical path: `$PROJECT_REPO_ROOT/creative/brief.md` |
| `output_dir` | path | Output directory; defaults to `$PROJECT_REPO_ROOT/creative/structure/` |

### OUTPUT (written to `output_dir`, paths recorded in DELIVERY.md)

| File | Description |
|------|-------------|
| `world.md` | World-building / architecture / background rules document |
| `entities.md` | Character bios / module inventory / stakeholder map |
| `outline.md` | Global outline: main arc, rhythm, key turning points |
| `units/<n>-<title>.md` | Per-unit brief (each independently executable by cs-write) |

### ACCEPTANCE CRITERIA

- `outline.md` covers all dimensions required by the brief
- Each `units/<n>-<title>.md` is a self-contained execution brief containing:
  - Unit goal and position in the global arc
  - Relevant entities (characters / modules) from `entities.md`
  - Required events / points to cover
  - Minimum word count / line count / format spec
- `$PROJECT_REPO_ROOT/creative/` directory exists; `structure/` has been written
- `DELIVERY.md` lists all output file paths + units table (id, title, min_words)

## 工作流程

```
读 brief_path
  → 产出 world.md（世界观/架构）
  → 产出 entities.md（人物/模块）
  → 产出 outline.md（全局大纲）
  → 拆分为 units/N-title.md（每单元独立执行简报）
  → 写 DELIVERY.md（列全部路径 + units 表格）
```

## PATH CONVENTIONS

Canonical shared directory under the project repo:

```
$PROJECT_REPO_ROOT/
  creative/
    brief.md                     # 项目简报（cs-structure 的输入）
    structure/
      world.md                   # 世界观/架构文档
      entities.md                # 人物小传/模块清单
      outline.md                 # 全局大纲
      units/
        01-<title>.md            # 单元简报（cs-write 的输入）
    content/
      01-<title>.md              # cs-write 产出内容
      01-<title>.meta.json       # 字数/完成度 metadata
    scores/
      01-<title>-score.json      # cs-score 评分
      01-<title>-report.md       # 人类可读评分报告
```

This structure ensures all seats in the same project share a consistent filesystem layout, consistent with the engineering pattern where all seats operate in the same git repo.

## 执行者说明

| Template | Executor | Use case |
|----------|----------|----------|
| `clawseat-creative` | `creative-planner` (claude oauth) | Fiction / narrative structure |
| `clawseat-engineering` | `planner` (claude oauth) | Engineering architecture docs |

Skill 本身不绑定任何特定工具；executor 自行决定执行方式。

## 禁止事项

- 不直接写长文内容（那是 cs-write 的职责）
- unit brief 只写结构要点，不写完整文本
- 不假设执行者工具；只定义接口
