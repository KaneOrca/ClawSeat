# Session Handoff — ClawSeat v2 Refactor

> 此文件用于：(a) 上下文压缩后让我（ancestor）快速 reload 状态；(b) operator 一目了然当前进度。
> **last updated**: 2026-04-26 02:30+
> **Author**: ancestor (cartooner-ancestor session, Opus 4.7)

---

## TL;DR — 一段话状态

ClawSeat v2 架构 (RFC-001) 已设计 + 部分实施完成。**install-memory + planner-claude + builder-codex + designer-gemini 4-seat team 已活**，正在 Phase-A 完成后接收 M1 任务包。Backlog 共 12 issue 分 5 批次，install team 自驱实施。Operator 持续报新问题，ancestor 继续追加到 backlog。

---

## 关键路径

| 路径 | 用途 |
|------|------|
| `/Users/ywf/coding/.claude/worktrees/clawseat-v2/` | v2 worktree (分支 `refactor/clawseat-v2-self-contained`，基于 `clawseat/experimental`) |
| `~/clawseat` (= `/Users/ywf/clawseat`) | v1 worktree on `experimental` (baseline，未动) |
| `/Users/ywf/coding/ClawSeat` | 主仓 on `main` (115 commits 落后，未动) |
| `docs/rfc/RFC-001-self-contained-project-architecture.md` | v2 完整架构 |
| `docs/rfc/M1-issues-backlog.md` | 12 issue 完整追踪 + 5 批次规划 + operator 反馈区 |
| `templates/clawseat-minimal.toml` | 4-seat 模板 (memory + planner + builder + designer) |
| `scripts/install.sh` | install 入口 (含 PRIMARY_SEAT_ID + 2-mode prompt + workers/memories 双窗口) |
| `core/scripts/iterm_panes_driver.py` | iTerm 窗口驱动 (含 recipe override 机制) |
| `core/scripts/agent_admin_window.py` | 窗口管理 (PRIMARY_SEAT_ID 抽象) |
| `core/scripts/agent_admin_session.py` | seat session 管理 |

---

## v2 架构核心（必读 RFC §1-§3 否则会"幻觉"）

### 词汇（canonical）

| Term | Definition |
|------|-----------|
| **始祖 / ancestor** | SEAT TYPE — 每项目 1 个，tmux 名 `<project>-memory`，4 capabilities |
| **memory (capability)** | 项目持久知识库 (TASKS / STATUS / 决策史)，住在 ancestor 上，**非独立 seat** |
| **research (capability)** | 主动调研 (grep / Bash / 查文档)，住在 ancestor 上，**非独立 seat** |
| **dispatch (capability)** | 派工给项目 worker 或跨项目派给其他 memory |
| **dialog (capability)** | 用户对话第一入口 |
| **project** | 4-seat 自闭环单元: `<project>-memory` + planner + builder + designer |
| **没有全局 seat** | 没有 global ancestor / global memory；跨项目 = memory ↔ memory 直接 dispatch |

### Seat 命名（canonical）

```
<project>-memory                     primary seat (项目大脑)
<project>-planner-claude             worker: 规划 + code review
<project>-builder-codex              worker: 代码执行
<project>-designer-gemini            worker: 审美 / 视觉
```

### 工具分配理由（"用 LLM 各自所长"）

- Claude (memory + planner): 长上下文 + 强判断 + code review
- Codex (builder): GPT-5.4 codegen
- Gemini (designer): 多模态视觉

### iTerm 窗口拓扑

- **`clawseat-memories`** (全局共享): N 项目 memory 都在这；M1.5 任务: 改 tabs (每 tab = 1 项目)；当前还是 split panes
- **`clawseat-<project>-workers`** (per-project): planner main 左 50% + 右侧 grid (max 2 rows, expand cols, col-major fill)

总窗口数 = N+1 (N 项目 = 1 memories + N workers)

---

## 已完成的代码 commits

```
aeba4c7  docs: backlog 文件 (M1-issues-backlog.md, 9 issues)
90dd60b  fix: #10 workers planner pane wait-for-seat (BLOCKER 自修)
8e29345  feat: 双窗口拓扑 (workers + memories)
f3907bb  docs: 锁定窗口拓扑设计 (RFC §3 + minimal template window_layout)
807d281  fix: kind-first prompt 文本对齐 (planner+builder+designer)
e0d3395  refactor: PRIMARY_SEAT_ID 抽象 (install.sh 8 处 + Python 5 处) + 模板角色重分
70c0a73  feat: 2-mode prompt + clawseat-minimal whitelist + reinstall session resurrect
7a2cae0  docs: RFC-001 v1 草案
```

加上后续可能添加的 commit (如果 install team 已经开始干): 检查 `git log --oneline refactor/clawseat-v2-self-contained` 即可。

---

## 当前 install team 状态 (post Phase-A)

| Seat | tmux name | LLM | Auth | Status |
|------|-----------|-----|------|--------|
| memory | `install-memory` | Claude Opus 4.7 (1M) | OAuth Pro | running, 已收 M1 dispatch |
| planner | `install-planner-claude` | Claude | OAuth | running, 已 ack ping |
| builder | `install-builder-codex` | Codex | OAuth | running |
| designer | `install-designer-gemini` | Gemini 3 | OAuth | running |

iTerm 窗口:
- `clawseat-memories`: 1 pane attached to install-memory
- `clawseat-install-workers`: 3 panes (planner / builder / designer 各自 attach)

`~/.agents/tasks/install/STATUS.md` 已写 (Phase-A 完成):
```
phase=ready
completed_at=2026-04-26T02:10:00Z
template=clawseat-minimal (v2)
roster=memory(=ancestor), planner, builder, designer
```

---

## M1 Issues Backlog 状态 (12 issues, 5 批次)

**详见 `docs/rfc/M1-issues-backlog.md`**

| 批次 | Status | Issue # | 简述 |
|------|--------|---------|------|
| 0 (ancestor 自修) | ✅ DONE | #10 | workers planner pane wait-for-seat (commit 90dd60b) |
| 1 (HIGH) | ⏳ install team 接手 | #1 #2 #4 #5 #11 #12 | brief 模板动态化 / auto-send 窗口扩展 / memories tabs / brief session check / reseed-pane AppleScript / recover-grid 重构 |
| 2 (MEDIUM) | pending 批次 1 | #3 #6 | banner 文案 / memories 增量 rebuild |
| 3 (LOW + M2) | pending | #7 #8 | projects.json / watchdog 集群 |
| 4 (M4) | pending | #9 | 删 machine-memory-claude |

---

## 上下文压缩后我应该做什么

如果上下文被压缩了，重新 reload 这个文件 + 检查以下：

1. **install-memory 的最新 pane 内容** — 看它处理 M1 backlog 进展到哪了
   ```bash
   /opt/homebrew/bin/tmux capture-pane -t install-memory -p -S -200 | tail -50
   ```

2. **v2 worktree 最新 commits**
   ```bash
   git -C /Users/ywf/coding/.claude/worktrees/clawseat-v2 log --oneline -20
   ```

3. **Backlog 是否有 operator 新追加**
   ```bash
   grep -A5 "^### 2026-04-26" /Users/ywf/coding/.claude/worktrees/clawseat-v2/docs/rfc/M1-issues-backlog.md
   ```

4. **install team 4 seat 是否还活着**
   ```bash
   /opt/homebrew/bin/tmux ls | grep "^install-"
   ```

5. **Operator 当前注意力在哪** — 看 conversation 最近一条 user message

---

## 工作模式 (operator 偏好)

1. **大粒度派工**: 我不参与每个 commit review。install team 自驱 verify→fix→reverify，完成批次再回报
2. **持续追加 issue**: operator 报新问题 → 我立刻 append 到 `docs/rfc/M1-issues-backlog.md` 的"Operator 实时反馈记录区" + 必要时建新 issue (编号自增，当前到 #12，下一个是 #13)
3. **快速 ack 指令**: operator 用 "继续" / "OK" / "同意" 等短词推进；我应快速行动不啰嗦确认
4. **ClawSeat 代码实施职责** = install team。ancestor 只在以下情况自己改代码:
   - 自己引入的 bug (如 #10)
   - 阻塞 install team 启动的最小修复
   其他情况一律派给 install-memory
5. **文档先行**: 重大决策先写 RFC 再写代码，避免幻觉漂移
6. **memory note 已记**: operator 多次纠正"用 ClawSeat 脚本而非裸 tmux send-keys"。所有 send 必走 `send-and-verify.sh --project install <seat> "..."` 或 `tmux-send <session> "..."`

---

## 与 install-memory 通信模板

```bash
/Users/ywf/clawseat/core/shell-scripts/send-and-verify.sh --project install memory "你的消息"
```

注意 v2 的 send-and-verify 仍是 v1 路径 (`~/clawseat/core/shell-scripts/`)，因为 install team 用的是 v1 path 的 send-and-verify。v2 worktree 也有同样脚本但路径不同。

跨项目 (如果有 cartooner-memory 活着):
```bash
/opt/homebrew/bin/tmux send-keys -t install-memory "..."  # 不推荐，没有 verify
# 或更好:
/Users/ywf/.local/share/agent-launcher/bin/tmux-send install-memory "..."
```

---

## 已知未解事项 (operator 有待决策)

1. **memories 窗口 tabs vs panes 的实施细节** — 已建为 #4 HIGH，待 install team 实施。Operator 已确认要 tabs。
2. **批次 1 拆解方案** — install-memory 正在制定中（监控显示它在调用 dispatch_task.py 给 planner 派 Package A）。等它给方案后 ancestor 知会 operator。
3. **operator 持续报新问题** — 模式确立: operator 报 → ancestor append backlog → install team 取 → 修。不打断 install team 节奏。

---

**End of Handoff**
