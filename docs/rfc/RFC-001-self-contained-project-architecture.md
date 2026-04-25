# RFC-001: Self-Contained Project Architecture (ClawSeat v2)

- **Status**: Draft
- **Author**: ancestor (cartooner-ancestor session) on behalf of operator (ywf)
- **Date**: 2026-04-25
- **Branch**: `refactor/clawseat-v2-self-contained`
- **Worktree**: `/Users/ywf/coding/.claude/worktrees/clawseat-v2/`
- **Discussion log**: cartooner-ancestor scrollback 2026-04-25 22:30~23:50（与 operator 的实时架构对齐对话）

---

## 1. Motivation

ClawSeat v1 (current) 拓扑存在三类问题：

1. **重复的 ancestor**：每个项目独立 ancestor seat，N 个项目 = N 个 ancestor 进程，协调能力却不跨项目
2. **memory 角色弱化**：全局 `machine-memory-claude` 主要做 install 时一次性 env scan，之后基本只是查询目标，养一个常驻 LLM 不划算
3. **`close t` bug 引发的整窗炸 + recover 链路依赖 sandbox 内 ancestor 主动跑（已知失效）** —— 详见 [`/tmp/clawseat-reports/cartooner-grid-rca-20260425-152000.md`](file:///tmp/clawseat-reports/cartooner-grid-rca-20260425-152000.md)
4. **OAuth engineer seat 实际 unsandboxed**（HOME=`/Users/ywf` + `--dangerously-skip-permissions`），与 sandbox 化的 ancestor 形成"工人比老板权限大"的反直觉拓扑
5. **没有自定义模板** — `install.sh` 硬编码白名单只接受 `clawseat-{default,engineering,creative}`
6. **template UX 半瘸** — `prompt_kind_first_flow()` 一旦遇到 pipe / `--reinstall` 就静默 skip，操作员看不到"工程/创作/通用"选择

---

## 2. Proposal

### 2.1 核心简化：项目自闭环

**没有 global ancestor，没有 global memory，每个项目是 4-seat 自闭环单元。**

```
项目 = install (例)
┌────────────────────────────────────────────────────────────┐
│ install-memory  (= 旧 ancestor + 旧 memory 合并)           │
│ - claude oauth · HOME=/Users/ywf · max privilege           │
│ - 职责: 项目记忆 + 决策 + 观察 + 派工 + 与用户对话         │
│ - 记忆机制: M1 文件 placeholder, M2 接成熟 memory skill    │
│ - 独立 iTerm 窗口 (项目第一入口, 用户对话面)               │
└─────┬────────────────┬────────────────┬───────────────────┘
      │ dispatch       │ dispatch       │ dispatch
      ▼                ▼                ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│ planner  │    │ designer │    │ reviewer │
│ plan +   │    │ 审美判断 │    │ 代码审查 │
│ 编码     │    │ 视觉反馈 │    │          │
│          │    │          │    │          │
│ 默认     │    │ gemini   │    │ 默认     │
│ claude   │    │ oauth    │    │ codex    │
│ 可切换   │    │          │    │ oauth/api│
│          │    │          │    │ 可切换   │
└──────────┘    └──────────┘    └──────────┘
       (3 个 worker, 同一个 iTerm 窗口的 3 panes)
```

### 2.2 关键合并/精简

| 旧（v1） | 新（v2） |
|---------|---------|
| per-project ancestor | 删除，由 `<project>-memory` 接管 |
| 全局 `machine-memory-claude` (LLM seat) | 删除，机器观察由 Tier 3 watchdog daemon 承担 |
| 单独 `builder` seat | 合并进 planner（planner 既规划又写代码） |
| 单独 `qa` seat | 删除（M1 不要，M2 看是否需要） |
| 全局 ancestor 协调跨项目 | 不存在；project memory 之间通过 dispatch 协议互发 |
| iTerm 1 窗口 6 panes | iTerm 2 窗口/项目: `<project>-memory` (1 pane) + `<project>-workers` (3 panes) |

### 2.3 4-Seat Minimal Template

文件：[`templates/clawseat-minimal.toml`](../templates/clawseat-minimal.toml)（草案见 §6）

| Seat | Tool | Auth | Provider 默认 | 可切换 | 角色 |
|------|------|------|--------------|--------|------|
| `memory` | claude | oauth | anthropic | 否 (固定) | 项目记忆 + 决策 + 派工 + 用户对话 |
| `planner` | claude | oauth | anthropic | **是** (任意 LLM 模型) | 规划 + 编码 |
| `designer` | gemini | oauth | google | 是 | 审美判断 |
| `reviewer` | codex | oauth | openai | **是** (oauth ⇄ api 可切，api 默认 xcode-best) | 代码审查 |

### 2.4 iTerm 拓扑（多项目并存）

```
        ┌──────────────────────┐    ┌──────────────────────┐
对话窗口 │  install-memory      │    │  cartooner-memory    │
        │  ❯ 第一入口           │    │  ❯ 第一入口          │
        └──────────────────────┘    └──────────────────────┘

工人窗口 ┌──────────────────────┐    ┌──────────────────────┐
        │  install-workers     │    │  cartooner-workers   │
        │  ┌────────┬────────┐ │    │  ┌────────┬────────┐ │
        │  │planner │designer│ │    │  │planner │designer│ │
        │  ├────────┴────────┤ │    │  ├────────┴────────┤ │
        │  │     reviewer    │ │    │  │     reviewer    │ │
        │  └─────────────────┘ │    │  └─────────────────┘ │
        └──────────────────────┘    └──────────────────────┘
```

每加一个项目 = +2 个 iTerm window (1 memory + 1 workers grid)。

---

## 3. Architecture Tiers

### Tier 1 — Decision + Memory (Per-Project Memory Seats)

每个 `<project>-memory`：
- LLM 决策（接收用户请求、做策略判断）
- 项目记忆（持有 TASKS / STATUS / 历史决策 / 项目知识库）
- 项目内派工（dispatch 给本项目 workers）
- **跨项目协作**：直接 `tmux-send <other-project>-memory` 发 dispatch 给其他项目的 memory
- 通过 `cmdq.jsonl` 给 Tier 3 watchdog 派系统级活

**HOME 模式**：REAL_HOME（不沙箱），原因：OAuth 必须复用宿主登录态；与现有 OAuth engineer seat 同等权限。

### Tier 2 — Workers (Per-Project Worker Seats)

`<project>-planner` / `<project>-designer` / `<project>-reviewer`：
- 接受 memory dispatch，执行具体任务
- 不直接面用户（汇报回 memory）
- 不能直接 dispatch 跨项目（必须通过自己 memory 中转）

### Tier 3 — Execution (No-LLM Watchdogs)

机器级 daemon 集群（无 LLM，纯 shell）：
- `watchdog-iterm-grid` — 监控所有 `<project>-memory` 和 `<project>-workers` 窗口存在性，缺失自动 recover
- `watchdog-cron-drift` — 校验 crontab 期望与现状
- `watchdog-tmux-health` — 关键 session alive 监控
- `watchdog-secrets-ttl` — token 即将过期预警
- `watchdog-disk-quota` — `~/.clawseat` 占用监控

**部署形态**：launchd plist，跑在用户身份下，0 LLM token 成本。
**输入/输出契约**：
- 写：`~/.clawseat/state/observations.jsonl`、`~/.clawseat/state/alerts.jsonl`
- 读：`~/.clawseat/state/policy.json`（仅 memory seat 可写）、`~/.clawseat/state/cmdq.jsonl`（memory 派活给 watchdog 用）
- 反馈：`~/.clawseat/state/cmdq-results.jsonl`

### Tier 0 — Templates

模板系统（§6）：
- repo 内置：`clawseat-minimal`（v2 第一个）、未来可加 `clawseat-engineering`（重写适配 v2）/ `clawseat-creative` 等
- 用户自定义：`~/.agents/templates/<name>.toml` ✅ v2 解锁
- 模板继承：`extends = "clawseat-minimal"` + override seat 字段
- 模板版本：`version` 字段 + 升级路径

---

## 4. Slash-Command Awareness

来自 operator 的明确要求："让 ClawSeat 知道如何使用 /new、/clear 等基础功能"。

> **Memory note**: Claude Code 的 slash-command **只能由真正的键盘输入触发**——LLM 在响应里写 `/clear` 文本不会被解释为命令。

设计：
- Tier 3 加一个 `watchdog-slash-injector` daemon，订阅 `cmdq.jsonl` 中 `kind: "slash"` 的指令
- memory seat 决策"该让某个 worker /clear context"时，写一行 cmdq:
  ```json
  {"kind": "slash", "target_seat": "install-planner", "command": "/clear", "reason": "context > 200k tokens"}
  ```
- watchdog 通过 `tmux send-keys` 真正按键投递（而非文本投递）
- 用途：定期 /clear 长上下文 worker、紧急 /new 重置卡死 seat 等

---

## 5. Open Questions（M1 不阻塞，M2 决定）

| # | 问题 | M1 临时方案 | M2 决策 |
|---|------|------------|---------|
| Q1 | 机器级 watchdog 归谁？ | install 时装机器级 launchd plist，跑无 LLM daemon | 确认 launchd plist 内容 |
| Q2 | bootstrap 时是否默认创建第一个项目？ | 否（install.sh 只装基础设施，用 `clawseat project new <name>` 创建） | 确认 |
| Q3 | memory skill 现在选型？ | 后期接口预留（M1 用 `~/.agents/memory/<project>/notes.md` placeholder）| 选型 mem0/letta/built-in/vector DB |
| Q4 | 大规模 (5+ 项目) iTerm UX | 自然摆放 | 探索 dock 风格 / Spaces 分桌面 |
| Q5 | per-project memory 的写权限范围 | 跟当前 OAuth engineer 一样 (REAL_HOME + dangerously-skip) | 加 ACL gate (只能写 cmdq.jsonl, 系统级 mutating 走 watchdog) |
| Q6 | 跨项目协作的限速 | memory ↔ memory 自由 dispatch | 加 rate limit / circuit breaker |

---

## 6. Implementation Milestones

### M1 — Skeleton (本 RFC 范围)

- [ ] `templates/clawseat-minimal.toml` 落到 v2 worktree（草案已有）
- [ ] install.sh 接受 `clawseat-minimal` 模板（去掉 3 名字白名单，改为 `templates/*.toml` 文件扫描）
- [ ] `install.sh` 修复 prompt_kind_first_flow 失效问题（pipe 兼容、--reinstall 也触发）
- [ ] 让 install.sh 创建项目时分别开 `<project>-memory` 和 `<project>-workers` 两个 iTerm 窗口
- [ ] 修复 `close t → close s` bug ([cartooner grid RCA #1](file:///tmp/clawseat-reports/cartooner-grid-rca-20260425-152000.md))
- [ ] memory seat 启动时挂 Stop hook：每次回合结束跑 `~/.clawseat/state/observations` 自检
- [ ] memory seat 接受 dispatch 协议（跟 v1 dispatch_task 兼容）
- [ ] 测试：`clawseat project new testbed --template clawseat-minimal` → 4 seat 正常 spawn → memory 收到用户对话

### M2 — Watchdog Tier

- [ ] `~/.clawseat/state/` 目录契约（policy.json / cmdq.jsonl / observations.jsonl / alerts.jsonl / cmdq-results.jsonl）
- [ ] `watchdog-iterm-grid` daemon
- [ ] `watchdog-cron-drift` daemon
- [ ] `watchdog-secrets-ttl` daemon
- [ ] `watchdog-slash-injector` daemon (触发 /clear / /new)
- [ ] launchd plist 装载脚本

### M3 — 自定义模板 + 继承

- [ ] `templates/*.toml` 文件扫描注册（去掉硬编码白名单）
- [ ] template `extends = "clawseat-minimal"` 继承机制
- [ ] `agent_admin template list/show/validate/create` 子命令
- [ ] 文档：如何写自定义模板

### M4 — 干掉 v1 旧拓扑

- [ ] 现有 install/cartooner/mor 项目迁移工具（v1 → v2 自闭环）
- [ ] 删除 v1 的 per-project ancestor 概念
- [ ] 删除 v1 的全局 machine-memory-claude
- [ ] 文档：v1 → v2 升级指南

---

## 7. Migration Plan

### 短期：v1 + v2 并存

- 当前 install (在 experimental 分支上) 保留作 baseline
- v2 新建项目用 `--template clawseat-minimal`，跑在 v2 worktree 的代码上
- 两套并存验证 1-2 周
- v2 验证通过后，提供迁移工具把 v1 项目转 v2

### 长期：完全切换 v2

- v2 stable 后 mark `clawseat-{default,engineering,creative}` 为 deprecated
- 至少 1 个发布周期保持兼容
- 然后正式删除 v1 拓扑代码

---

## 8. Decision Log（本次对话共识）

| 日期 | 决议 | 来源 |
|------|------|------|
| 2026-04-25 | 取消"全局 ancestor + 全局 memory"路线，改为"项目自闭环 + per-project memory" | operator 22:50~23:00 |
| 2026-04-25 | per-project memory 名 = `<project>-memory`（不再叫 `<project>-ancestor`）| operator 23:30 |
| 2026-04-25 | 没有 builder seat（planner 自己写代码） | operator 23:35 |
| 2026-04-25 | 没有 qa seat（M1 范围）| operator 23:35 |
| 2026-04-25 | 没有 global ancestor（"如果有多个项目，所有 memory 都是第一入口直接跟用户沟通"） | operator 23:42 |
| 2026-04-25 | 每个项目 2 个 iTerm 窗口（memory 独立窗口 + workers grid 窗口） | operator 23:42 |
| 2026-04-25 | planner 默认 claude，支持任意模型切换 | operator 23:48 |
| 2026-04-25 | reviewer 默认 codex，支持 oauth/api 切换；api 默认 xcode-best | operator 23:48 |
| 2026-04-25 | 跨项目协作通过 memory ↔ memory 直接 dispatch（无中介） | ancestor 提议 + operator 隐含同意 |

---

## 9. Review Workflow

本 RFC 完成草案后：

1. operator review（你正在看的就是）
2. operator 拍板后，dispatch 给 install team 实施
3. install team planner 出实施细则 → builder 编码 → reviewer code review
4. M1 完成后 operator 验收（用 `clawseat project new testbed` 创个最小项目跑通对话）
5. M1 验收通过 → 启动 M2

---

**End of RFC-001**
