# Koder Frontstage — Disposition Playbook

完整的 `frontstage_disposition` 处理矩阵。SKILL.md 里的表格是一眼扫的索引；
遇到具体 disposition 时回到这里看细则。还收录了 planner 启动后的一次性后续
流程（只有首启 / 项目绑定一次），以及 stage closeout 的复合流程。

## Disposition Matrix

### `AUTO_CONTINUE`

- 不要仅仅因为链路健康就打扰用户。
- 巡检时在内部 log / summarize，不产生用户可见输出。

### `AUTO_ADVANCE`

- 读 planner delivery 或 brief summary。
- 用大白话向用户汇报结果。
- 如果 planner 已经给出下一步，把它直接派回链路，**不要**在 frontstage 停住。

### `USER_DECISION_NEEDED`

- 读 `PENDING_FRONTSTAGE.md`。
- 按条处理未解决事项。
- 判断 koder 能自己解还是必须上浮给用户（参见 `operations.md` 的 Pending Queue
  Resolution 规则）。
- 每条解决结果在 planner 消费之前必须落成 durable fact。

### `BLOCKED_ESCALATION`

- 用最短可操作说明把阻塞点告诉用户。
- 如果阻塞是 seat / runtime 健康问题、且 koder 被允许自愈，先尝试自愈，然后通知
  planner。
- 否则请求用户或系统补上缺失动作，保留 `task_id`。

### `CHAIN_COMPLETE`

- 给用户总结最终结果。
- 把 frontstage 对话标记为完成 / 归档。
- 巡检不应对已完成链路继续唠叨。

### `BOOTSTRAP_REQUIRED`

- 以 session binding + tmux state 为权威，不信陈旧文案。
- 通过 adapter resolve planner。
- planner 不存在 → 实例化。
- planner binding 存在但 tmux 挂了 → 重启 or 通知 operator。
- planner 存在且运行但陈旧 → 发提醒 or unblock notice。

## Planner Launch Follow-up（首次启动 / 项目绑定一次性）

当 `planner` 刚初始化且项目用 OpenClaw + Feishu：

- 主动请求用户让主 agent 创建或拉出目标 Feishu 群并报 `group ID`。不问 `open_id`——
  `group ID` 就够。
- 主 agent 保持 `requireMention = true`。
- 项目面向的 `koder` 账号在该群默认 `requireMention = false`；只有明确部署的
  可选系统 seat（如 `warden`）才在该群里额外加。
- 验证已有 group id：扫 `~/.openclaw/agents/*/sessions/sessions.json` 中 `group:`
  前缀的 key。
- 在 `~/.openclaw/openclaw.json` 检查
  `messaging.feishu.accounts.<account>.groups.<group_id>` 下的 group 专属设置。
- `group ID` 到位后，**显式确认**这个群是绑当前项目、切到另一个已有项目、还是
  引导新项目——**不要**把"新群"等价于"新项目"。
- planner 把同一个绑定群作为用户可见的 `OC_DELEGATION_REPORT_V1` decision gate
  和 closeout 桥梁；legacy 自动广播默认关闭，只在显式 opt-in 时启用。
- `group ID` 和项目绑定确认后，立即委托 planner 做 bridge smoke test，告诉
  用户 `收到测试消息即可回复希望完成什么任务`，并在 `reviewer-1` 存在时并行启动。
- 当前链路以验证为主时，请求 planner 和 `reviewer-1` 并行或紧接启动 `qa-1`；
  QA 不是首启 seat。
- planner 初始化完成后，依赖 planner smoke test + `OC_DELEGATION_REPORT_V1`
  bridge 回执，**不要**发一条自由文本的 "planner 初始化完成" 广播。

如果主 agent 也在该群，它继续保持 mention-gated。**不要**把主账号弱化为
`requireMention = false`。

## Stage Closeout Review

当 planner 把 stage closeout 返回 frontstage、群里出现 wrap-up 结果，koder 必须：

- 读 linked delivery trail 和任何被引用的 specialist delivery；
- 把 stage 结果和 `TASKS.md`、`STATUS.md`、项目文档对齐；
- 在用户总结发出**之前**更新 `PROJECT.md` 和任何受影响的项目文档；
- 然后才向用户总结 closeout 或自动推进链路。
