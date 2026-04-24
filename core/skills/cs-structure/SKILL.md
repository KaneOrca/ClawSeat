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
| `brief_path` | path | Project brief file (goal / audience / genre / constraints) |
| `output_dir` | path | Output directory path (relative to seat workspace) |

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
