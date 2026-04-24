---
name: cs-score
description: Capability skill for rubric-based acceptance scoring with optional Feishu publication. Evaluates a deliverable against the original brief and a rubric. Interface contract only; tool-agnostic.
---

# CS-Score — Acceptance Scoring Capability

**Design principle**: Skill = WHAT (interface contract), not HOW (tool or executor).
The scorer reads deliverables and produces structured scoring artifacts; it does not modify content.

## CONTRACT

### INPUT (passed via TODO objective)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deliverable_path` | path | ✓ | Path to content.md / DELIVERY.md / git commit SHA |
| `brief_path` | path | ✓ | Original project brief (for alignment assessment) |
| `rubric_path` | path | optional | Custom rubric TOML/MD; defaults to built-in rubric below |
| `feishu_publish` | bool | optional | Publish score summary to Feishu (default: false) |

### OUTPUT

| File | Description |
|------|-------------|
| `score.json` | `{dimensions:[{name,weight,score,evidence}], total, grade, timestamp}` |
| `report.md` | Human-readable scoring report (dimension breakdown + summary + improvement suggestions) |

### ACCEPTANCE CRITERIA

- `score.json` includes a score and textual evidence for each rubric dimension
- `total = weighted_sum(dimension scores)`, clamped to [0, 100]
- Grade: A≥90 / B≥80 / C≥70 / D<70
- If `feishu_publish=true`: call `send_delegation_report.py` or `lark-cli` to push `report.md` summary
  - If `CLAWSEAT_FEISHU_ENABLED=0`: skip publish without failing the scoring task
- `DELIVERY.md` records `score.json` path + grade

## 默认 Rubric（可被 rubric_path 覆盖）

| Dimension | Weight | Assessment focus |
|-----------|--------|-----------------|
| 目标对齐度 | 30% | Does content address brief's goal and audience? |
| 内容质量 | 25% | Logic, language clarity, internal consistency |
| 完整性 | 20% | Covers all required points from brief |
| 格式规范 | 15% | Matches specified format requirements |
| 原创性 | 10% | Novel expression, fresh perspective |

## 工作流程

```
读 deliverable_path（理解交付内容）
读 brief_path（了解原始目标和约束）
读 rubric_path 或使用默认 rubric
逐维度评分（每维度附文字依据，引用原文片段）
计算 total = Σ(weight * score)，确定 grade
写 score.json
写 report.md（维度明细 + 综合评价 + 改进建议）
若 feishu_publish=true → 推送摘要
写 DELIVERY.md（记录路径 + grade）
```

## 执行者说明

| Template | Executor | Typical use |
|----------|----------|-------------|
| `clawseat-creative` | `creative-qa` (claude minimax api) | Creative content scoring |
| `clawseat-engineering` | `qa` (claude minimax api) | Engineering deliverable validation |

Skill 不绑定特定工具；executor 自行执行评分逻辑。

## 禁止事项

- 不修改被评审的内容（发现问题只记录在 report.md）
- 每条评分必须引用具体原文证据（不允许无依据评分）
- 不把 `feishu_publish=true` 失败当作评分失败（两者独立）
- 不伪造评分结果
