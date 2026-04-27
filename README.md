# ClawSeat

## Repository Roles

- `~/ClawSeat` is the install/release clone. Always on `main`.
- Auto-updates daily via LaunchAgent (opt-in during first install).
- Each `install.sh` run does a self-check + auto fast-forward.
- For dev work, use a separate worktree:
  `git worktree add ~/path/to/dev <branch>`

## OpenClaw × gstack × tmux = 一支住在你 Mac 里的 AI 研发团队

不上云。不订阅。在你的 Mac 上。

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![macOS 14+](https://img.shields.io/badge/macOS-14%2B-black)](docs/INSTALL.md)
[![OpenClaw](https://img.shields.io/badge/built%20on-OpenClaw-purple)](https://github.com/openclaw/openclaw)
[![gstack](https://img.shields.io/badge/powered%20by-gstack-orange)](https://github.com/garrytan/gstack)
[![PRs welcome](https://img.shields.io/badge/PRs-%E6%AC%A2%E8%BF%8E-brightgreen)](CONTRIBUTING.md)

---

```
clawseat-<project>-workers
┌──────────────────────────┬──────────────────────┐
│ planner main             │ builder              │
│ 拆解 / 派工 / 合并        │ 写代码 / 跑测试       │
│                          ├──────────────────────┤
│                          │ designer             │
│                          │ 视觉 / 交互 / 资源    │
└──────────────────────────┴──────────────────────┘

clawseat-memories
┌─────────────────────────────────────────────────┐
│ <project>-memory tabs, one project per tab      │
└─────────────────────────────────────────────────┘
```

---

## 一句话装好

给你的 Claude 讲这句话：

> Install ClawSeat on my Mac. Clone `https://github.com/KaneOrca/ClawSeat`
> to `~/ClawSeat`, then read `~/ClawSeat/docs/INSTALL.md` and follow it.
> Ask me for every choice.

本地已经有 `~/ClawSeat` 的拷贝？换这句：

> Install ClawSeat from my local `~/ClawSeat` (do not clone from GitHub,
> use the directory as-is). Read `~/ClawSeat/docs/INSTALL.md` and follow
> it. Ask me for every choice.

九十秒后，你有四个 agent——memory 在 memories 窗口，planner / builder /
designer 在 workers 窗口，各自住在沙箱里，互相说话。

> **你看。它们干活。**

---

## ClawSeat 是**把两个开源巨头织进一台 Mac**的那层

不是另一个 agent 框架。不是又一个 SaaS。是一层约 350 个文件的 bash + Python，
把两个已经证明自己的开源项目织在一起——让它们当你的研发团队。

### 左边：OpenClaw — 通道 + Agent 控制面

[OpenClaw](https://github.com/openclaw/openclaw)（MIT 开源）是一个本地跑的
多通道 AI 助手 Gateway。Feishu / WhatsApp / Telegram / Slack / Discord /
iMessage 等 20+ 通道，同一个 agent 在所有通道里都是你。每个 agent 是独立
进程、独立 sandbox、独立 memory。心跳机制让 agent 主动行动，不只被动回复。
插件市场 [ClawHub](https://clawhub.ai) 里 101+ bundled extensions。

ClawSeat 借它的：ACP agent 进程模型、Feishu 通道桥接、心跳调度、koder
overlay（把一个 OpenClaw agent 变成 ClawSeat 的反向信道）、state.db 事件总线。

### 右边：gstack — 方法论工具包

[gstack](https://github.com/garrytan/gstack)（MIT 开源）是一套给 Claude Code
用的工程方法论 skill 包。30+ 种技能，每个都是一套完整流程——`/ship`（改代码
→ 跑测试 → review → merge → 部署 → canary）、`/qa`（定位 bug → 修 → 验）、
`/review`（pre-merge 审核）、`/investigate`（根因调查 iron law）、`/cso`（安全
审计）、`/design-review`（视觉 QA）⋯⋯每一个都像请了个专家站你旁边。

ClawSeat 借它的：builder 默认装 `/ship` + `/investigate` + `/land-and-deploy`；
designer 装 `/design-review` + `/design-shotgun`；planner 装 `/plan-eng-review`、
`/plan-ceo-review`、`/plan-design-review`，同时承担代码审查。每个 seat 生来就会做自己该做的事。

### 中间：ClawSeat — 编排粘合层

把两者整合进 iTerm 双窗口：

- **4 seat roster**（memory / planner / builder / designer）
  ——每个对应一个 OpenClaw agent 身份 + 一组 gstack skills
- **dispatch 协议**——三阶段状态机（assigned → notified → consumed），每一阶段
  写 `handoff.json` + `state.db`，seat 崩了能从上次位置接回
- **intent 系统**——planner 派活时写 `--intent ship`，harness 自动注入 gstack
  trigger phrase + 对应 SKILL.md，builder 自动激活 `/ship` 方法论，不用谁记咒语
- **AI 原生安装**——本来就该这样
- **workers window + memories window 可视化**——本来也该这样

---

## 三件事让它不一样。

### 你跟它对话，它就装好了。

别家 agent 编排要 wizard、YAML DSL、集群 control plane。ClawSeat 只要一句话。
你的 AI 自己 clone、扫环境、问 provider、拉 4 个 seat、引你走完 Phase-A。

> **这才叫 AI 原生。**

### 你看见它在干。

不是 dashboard。不是 log 流。是活的 TUI：memory 在 memories 窗口，workers
在项目窗口，每一格是一个真正在思考的 agent。

你看见 planner 否决 builder 的 diff。
你看见 planner 拿 gstack `/plan-eng-review` 拆解需求。
你看见 designer 和 builder 为一个按钮吵五个来回。

> **你看见你的团队在工作——因为它们就是你的团队。**

### 巨人的肩上，每一行你都能改。

ClawSeat 自己只有 ~350 个文件。OpenClaw 和 gstack 也都 MIT 开源。三层全开。

想让 planner 更凶？改 `core/skills/planner/SKILL.md`。
想换 gstack skill 绑定？改 `core/scripts/seat_skill_mapping.py` 一行。
想加通道（Slack 不够，要 DingTalk）？OpenClaw 的 plugin SDK 写一个就完。
想把 builder 换成 Codex 而不是 Claude？改项目的 `project-local.toml` 里的
seat provider 配置。
想 fork 整个栈？三个都是 MIT，整套拿走。

没有 Docker。没有 YAML 状态机。没有封闭的 plugin 墙——插件走的是上游
OpenClaw 的 SDK + ClawHub 市场，生态比我们大得多。

---

## 为什么不是 X？

| 你已经有 | 它给你 | ClawSeat 多给什么 |
|---|---|---|
| **Cursor / Windsurf** | IDE 内嵌一个 AI pair | 四个专业化 agent 并行，每人管自己的事（不是一个万能助手） |
| **Devin / Replit Agents** | 云端单 agent 跑长任务 | 本地、可看见、可打断、每一行代码都在你 Mac 上 |
| **LangChain / LangGraph** | Python 框架写 agent 流程图 | 零 DSL、零 YAML 状态机；流程是 SKILL.md 自然语言 |
| **AutoGen / CrewAI** | 多 agent 库，代码里组编队 | CLI 装一下就是一整队，不写 agent 代码 |
| **OpenClaw 单用** | 多通道 AI 助手 + 插件市场 | 把它扩成研发团队，配 iTerm workers/memories 窗口 + gstack 方法论 |
| **gstack 单用** | 30+ Claude Code skill | 把它按 seat 角色分发，planner 派一句 intent 就自动激活正确咒语 |

**共同点**：ClawSeat 不是取代任何一个——是把**你已经信的几个**缝合成一个你能**看见**的团队。

---

## 装它

```bash
git clone https://github.com/KaneOrca/ClawSeat ~/ClawSeat
cd ~/ClawSeat && ./scripts/install.sh --project demo
```

或者，跟你的 AI 说一句话。结果一样。

---

## 这是给谁的

给已经在付 Claude Pro、Codex Plus 或 Gemini Advanced 的人。
给用 Mac 的人。
给懂 tmux 的人。
给不想再学一个云端 console 的人。
给爱拆开研究整个工具链的人。

> **就是你。**

---

## FAQ

**Q: 我已经有 Cursor，为什么还要这个？**

Cursor 给你 IDE 里一个 pair。ClawSeat 给你四个各司其职的专业化 agent。
互补，不互斥。你可以在 Cursor 里改代码，同时 ClawSeat 的 planner 审你的
diff、builder 跑回归。

**Q: 这玩意只在 Mac 上能跑？**

现在是。我们用 iTerm 网格 + macOS Keychain 路由 + LaunchAgent。Linux 能
跑核心功能但少了网格可视化。Windows 没测试。欢迎 PR——但绝不是 trivial
工作量。

**Q: 不用 Docker 怎么隔离 agent？**

用 `$HOME` 沙箱 + PATH 操控 + 符号链接。每个 seat 的
`~/.agent-runtime/identities/.../home/` 是独立 HOME。比 Docker 轻，但不
隔离系统库——这是 feature，让 seat 共享你的 Homebrew 和 iTerm 配置。

**Q: API key 会被传给 ClawSeat 的作者吗？**

不会。一次网络请求都没有。ClawSeat 只跑在你本地，直接向你配的 provider
（Anthropic / OpenAI / Google / minimax 等）发请求。零 telemetry，零
phone-home。你能 grep 整个代码库搜 `http` 验证。

**Q: 一个月烧多少 token？**

四个 agent 同时活跃 ≈ 一个 Cursor Pro session × 4。实际用下来大头是
builder 和 planner。我们建议 minimax-M2 这种国产 API 跑轻量 seat，
Claude Opus 只给 memory + planner。配好混搭一天 $10-30 跑完整迭代。

**Q: 坏了怎么办？**

`./scripts/clean-slate.sh --yes` 一键清空重装。state.db 有所有 dispatch
历史，恢复 chain 走 `verify_handoff.py --task-id X`。所有文件是纯文本，
vim 能改、git 能 bisect。

---

## 深入

- [`docs/INSTALL.md`](docs/INSTALL.md) — 你的 AI 会自己读
- [`docs/OPENCLAW.md`](docs/OPENCLAW.md) — ClawSeat 怎么用 OpenClaw 的
- [`docs/GSTACK.md`](docs/GSTACK.md) — 哪个 seat 装哪些 gstack skill
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — L1/L2/L3 金字塔 + dispatch 协议
- [`docs/HACKING.md`](docs/HACKING.md) — 想改哪就改哪的导览

## 许可

MIT。ClawSeat、OpenClaw、gstack 全是。
