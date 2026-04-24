---
name: cs-classify
description: Creative task routing skill — accepts a user brief and classifies it as long-form or short-form, producing a routing decision (classification.json) that determines which cs-* skills to invoke.
---

# CS-Classify — Creative Task Router

**Design principle**: Entry point for the creative pipeline. Reads the user brief once, decides the optimal execution path, and outputs a structured routing decision.

## CONTRACT

### INPUT (passed via TODO objective)

| Field | Type | Description |
|-------|------|-------------|
| `brief` | string / path | User's creative request (natural language or structured) |

### OUTPUT

`classification.json`:

```json
{
  "type": "long-form" | "short-form",
  "reasoning": "1-2 sentence justification for the classification",
  "estimated_words": 5000,
  "estimated_units": 5,
  "recommended_flow": "cs-structure→cs-write→cs-score" | "cs-classify-short→cs-write→cs-score",
  "short_form_direct": true | false
}
```

| Field | Description |
|-------|-------------|
| `type` | Route decision: long-form activates full cs-structure pipeline; short-form uses lightweight path |
| `reasoning` | Brief explanation for the classification |
| `estimated_words` | Estimated total word count for the deliverable |
| `estimated_units` | Number of chapters/episodes (long-form only; omit for short-form) |
| `recommended_flow` | The exact skill chain to execute after classification |
| `short_form_direct` | If true: skip cs-classify-short, pass inline brief directly to cs-write |

## 判断规则

### 长文触发条件（满足任一即为 long-form）

- 预计超过 **3000 字**
- 需要多个章节/集数（>1 unit）
- 明确包含人物设定/世界观需求（小说/剧本/系列）
- 用户使用关键词：「连载」「系列」「全本」「剧本」「小说」「分集」「多章」

### 短文触发条件（满足任一即为 short-form）

- 预计 3000 字以内，单次可完成
- 推文/朋友圈/公众号单篇/短评/文案/slogan
- 无人物设定/世界观需求
- 用户使用关键词：「推文」「一篇」「单篇」「短文」「标题」「文案」「摘要」

### short_form_direct 判断

| 情景 | `short_form_direct` | 路径 |
|------|-------------------|------|
| 需求明确，无需确认角度 | `true` | brief → cs-write 直接 |
| 有多种角度/风格选项需确认 | `false` | brief → cs-classify-short → cs-write |

## 工作流程

```
读 brief（理解创作需求）
  → 按判断规则分类为 long-form / short-form
  → 估算总字数和单元数
  → 决定 recommended_flow
  → 若 short-form：判断是否需要角度确认（short_form_direct）
  → 写 classification.json
  → 写 DELIVERY.md（记录分类结论和路由建议）
```

## 执行者说明

| Template | Executor | Use case |
|----------|----------|----------|
| `clawseat-creative` | `creative-planner` (claude oauth) | 创作项目入口分类 |

## 禁止事项

- 不直接产出内容（只做路由决策）
- 不猜测用户意图，模棱两可时选 long-form（保守）
- 不在 classification.json 以外产出其他文件
