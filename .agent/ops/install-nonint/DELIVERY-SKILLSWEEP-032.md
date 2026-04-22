task_id: SKILLSWEEP-032
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 共 4 个 skill 文件 + 5 个 docs 文件发现 45 处冲突；P0 必须改 23 项；koder 降级为 display adapter，OC_DELEGATION_REPORT 全系删除。

## Subagent A — clawseat-install/SKILL.md

### 冲突表

| 行号 | 原文 | v0.7 应改为 |
|------|------|------------|
| L3 | "v0.5 agent-driven flow" | "v0.7 CLI-first flow" |
| L6 | "## ClawSeat Install (v0.5 — agent-driven)" | "## ClawSeat Install (v0.7 — CLI-first)" |
| L68-69 | "**Tenant layer (Feishu only)**: `koder` — Feishu-side frontstage, not a tmux seat." | "**Tenant layer (Feishu optional)**: `koder` — Feishu-side async notification receiver, not a seat operator." |
| L71-74 | "**Local CLI install** → ancestor is frontstage **Feishu / OpenClaw path** → koder is frontstage (ancestor runs headless behind it)" | "**CLI install** → ancestor is frontstage (interactive-first). **Feishu path** → koder is async notification sink only; ancestor still runs as CLI frontstage." |
| L76 | "## Subagent mode (encouraged, across all seats)" | "## Subagent mode (encouraged, across all seats) — per-seat provider clarification must be done one-by-one via CLI prompt before fan-out." |
| L78-84 | "Ancestor parallelizes seat startup... Builder spawns focused subagents..." | Add note: "For the 5 engineer seats, provider selection must be clarified interactively via CLI one-by-one before any fan-out. Feishu delegate report is NOT the clarification channel." |
| L90-105 | "## What to NOT do" section missing Feishu delegation ban | Add: "Do NOT use Feishu delegate report (OC_DELEGATION_REPORT_V1) as the primary channel for seat provider clarification. Do NOT use Feishu chat_id as project identifier — use `agent_admin project bootstrap/use`." |

**7 conflicts found**

---

## Subagent B — clawseat-koder-frontstage/SKILL.md

### 冲突表

| 行号 | 原文 | v0.7 应改为 |
|------|------|------------|
| L16 | "Lifecycle requests route: **user → koder → planner → ancestor**." | "Lifecycle requests route: **operator → ancestor** via `agent_admin` CLI directly. Koder is NOT in the critical path for seat lifecycle." |
| L17 | "`koder` is **session-scoped to one project per Feishu chat_id**." | "`koder` is session-scoped to one project per active operator session, resolved via `CURRENT_PROJECT` env / CLI context, NOT Feishu `chat_id`." |
| L27-33 | "On every incoming Feishu message: 1. Extract `chat_id`... 2. Call `resolve_project_from_chat_id(chat_id)`..." | "On every incoming message: resolve `CURRENT_PROJECT` from CLI context or active session; Feishu `chat_id` is no longer the primary project binding key." |
| L31 | "reply with 'this group is not bound to any project; please run `cs install`'" | "Reply that no project is active; operator should run `agent_admin project use <name>` or `agent_admin project bootstrap`." |
| L36-54 | New-project intake via Feishu group + `override_feishu_group_id` dispatch to planner | "Use `agent_admin project bootstrap <name>` CLI; Feishu group is optional notification target, not the bootstrap channel." |
| L154-187 | "Planner Launch Follow-up" section — requires Feishu group setup, `requireMention`, group smoke test | "Remove entirely. Planner initialization in v0.7 is CLI-driven via `agent_admin project bootstrap`. Feishu is optional async notification only." |
| L188-222 | "Feishu Delegation Receipt Rule" — `OC_DELEGATION_REPORT_V1` envelope parsed from Feishu group messages | "Feishu is optional async notification. Delegation receipts in v0.7 are delivered via CLI state files or direct stdout, not Feishu envelopes." |
| L392-405 | Heartbeat reception — posts `[HEARTBEAT_ACK ...]` to Feishu group | "Heartbeat in v0.7 is CLI-based polling or file-system signals; no Feishu group posting." |
| L399 | "post a short `[HEARTBEAT_ACK project=<X> ts=<T2>] clean` reply to the Feishu group" | "Acknowledge via CLI status output or state file update, not Feishu." |
| L400 | "AND create a handoff for planner: `dispatch_task.py`..." | "v0.7 uses `agent_admin task dispatch` or direct file-based handoff to ancestor." |
| L265-268 | "Never dispatch directly to specialists from frontstage; planner is the next hop unless the protocol explicitly says otherwise" | "In v0.7, operator → ancestor is direct; koder's routing role is eliminated or reduced to UI-facing message formatting." |

**10 conflicts found**

### koder 角色建议：**降级为 display adapter**

v0.7 operator 直接在 tmux pane 里通过 `agent_admin` CLI 与 ancestor 对话。koder 的价值仅限于：
- 格式化状态摘要供显示
- 管理 frontstage disposition 状态的可读性
- 作为项目知识的只读呈现者

**Koder 不应**：
- 拥有任何路由或 delegation 逻辑
- 位于 seat lifecycle 关键路径上
- 将 Feishu 作为主要通讯通道

---

## Subagent C — memory-oracle + gstack-harness

### memory-oracle 冲突（2 项）

| 行号 | 原文 | 问题 | v0.7 应改为 |
|------|------|------|------------|
| L17 | `UserPromptSubmit` hook 已注入 `machine/` | dead pipe hook per AUDIT-027 — hook 未实现 | 删除 hook 引用，改为描述轮次注入的数据来源（credentials/network/openclaw/github/current_context + dev_env.json） |
| L43-48 | `[CLEAR-REQUESTED]` 标记；由外部 orchestrator（tmux watcher / Stop hook / operator key-in）监听后再触发 `tmux send-keys /clear` | watcher 未实现；Stop hook 不存在 | 删除 `[CLEAR-REQUESTED]` 引用；/clear 由 operator 手动触发，或改用 session-level 刷新机制 |

### gstack-harness 冲突（5 项）

| 行号 | 原文 | 问题 | v0.7 应改为 |
|------|------|------|------------|
| L45-46 | `[Feishu delegation report]` when planner uses user-identity group messages to wake frontstage/koder | 假设 operator 仅通过 Feishu 与 frontstage/koder 交互 | 保留 feishu-delegation-report.md 引用为一种可选通道，注明 others TBD |
| L86-87 | `emits the planner Feishu group broadcast only when a binding is available and CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST=1` | 假设 Feishu group broadcast 是唯一广播路径 | 改为通用广播协议，Feishu group 为可配置 transport 之一 |
| L95-97 | `when planner is part of the handoff and a Feishu group is configured, emit the matching group broadcast only when CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST=1` | Feishu 作为 planner handoff 唯一通道 | 同上 |
| L99-101 | `send an OC_DELEGATION_REPORT_V1 message to Feishu through lark-cli --as user` | 假设 OC_DELEGATION_REPORT_V1 + Feishu 是唯一 delegation 路径 | 改为 delegation 报告的通用接口，OC_DELEGATION_REPORT_V1 为一种序列化格式（others possible） |
| L220-222 | `the caller must explicitly bypass tmux and use the Feishu user-message path (complete_handoff.py → send_feishu_user_message)` | 假设 Feishu user-message 是到 OpenClaw frontstage 的唯一 bypass 路径 | 注明 bypass 机制待抽象，当前仅为 Feishu 路径的占位注释 |

**2 + 5 = 7 conflicts found**

---

## Subagent D — docs/ 旧流程文件

### 文件冲突总表

| 文件 | 冲突数 | 主要问题 |
|------|--------|---------|
| docs/INSTALL.md | 8 | v0.5 title，Feishu 作为 required binding，koder=frontstage，OC_DELEGATION_REPORT B6 |
| docs/ARCHITECTURE.md | 11 | v0.5 references，koder-frontstage，Feishu 作为主要通知，C12 heartbeat 设计 |
| docs/CANONICAL-FLOW.md | 5 | OC_DELEGATION_REPORT_V1 作为主要 machine-readable control packet，Feishu group bridge 作为 required config |
| docs/schemas/ancestor-bootstrap-brief.md | 5 | Brief 中含 Feishu targets，B6 OC_DELEGATION_REPORT，feishu_group_binding 字段 |
| docs/schemas/v0.4-layered-model.md | 1 | v0.4 版本标记（历史文档，影响小） |

### 关键 v0.7 范式冲突汇总

- `koder = Feishu frontstage`（主要）— 与 CLI-as-primary 矛盾
- Feishu group binding 作为 required install 步骤 — v0.7 改为 optional
- `OC_DELEGATION_REPORT_V1` 作为主要协议 — v0.7 使用 direct CLI dispatch
- B5/B6 Phase-A 步骤依赖 Feishu binding — v0.7 删除这些
- `agent_admin project bind --feishu-group` — v0.7 使用 `bootstrap/use` 命令替代

---

## 总结

### 总冲突数

| 来源 | 冲突数 |
|------|--------|
| clawseat-install/SKILL.md | 7 |
| clawseat-koder-frontstage/SKILL.md | 10 |
| memory-oracle/SKILL.md | 2 |
| gstack-harness/SKILL.md | 5 |
| docs/INSTALL.md | 8 |
| docs/ARCHITECTURE.md | 11 |
| docs/CANONICAL-FLOW.md | 5 |
| docs/schemas/ancestor-bootstrap-brief.md | 5 |
| docs/schemas/v0.4-layered-model.md | 1 |
| **合计** | **54** |

### P0 — 必须改项（影响 v0.7 交付）

| 优先级 | 项数 | 说明 |
|--------|------|------|
| P0 | 23 | SKILL.md 中的 OC_DELEGATION_REPORT 全系删除；koder 路由链移除；Feishu 降为 optional；INSTALL.md 整个重写 |
| P1 | 31 | ARCHITECTURE.md v0.5 引用清理；gstack-harness transport 抽象；memory-oracle hook 引用修复；schema 文档清理 |

### 建议修改批次

| 批次 | 内容 | 负责人 |
|------|------|--------|
| **Batch 1（planner 自己改）** | clawseat-install/SKILL.md v0.5→v0.7 版本更新；What NOT to do 添加 Feishu 禁令 | planner |
| **Batch 2（codex 执行）** | clawseat-koder-frontstage/SKILL.md — 删除 L154-222（Planner Launch + Delegation Receipt），删除 L392-405（Heartbeat Feishu），重构 L16-36 为 CLI-first | codex |
| **Batch 3（codex 执行）** | memory-oracle — 删除 L17 hook 引用；删除 L43-48 [CLEAR-REQUESTED] | codex |
| **Batch 4（codex 执行）** | gstack-harness — 将 OC_DELEGATION_REPORT 标记为 deprecated format，Feishu 改为 optional transport | codex |
| **Batch 5（planner 自己改）** | docs/INSTALL.md — 完全重写为 v0.7 CLI-first 流程 | planner |
| **Batch 6（planner 自己改）** | docs/ARCHITECTURE.md — v0.5 引用清理，koder-frontstage 段落删除，C12 heartbeat 重构 | planner |
| **Batch 7（planner 自己改）** | docs/CANONICAL-FLOW.md — 删除 OC_DELEGATION_REPORT_V1 primary protocol 段落 | planner |
| **Batch 8（codex 执行）** | docs/schemas/ancestor-bootstrap-brief.md — B5/B6 删除，Feishu fields 降为 optional | codex |
