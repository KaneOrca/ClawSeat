# ClawSeat 团队实例化与巡检协议计划

## Summary

ClawSeat 将从固定 `engineer-a/b/c...` roster 模式重构为模板驱动、项目内实例化的团队框架。

重构后的主线：

- 默认只启动 `koder`
- `koder` 先做需求澄清，再推荐团队配置
- 用户确认后按模板实例化团队成员
- `planner` 自主推进，不再向 `koder` 回执 closeout
- `planner` 维护 `.tasks/planner/PLANNER_BRIEF.md`
- `koder` 默认不巡检；只有用户开启巡检时才读取工程师状态和 `PLANNER_BRIEF.md`

## 模板目录

第一版固定模板：

- `planner`
- `builder`
- `reviewer`
- `qa`
- `designer-creative`

默认运行时倾向：

- `koder`：用户自行选择
- `planner`：Claude
- `builder`：Codex
- `reviewer`：Codex
- `qa`：Claude API / `minimax` / `MiniMax-M2.7-highspeed`
- `designer-creative`：Gemini

测试偏好补充：

- 以后凡是“跑测试 / 验证 / smoke / 回归 / 审批前复测”类型任务，默认优先走 `qa`
  lane
- `qa` lane 默认模型固定为 `MiniMax-M2.7-highspeed`
- 如果 builder / reviewer 只是顺手做了小范围自检可以保留原模型；但明确的测试任务应优先派给
  `qa`

## 实例命名规范

项目内实例使用 role-first 稳定命名：

- `koder`
- `planner`
- `builder-1`
- `reviewer-1`
- `qa-1`
- `designer-creative-1`

## 团队创建流程

1. 创建项目时只生成 `koder`
2. `koder` 做需求澄清
3. `koder` 生成推荐团队配置
4. 用户确认后实例化团队成员
5. 最后统一拉起 TUI 窗口和 tabs

推荐团队配置至少包含：

- 需要实例化哪些模板
- 每个实例使用的 CLI
- oauth 还是 api
- provider / model
- 实例 id

## Planner 协议

- `planner` 是 active loop owner
- `planner` 不再要求向 `koder` 写 formal closeout receipt
- `planner` 负责维护：
  - `.tasks/planner/PLANNER_BRIEF.md`
- `STATUS.md`、`TASKS.md`、specialist 的 `TODO.md` / `DELIVERY.md` / receipts 仍是任务链事实源
- `PLANNER_BRIEF.md` 是面向 `koder` 和用户的总览文档

## Koder 巡检协议

- `koder` 默认不巡检
- 用户显式开启巡检后，`koder` 读取：
  - 各工程师状态
  - `.tasks/planner/PLANNER_BRIEF.md`
  - 必要的 `STATUS.md` / `TASKS.md`
  - `tasks_root/patrol/learnings.jsonl` 中已沉淀的经验教训
- `koder` 向用户汇报并给出建议
- 若发现停滞或阻塞，`koder` 应向 `planner` 下达推进指令
- `koder` 不直接接管 `planner` 的工作
- 资源阻塞（如 `usage limit` / `no active subscription` / `quota exceeded` /
  `429 Too Many Requests` / `exceeded retry limit`）视为 `BLOCKED`，不是普通
  `STALLED`
- 如果巡检判断后来被 durable 事实推翻（例如任务已 completed、delivery 已被
  durable ACK、pane 状态陈旧），框架应自动把该误判记录为经验教训，供后续
  巡检复用

## Provider 模板原则

provider 配置应模板化，不再依赖逐个 seat 手改 env。

对 `xcode` lane：

- Claude lane 与 Codex lane 共享 provider 概念
- 但 key / model / CLI materialization 必须分流
- Claude lane 使用 Claude 专用 key
- Codex lane 使用 GPT 专用 key

## 当前重构优先级

1. 模板 schema 设计
2. 项目内实例化引擎
3. 从静态 roster 向模板驱动迁移
4. `koder` 巡检 opt-in
5. 协议与窗口/tab 规则同步
