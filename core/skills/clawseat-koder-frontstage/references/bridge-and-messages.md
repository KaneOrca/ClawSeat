# Koder Frontstage — Bridge Receipts, Message Formats, Patrol

飞书群里 planner → koder 的唯一机器可读控制面、用户可见消息模板、patrol 触发
条件。SKILL.md 的 Non-Negotiables 约束了边界；本文是具体模板。

## Feishu Delegation Receipt Rule

当 planner 侧的桥通过 `lark-cli --as user` 发送时，群里显示的 sender 身份
**不再有语义**。koder **不能**基于 sender 推断 "这条来自 planner"。

只有当群消息包含严格的 `OC_DELEGATION_REPORT_V1` 信封时，才把它当成
machine-actionable。按 delegation receipt 解析，**不要**当成 agent 人格发言。

### 必需字段

- `project`
- `lane`
- `task_id`
- `dispatch_nonce`
- `report_status`
- `decision_hint`
- `user_gate`
- `next_action`
- `summary`

### 解析规则

- `lane=planning` 表示回执属于 planning lane；**不等价于**"可见 sender 是
  planner"。
- 如果 `project` / `task_id` / `dispatch_nonce` 与当前 active chain 不匹配，
  **拒绝**该信封。
- 只在 state machine resolve 到安全分支时 auto-advance：
  `done + proceed + none + consume_closeout`。
- `needs_decision + ask_user` → 把回执转成一条简短的用户问题，**不要**直接派发。
- `blocked + retry` / `blocked + escalate` → 按框架决策表上浮阻塞点；**不要**
  编造隐藏的 next hop。

## Message Formats

### DM with user

- 用户可见的状态消息前缀 `[{project}]`。
- Intake: 自然语言 → 简洁任务框架。
- Status: `[{project}] {用户摘要}`
- Decision: `[{project}] 决策点：{options}`
- Blocker: `[{project}] 阻塞：{reason}`
- Switch 确认: `已切换到 {project}`

### Project channel / seat-to-seat 通知

- Dispatch: `{task_id} assigned from {source} to {target}`
- Review result: `{task_id} verdict: {VERDICT}`
- Patrol: `patrol: {brief_status}`
- Blocker: `BLOCKED_ESCALATION: {reason}`

### 结构化信封（系统需要 machine-readable metadata 时）

```toml
[message]
project = "{project_name}"
sender = "{seat_id}"
receiver = "{seat_id | user}"
task_id = "{task_id}"
disposition = "{disposition}"
action = "{requested_operation}"
body = "{natural_language_body}"
```

## Patrol Triggers

Patrol 是 **opt-in only**。

### 触发条件

- `[patrol].enabled = true`；
- 用户显式要状态 / 提醒 / 健康检查；
- frontstage 收到已知的 stale 或 blocked 链路信号；
- `BOOTSTRAP_REQUIRED` 出现在 `PLANNER_BRIEF` 中。

### Patrol 行为

- 通过 adapter 加载 brief 和 dynamic roster；
- 如果 brief disposition 要求，通过 adapter 加载未解决的 pending-frontstage
  items；
- 评估 `frontstage_disposition`；
- `BOOTSTRAP_REQUIRED` → 把注意力路由回 `koder`，带 `requested_operation`；
- `AUTO_CONTINUE` → 不产生用户可见噪音。
