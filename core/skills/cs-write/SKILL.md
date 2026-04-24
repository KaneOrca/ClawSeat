---
name: cs-write
description: Capability skill for content execution — long-form writing, code implementation, or copy. Receives a unit brief from cs-structure and produces the actual content artifact. Interface contract only; tool-agnostic.
---

# CS-Write — Content Execution Capability

**Design principle**: Skill = WHAT (interface contract), not HOW (tool or executor).
The same interface covers fiction writing (Gemini), code implementation (Codex), and other content forms.

## CONTRACT

### INPUT (passed via TODO objective)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `unit_brief_path` | path | ✓ | Unit brief file (from cs-structure's `units/`) |
| `context_dir` | path | optional | Context directory containing `world.md` + `entities.md` |
| `min_words` | int | optional | Minimum word/line count (read from unit brief if not specified) |
| `format` | enum | optional | Output format: `prose` / `fountain` / `markdown` / `code` (default: `prose`) |

### OUTPUT

| File | Description |
|------|-------------|
| `content.md` (or `.fountain` / `.py` / etc.) | The actual produced content; format determined by `format` parameter |
| `meta.json` | `{word_count, sections_completed[], format, completed_at}` |

Output path: same directory as `unit_brief_path` unless `objective` specifies otherwise.

### ACCEPTANCE CRITERIA

- `content` covers all points required by `unit_brief`
- `meta.json.word_count >= min_words` (if specified)
- Format matches `format` parameter
- `DELIVERY.md` records content path + `meta.json` summary (word_count, grade)

## 工作流程

```
读 unit_brief_path（确认所有结构要素齐全）
  若 context_dir 存在 → 读 world.md + entities.md（确保一致性）
  执行内容创作（长文/代码/文案）
  写 content.<ext>
  写 meta.json
  写 DELIVERY.md（记录路径 + meta 摘要）
```

## 执行者说明

| Template | Executor | Output form |
|----------|----------|-------------|
| `clawseat-creative` | `creative-designer` (gemini oauth) | Long-form narrative / script |
| `clawseat-engineering` | `builder` (codex oauth) | Code / configuration / docs |

Skill 不绑定任何特定工具；executor 自行决定生成方式。

## 禁止事项

- 不自行修改 unit brief 或 outline（如发现结构问题，escalate 给 planner）
- 不引入 unit brief 未提及的新人物/模块（需 planner 决策）
- meta.json 必须如实记录 word_count，不能伪造
- 不写超出 unit 范围的内容（范围由 unit brief 定义）
