# TODO — SKILLSWEEP-032 (旧飞书范式污染全量审计)

```
task_id: SKILLSWEEP-032
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P1
subagent-mode: REQUIRED — 4 parallel subagents (A/B/C/D)
do-not-modify: read-only
```

## Context

clawseat-ancestor/SKILL.md 被 v0.4 "headless 飞书守护" 旧范式污染（§5 通讯表禁
CLI 直接交互、§2 B5 "不 prompt"、§4 克隆项目走 `override_feishu_group_id`、
§2 B6 必经飞书 smoke）。v0.6 clean-slate 没清到 skill 层。

v0.7 新范式：
- operator ↔ ancestor = **CLI 直接交互**（主）
- 飞书 = **异步通知可选**（辅）
- 5 engineer seat provider 澄清 = **CLI 逐个 prompt**，不是飞书 delegate report
- 新项目用 `agent_admin project bootstrap / use`，不再走飞书 group override

本次 audit 扫描其他 3 个关键 skill 文件 + shared harness，
报告**每一处**与 v0.7 新范式冲突的条款。

---

## Subagent A — `core/skills/clawseat-install/SKILL.md`

读整个文件，找：

1. **禁 CLI 直接交互的条款**（N1 / no-prompt 规则）
2. **必须走飞书的步骤**（delegate report / OC_DELEGATION_REPORT_V1 作为唯一通道）
3. **基于飞书 group 的项目管理**（chat_id 作为项目唯一标识）
4. **fan-out seat 启动**（不给用户逐个澄清的机会）
5. **headless / dry-run / daemon 相关默认值**（应改为 interactive-first）

每处给：行号 + 原文摘录 + v0.7 应改成什么。

---

## Subagent B — `core/skills/clawseat-koder-frontstage/SKILL.md`

同上，找所有与 v0.7 CLI-first 冲突的条款。

另外重点看：
- koder 如何把 operator 消息转发给 ancestor/planner（老范式是飞书间接通道）
- install 阶段 koder 的角色是什么？v0.7 还需要 koder 作为 operator→ancestor 中转吗？
  （v0.7 operator 直接在 tmux pane 里跟 ancestor 对话，koder 可能多余了）

---

## Subagent C — `core/skills/memory-oracle/SKILL.md` + `core/skills/gstack-harness/SKILL.md`

扫两个文件，找：

1. **memory-oracle**：
   - 老 `UserPromptSubmit hook` 引用（hook 已证实是 dead pipe，AUDIT-027 结论）
   - 老 `[CLEAR-REQUESTED]` watcher 依赖（watcher 未实现）
   - 飞书告警作为唯一失败通道
2. **gstack-harness**：
   - 有无"operator 只能通过飞书"假设
   - 有无依赖 OC_DELEGATION_REPORT_V1 作为 seat 间通讯唯一格式

---

## Subagent D — `docs/` 下的旧流程文档

```bash
cd /Users/ywf/ClawSeat
grep -rln "OC_DELEGATION_REPORT\|override_feishu_group\|N1.*prompt\|feishu_group_id.*required\|headless.*default" docs/ 2>/dev/null | head -20
```

对每个命中文件：摘要问题 + 建议（删 / 重写 / 标 deprecated）。

重点看：
- `docs/INSTALL.md`（已知与 v0.7 冲突，但还没改）
- `docs/ARCHITECTURE.md`
- `docs/design/` 下所有 .md
- `docs/review/` 下所有 .md

---

## Deliverable

写 `DELIVERY-SKILLSWEEP-032.md`：

```
task_id: SKILLSWEEP-032
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话：共 <N> 个文件、<M> 处冲突>

## Subagent A — clawseat-install/SKILL.md
<冲突表：行号 + 原文 + v0.7 应改法>

## Subagent B — clawseat-koder-frontstage/SKILL.md
<同上 + koder 角色建议：保留/删/降级>

## Subagent C — memory-oracle + gstack-harness
<dead pipe 引用清单 + 老范式残留>

## Subagent D — docs/ 旧流程文件
<文件 → 操作建议表（删/改/保留）>

## 总结
- 总冲突数
- 影响 v0.7 交付的必须改项（P0）
- 可留到 v0.8 的次要改项（P1）
- 建议每一批谁来改（planner 自己 / codex / 混合）
```

完成后通知 planner: "DELIVERY-SKILLSWEEP-032 ready"。
