---
name: cs-structure
description: Capability skill for structural planning — world-building, architecture documents, global outlines, and per-unit briefs. Interface contract only; tool-agnostic.
---

# CS-Structure — Structural Planning Capability

**Design principle**: Skill = WHAT (interface contract), not HOW (tool or executor).
The executor (ancestor, engineering planner, etc.) adapts this contract to its runtime.

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
  → [GATE] 推飞书摘要，等待用户确认
```

## EXECUTION MODEL: Hollywood Writers Room (Agent Teams)

cs-structure 通过 Claude Code Agent Teams 模式执行，模拟好莱坞编剧室协作：

**Team composition（建议 4–5 人）**

```
Lead: ancestor
  - 协调整个编剧室，解决世界观/人物设计冲突
  - 合并各 teammate 产出，写入 creative/structure/

Teammate: 世界观架构师
  - 时代背景、世界规则、地理格局、势力分布
  - 与人物设计师协商规则对人物的影响

Teammate: 人物设计师 A
  - 主角及核心配角的完整小传
  - 响应叙事设计师的弧线需求，调整人物设定

Teammate: 人物设计师 B
  - 反派及次要角色的完整小传
  - 与人物设计师 A 协调角色间关系和张力

Teammate: 叙事设计师
  - 全局故事弧线、主题、分集节奏设计
  - 向人物设计师提出弧线需求
  - 产出 outline.md + units/ 骨架
```

**跨 teammate 协调机制**：Teammate 通过 Agent Teams inter-agent messaging 互发消息，世界观规则和人物设定在同一 session 内协商，避免矛盾；Lead 在最终合并前做一致性审查。

**启动要求**：ancestor 的运行环境需设置 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`。

## GATE 1: 世界观 + 人物确认

编剧室的世界观架构师和人物设计师完成初稿后**暂停**：

1. 产出 `creative/structure/world.md` + `entities.md`（草稿标记为 draft_v1）
2. 推飞书摘要（`user_gate=required`）：
   - world.md 前 500 字
   - entities.md 主要人物列表

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" \
  --project <project> \
  --report-status in_progress \
  --decision-hint ask_user \
  --user-gate required \
  --human-summary "世界观+人物初稿完成（Gate 1）。请确认世界观规则和人物设定后继续大纲创作。"
```

3. 用户确认后，叙事设计师继续完成 `outline.md` + `units/`

## GATE 2: 分集大纲确认

叙事设计师完成分集大纲后**暂停**，不自动进入 cs-write：

1. 产出 `creative/structure/outline.md` + `units/*.md`
2. 推飞书摘要（`user_gate=required`）：
   - outline.md 大纲骨架
   - units/ 分集列表（集号/标题/主要冲突）

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" \
  --project <project> \
  --report-status done \
  --decision-hint ask_user \
  --user-gate required \
  --human-summary "分集大纲完成（Gate 2）。大纲: <outline_summary>。分集: <units_list>。请确认后继续执行 cs-write。"
```

3. 用户确认后，ancestor 开始 dispatch cs-write

> **参考依据**：Hollywood Series Bible → Season Arc 两阶段确认；Netflix 全季预写模式

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
| `clawseat-creative` | `ancestor` (claude oauth) | Fiction / narrative structure |
| `clawseat-engineering` | `planner` (claude oauth) | Engineering architecture docs |

Skill 本身不绑定任何特定工具；executor 自行决定执行方式。

## 禁止事项

- 不直接写长文内容（那是 cs-write 的职责）
- unit brief 只写结构要点，不写完整文本
- 不假设执行者工具；只定义接口
