# Koder Frontstage — Operations

Adapter 调用模式、pending queue 处理规则、项目切换协议、窗口维护命令。
SKILL.md 约束 koder **能做什么 / 不能做什么**；本文告诉你 **怎么做**。

## Action Schema Consumption

通过 adapter 调用消费 action schema：

- `instantiate` → `adapter.instantiate_seat(project_name=..., template_id=..., instance_id=...)`
- `restart` → `adapter.check_session(...)`，然后在 skill 外跑项目的 runtime
  restart 路径；没有就显式通知 operator
- `redispatch` → `adapter.dispatch_task(...)` 或 `adapter.notify_seat(...)`，取决于
  是否需要 durable 任务 handoff
- `switch_provider` → 带上请求的 provider 和 reason 上浮给 operator / user；
  不要在 skill 层现编 runtime mutation
- `none` → 不做 adapter action

Guardrails：

- 每次 adapter 调用必须带 `project_name`。
- 不要从 frontstage 直接派给 specialist；除非协议明确说明，**下一跳总是 planner**。
- restart / redispatch / unblock 期间，如果链路还活着，必须保留 `task_id`。

## Pending Frontstage Queue

通过 adapter 读写 pending queue，**不要**在 prompt 层手改 markdown。

必需的 adapter 调用：

- `read_pending_frontstage(project_name=...)`
- `resolve_frontstage_item(project_name=..., item_id=..., resolution=..., resolved_by=...)`

### Resolution 规则

- `user_input_needed = false` 且 `type = decision`：koder 可以直接 adopt
  `planner_recommendation` 或 `koder_default_action`。
- `user_input_needed = false` 且 `type = clarification`：koder 可以基于项目知识
  和当前上下文作答。
- `user_input_needed = true` 且 `blocking = true`：koder 必须上浮给用户并等。
- `user_input_needed = true` 且 `blocking = false`：异步通知用户，同时让链路按
  `koder_default_action` 继续。
- koder 覆盖 planner 建议时，原因必须写进 `resolution`。

**不要自决的类别**：

- 范围变更
- 资源投入决策（比如再拉一个 specialist）
- 架构方向变更

**planner 已经收窄选项的可以自决**：

- 执行策略顺序
- planner 批准范围内的技术选项选择
- 来自已有文档的项目上下文澄清

### 归档规则

- koder 只处理 `resolved: false` 的条目。
- 一旦解决，写入 `resolved: true` / `resolved_by` / `resolved_at` / `resolution`。
- 把条目从 `## 待处理事项` 移到 `## 已归档`；**不要**删除。
- planner 后续消费归档决议，清空 frontstage backlog。

## Project Switching

维持一个显式的 `current_project`。

### Switch Protocol

1. 确认或解析目标项目名；
2. 离开当前项目前，通过 adapter drain 或 quiesce 其 inbox；
3. `frontstage_epoch++`；
4. 设置 `current_project`；
5. 通过 adapter 重新加载 profile、roster、planner binding、brief；
6. 刷新项目本地知识文件，如 `AGENTS.md`；
7. 用 project tag 格式向用户回报新项目状态。

### 规则

- **绝不**在没有显式 `project_name` 的情况下 dispatch / notify / instantiate /
  complete handoff。
- 只消费 `current_project` 的 inbox。另一项目 active 时，不处理它的 queued
  operations。
- **不要**跨项目复用 brief state。
- 目标项目 profile 不存在 → 直说并停。

## Window Maintenance (iTerm / TUI)

`agent-admin window open-monitor <project>` 是 koder 的**唯一标准修复动作**：

- seat 起 / 停 / 漂离 canonical tab 顺序时使用；
- **不要**为 `tabs-1up` 项目手动开单 seat 窗口；
- **不要**把 `tmux attach` 作为常规恢复路径；
- 该命令按 canonical seat 顺序重建**一个**项目窗口 + 每 seat 一 tab；
- 已经开了多个重复项目窗口时，helper 会关闭陈旧副本并恢复 canonical 布局。

实战规则：**一项目、一 iTerm 窗口、tabs 按 canonical seat 顺序**。koder 负责
保持这个布局整洁；specialist 不许自由发挥。
