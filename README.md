# ClawSeat

## OpenClaw × gstack × superpowers × tmux = 一支住在你 Mac 里的 AI 研发团队

不上云。不订阅。在你的 Mac 上。

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![macOS 14+](https://img.shields.io/badge/macOS-14%2B-black)](docs/INSTALL.md)
[![OpenClaw](https://img.shields.io/badge/built%20on-OpenClaw-purple)](https://github.com/openclaw/openclaw)
[![gstack](https://img.shields.io/badge/powered%20by-gstack-orange)](https://github.com/garrytan/gstack)
[![superpowers](https://img.shields.io/badge/practices%20from-superpowers-9b72cb)](https://github.com/obra/superpowers)
[![PRs welcome](https://img.shields.io/badge/PRs-%E6%AC%A2%E8%BF%8E-brightgreen)](CONTRIBUTING.md)

---

```
clawseat-<project>-workers
┌──────────────────────────┬──────────────────────┐
│ planner main             │ builder              │
│ 拆解 / 派工 / 合并         │ 写代码 / 跑测试       │
│                          ├──────────────────────┤
│                          │ patrol               │
│                          │ 巡检 / 证据 / 回归    │
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

九十秒后，你有 5-6 个 seat（取决于模板）。memory 在 memories 窗口，
planner / builder / patrol / designer 在 workers 窗口；engineering 模板
再加 reviewer。各自住在沙箱里，互相说话。

> **你看。它们干活。**

---

## 三个开源巨头，织进一台 Mac

不是 agent 框架。不是 SaaS。是约 350 个 bash + Python 文件的一层薄壳，
把三个已经证明自己的开源项目缝在一起。

### 左：OpenClaw — agent **是谁**

[OpenClaw](https://github.com/openclaw/openclaw)（MIT）是本地跑的多通道
AI 助手 Gateway。Feishu / WhatsApp / Telegram / Slack / iMessage 等 20+
通道，同一个 agent 在所有通道里都是你。每个 agent 是独立进程、独立
sandbox、独立 memory。心跳机制让它主动行动，不只被动回复。
[ClawHub](https://clawhub.ai) 插件市场 101+ bundled extensions。

### 右：gstack — agent **会做什么**

[gstack](https://github.com/garrytan/gstack)（MIT）是给 Claude Code 用的
工程方法论 skill 包。30 个一键流水的咒语。`/ship` 是改→测→评→并→部→灰；
`/qa` 是定位→修→验；`/investigate` 是根因→法则→证据；`/cso` 是安全审计。
每一个本身就是一套完整流程。

### 上：superpowers — agent **怎么想事**

[superpowers](https://github.com/obra/superpowers)（Jesse Vincent，MIT，
2026-04-27 集成）是 Anthropic 内部沉淀出来的工程实践。十个 SKILL：
brainstorming / writing-plans / executing-plans / TDD /
systematic-debugging / verification-before-completion /
requesting-code-review / receiving-code-review /
finishing-a-development-branch / subagent-driven-development。

不是 prompt 技巧。是工程师的 default 反射——**什么时候该想，什么时候该写，
什么时候该验**。

### 中间：ClawSeat — 把三层叠在一起

每个 seat 不只是一个 prompt。它有**三层**。

身份：OpenClaw 给。
技能：gstack 给。
方法：superpowers 给。

三层叠加，每个 seat 才是一个**完整的工程师**——不是一个 wrapper 调用更多
API，是一个 agent 学会了**做事的态度**。

| seat | 身份 | 技能 | 方法 |
|---|---|---|---|
| memory | OpenClaw memory agent | gstack `/cs` 系列 | brainstorming / writing-plans / verification |
| planner | OpenClaw planner agent | `/plan-eng-review` `/plan-ceo-review` | writing-plans / executing-plans / finishing-a-branch |
| builder | OpenClaw builder agent | `/ship` `/investigate` `/land-and-deploy` | executing-plans / TDD / code-review × 2 / subagent-driven-dev |
| reviewer | OpenClaw reviewer agent | `/review` | receiving-code-review / verification-before-completion |
| patrol | OpenClaw patrol agent | scheduled evidence scans | verification-before-completion / systematic-debugging |
| designer | OpenClaw designer agent | `/design-review` `/design-shotgun` | brainstorming |

---

## 三件事让它不一样

### 一. 你跟它对话，它就装好了

别家 agent 编排要 wizard、YAML DSL、集群 control plane。ClawSeat 只要
一句话。你的 AI 自己 clone、扫环境、问 provider、拉 4 个 seat、引你走完
Phase-A。

> **这才叫 AI 原生。**

### 二. 你看见它在干

不是 dashboard。不是 log 流。是活的 TUI：memory 在 memories 窗口，
workers 在项目窗口，每一格是一个真正在思考的 agent。

你看见 planner 否决 builder 的 diff。
你看见 builder 默默 TDD 一遍才提交。
你看见 designer 和 builder 为一个按钮吵五个来回。

> **你看见你的团队在工作——因为它们就是你的团队。**

### 三. 三层全开，每一行你都能改

ClawSeat 自己 ~350 文件。OpenClaw / gstack / superpowers 全 MIT。

想让 planner 更凶？改 `core/skills/planner/SKILL.md`。
想换 gstack skill 绑定？改 `core/scripts/seat_skill_mapping.py` 一行。
想加新通道？OpenClaw 的 plugin SDK 写一个就完。
想换 superpowers practice？删掉 SKILL.md 里那段 borrowed 引用就行。
想 fork 整个栈？四个项目都是 MIT，整套拿走。

没有 Docker。没有 YAML 状态机。没有封闭的 plugin 墙。

---

## 为什么不是 X

| 你已经有 | 它给你 | ClawSeat 多给什么 |
|---|---|---|
| **Cursor / Windsurf** | IDE 内嵌一个 AI pair | 四个专业化 agent 并行，每人管自己的事 |
| **Devin / Replit Agents** | 云端单 agent 跑长任务 | 本地、可看见、可打断、每一行代码都在你 Mac 上 |
| **LangChain / AutoGen** | Python 框架写 agent 流程 | 零 DSL；流程是 SKILL.md 自然语言 |
| **OpenClaw 单用** | 多通道 AI 助手 | 把它扩成研发团队，配 iTerm 双窗口 + gstack 流水 + superpowers 方法 |
| **gstack 单用** | 30+ Claude Code skill | 按 seat 角色分发，planner 派一句 intent 就自动激活正确咒语 |
| **superpowers 单用** | 一组 SKILL.md 工程实践 | 把 practice 作为「borrowed」嵌进每个 seat 的 SKILL，让方法变成 seat 的肌肉记忆 |

**ClawSeat 不取代任何一个**——是把你已经信的几个缝合成一个你能**看见**的
团队。

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
给爱拆开研究整个工具链的人。

> **就是你。**

---

## FAQ

**Q: 这玩意只在 Mac 上能跑？**

现在是。我们用 iTerm 网格 + macOS Keychain 路由 + LaunchAgent。Linux 能
跑核心功能但少了网格可视化。Windows 没测试。欢迎 PR——绝不 trivial。

**Q: 不用 Docker 怎么隔离 agent？**

`$HOME` 沙箱 + PATH 操控 + 符号链接。每个 seat 的
`~/.agent-runtime/identities/.../home/` 是独立 HOME。比 Docker 轻，但不
隔离系统库——这是 feature，让 seat 共享你的 Homebrew 和 iTerm 配置。

**Q: API key 会被传给 ClawSeat 的作者吗？**

不会。零网络请求出去 ClawSeat。直接向你配的 provider 发请求。零 telemetry，
零 phone-home。grep 整个代码库搜 `http` 验证。

**Q: superpowers 是什么时候加的？**

2026-04-27。导入 commit `6efe32c9`。十个 SKILL.md 原样存
`core/references/superpowers-borrowed/`，每个 seat 在自己 SKILL.md 的
"Borrowed Practices" 段落引用——不改原文，不污染上游。
license MIT，attribution 在 [`core/references/superpowers-borrowed/ATTRIBUTION.md`](core/references/superpowers-borrowed/ATTRIBUTION.md)。

**Q: 一个月烧多少 token？**

5-6 个 seat 同时活跃，成本取决于模板和 provider。大头是 builder 和 planner。
建议 minimax-M2 这种国产 API 跑轻量 seat，Claude Opus 只给 memory + planner。
混搭一天 $10–30 跑完整迭代。

**Q: 坏了怎么办？**

`./scripts/clean-slate.sh --yes` 一键清空重装。state.db 有所有 dispatch
历史。所有文件是纯文本，vim 能改、git 能 bisect。

---

## 深入

- [INSTALL guide](docs/INSTALL.md) | [安装指南（中文）](docs/INSTALL.zh-CN.md)
- [`docs/INSTALL.md`](docs/INSTALL.md) — 你的 AI 会自己读
- [`docs/OPENCLAW.md`](docs/OPENCLAW.md) — ClawSeat 怎么用 OpenClaw 的
- [`docs/GSTACK.md`](docs/GSTACK.md) — 哪个 seat 装哪些 gstack skill
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — L1/L2/L3 金字塔 + dispatch 协议
- [`docs/HACKING.md`](docs/HACKING.md) — 想改哪就改哪的导览
- [`core/references/superpowers-borrowed/`](core/references/superpowers-borrowed/) — Jesse Vincent 的十个工程实践原文

## 仓库角色

- `~/ClawSeat` 是 install/release clone，永远在 `main`
- LaunchAgent 每天自动 fast-forward（首次安装 opt-in）
- 每次跑 `install.sh` 自检 + auto fast-forward
- 开发用单独 worktree：`git worktree add ~/path/to/dev <branch>`

## 许可

MIT。ClawSeat、OpenClaw、gstack、superpowers 全是。
