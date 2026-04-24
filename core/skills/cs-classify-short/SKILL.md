---
name: cs-classify-short
description: Lightweight short-form structure skill. Receives a short-form brief, produces a concise angle.md (≤200 words) covering angle options, core thesis, target audience, and tone. Atomic tool; next step decided by caller.
---

# CS-Classify-Short — Lightweight Short-Form Structure

**Design principle**: Atomic tool. Produces only `angle.md` (200 words max). Unlike cs-structure (which produces full world-building docs), this skill is optimized for short-form content where a brief angle brief suffices. What happens after `angle.md` is produced is decided by the caller (creative-planner), not by this skill.

## CONTRACT

### INPUT (passed via TODO objective)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `brief` | string / path | ✓ | User's short-form creative request |
| `quick_mode` | bool | optional | If true: skip user confirmation gate, produce single best angle and proceed directly (default: false) |

### OUTPUT

`angle.md` (≤200 words):

```markdown
## 核心角度
[Option A: <angle title> — <one sentence description>]
[Option B: ...] (if multiple angles apply)
[Recommended: Option A] (or: Single best angle — <name>)

## 核心论点/主旨
<1-2 sentences summarizing the central argument or hook>

## 目标受众
<brief audience description>

## 风格基调
<tone: professional / conversational / humorous / urgent / etc.>
```

### ACCEPTANCE CRITERIA

- `angle.md` ≤ 200 words
- Contains exactly one "推荐" (recommended) angle or a single clear angle
- Includes core thesis, audience, and tone
- `DELIVERY.md` records `angle.md` path and whether gate was triggered

## GATE（角度确认）

```
if quick_mode=false:
    → 推飞书摘要（user_gate=required）等待用户确认角度选择
    → 用户回复后，planner 将确认的角度用于下一步（具体如何使用由 planner 决定）
if quick_mode=true:
    → 直接使用 Recommended 角度，无需确认
    → 将 angle.md 返回给 planner，由 planner 决定后续步骤
```

若 `CLAWSEAT_FEISHU_ENABLED=0`：自动切换为 `quick_mode=true`（无法推飞书，无法等待确认）。

## 工作流程

```
读 brief（理解短文创作需求）
  → 产出 1-3 个角度选项（或单一最佳角度）
  → 确定核心论点、受众、风格
  → 写 angle.md（≤200字）
  → [GATE] 若 quick_mode=false → 推飞书等待角度确认
  → 写 DELIVERY.md
```

## 执行者说明

| Template | Executor | Use case |
|----------|----------|----------|
| `clawseat-creative` | `creative-planner` (claude oauth) | 短文角度确认 |

## 禁止事项

- 不写超过 200 字的 angle.md
- 不在 angle.md 里写正文内容（那是 cs-write 的职责）
- 不在 quick_mode=false 时跳过门控
