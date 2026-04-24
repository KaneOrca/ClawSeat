# ClawSeat

## 一句话，六个 AI 工程师，装进你的 Mac。

不上云。不订阅。在你的 Mac 上。

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![macOS 14+](https://img.shields.io/badge/macOS-14%2B-black)](docs/INSTALL.md)
[![PRs welcome](https://img.shields.io/badge/PRs-%E6%AC%A2%E8%BF%8E-brightgreen)](CONTRIBUTING.md)

---

```
┌─────────────────┬─────────────────┬─────────────────┐
│    ancestor     │     planner     │     builder     │
│    正在统筹     │    正在拆解     │    正在写代码   │
├─────────────────┼─────────────────┼─────────────────┤
│    reviewer     │       qa        │    designer     │
│   正在审 diff   │    正在跑测试   │    正在改 UI    │
└─────────────────┴─────────────────┴─────────────────┘
```

---

给你的 Claude 讲一句话：

> Install ClawSeat on my Mac. Clone `https://github.com/KaneOrca/ClawSeat`
> to `~/ClawSeat`, then read `~/ClawSeat/docs/INSTALL.md` and follow it.
> Ask me for every choice.

九十秒后，你有六个 agent——在六格 iTerm 里各自跑着，各自住在沙箱里，互相说话。

你看。它们干活。

---

## 三件事让它不一样。

### 你跟它对话，它就装好了。

别家 agent 框架都要 wizard、YAML、云端 console。ClawSeat 只要一句话。
你的 AI 自己读文档。你的 AI 自己问你要哪家 provider、哪个项目、要不要开飞书。
你的 AI 自己告诉你装完了。

这才叫 AI 原生。

### 你看见它在干。

不是 dashboard。不是 log 流。是六格活的 TUI，每一格是一个真正在思考的 agent。

你看见 reviewer 否决 builder 的 diff。
你看见 planner 在 QA 找出 bug 后改方向。
你看见 designer 和 builder 为一个按钮吵五个来回。

你看见你的团队在工作——因为它们就是你的团队。

### 你掌握每一行。

350 个文件。全是 bash、Python、Markdown。

想让 planner 更凶？改一个 markdown。
想加一个 seat？`core/scripts/seat_skill_mapping.py` 加一行。
想 fork 整个系统？MIT 许可，拿走。

没有 Docker。没有 plugin SDK。改源码就是扩展方式。

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

就是你。

---

## 深入

- [`docs/INSTALL.md`](docs/INSTALL.md) — 你的 AI 会自己读
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 为想拆开看看的人
- [`docs/HACKING.md`](docs/HACKING.md) — 想改哪就改哪

## 许可

MIT。
