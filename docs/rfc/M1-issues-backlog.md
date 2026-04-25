# M1 Issues Backlog

> 所有 v2 实施过程中发现的问题（含 operator 反馈、ancestor 自检发现、install-memory 报告的 ARCH-VIOLATION 等），等 install team 4 seat 齐后**统一派单修复**。

- **Worktree**: `/Users/ywf/coding/.claude/worktrees/clawseat-v2/`
- **Branch**: `refactor/clawseat-v2-self-contained`
- **Owner (post-Phase-A)**: install-memory → planner-claude → builder-codex → planner-claude review
- **Last updated**: 2026-04-26 (持续追加)

---

## 严重度分类

- **🔴 BLOCKER**: 阻塞 Phase-A 完成或 install team 工作
- **🟠 HIGH**: 影响用户体验或功能正确性，M1 内必修
- **🟡 MEDIUM**: 小瑕疵或文案漂移，M1 内可修
- **🟢 LOW**: 清扫项 / nice-to-have，M2 / M3 再修

---

## Issue 清单

### #1 brief 模板硬编码 5-worker，与 minimal 4-seat 不一致 — 🟠 HIGH

**症状**:
- `core/templates/ancestor-brief.template.md` 写死 `planner, builder, reviewer, qa, designer` (5 workers)
- minimal 模板只有 `planner, builder, designer` (3 workers, no reviewer/no qa)
- 渲染出的 `~/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md` 让 memory seat 按 5-seat 心智 spawn，会失败

**当前缓解**: ancestor 在 install 时手动 sed 修补（删除 reviewer/qa 字面量），但模板源头没改

**修复**:
- 改 `render_brief()` (install.sh Step 4) 让它读 PENDING_SEATS 动态渲染
- 或在 brief 模板里用 `{{seats}}` placeholder + Python 渲染时替换

**Owner**: builder-codex

---

### #2 auto_send_phase_a_kickoff 72s polling 窗口对 OAuth 太短 — 🟠 HIGH

**症状**:
- `auto_send_phase_a_kickoff()` (install.sh:1403) max_polls=24 × poll_seconds=3 = 72s
- 全新 identity HOME 启 Claude Code OAuth 时弹"Quick safety check / Trust folder"，operator 手动确认完平均 30-90s
- 加上 `ancestor_pane_waiting_on_operator()` 检测期，72s 经常不够，install.sh 总是落到 banner fallback

**修复**:
- max_polls 从 24 → 60（约 180s）
- 或增加智能等待：检测到 trust prompt 自动按 1 + Enter 通过

**Owner**: builder-codex

---

### #3 install.sh operator-guide banner 仍说 install-ancestor — 🟡 MEDIUM

**症状**: install.sh 末尾的 fallback banner 文案（约 1261-1313 行）所有 "install-ancestor pane" 引用没跟 PRIMARY_SEAT_ID 同步：
```
tmux capture-pane -t install-ancestor -p | tail -10
tmux kill-session -t install-ancestor
重新启动 ancestor (建议重跑 scripts/install.sh ...)
```

**修复**: banner 内的 `install-ancestor` 全替换为 `${PROJECT}-${PRIMARY_SEAT_ID}` 模板变量

**Owner**: builder-codex

---

### #4 memories 窗口应该用 tabs 而不是 split panes — 🟠 HIGH

**症状**:
- 当前 `memories_payload()` 用 split panes（grid_for_n 公式）
- operator 期望: 用 iTerm tabs，每个 tab = 1 个项目 memory，tab 标题清晰显示项目名

**期望最终态**:
```
Window: clawseat-memories
┌─ install ─┬─ cartooner ─┬─ mor ─┐  ← tab bar
├───────────┴─────────────┴───────┤
│                                  │
│   <selected project>-memory pane │  ← full window
│                                  │
└──────────────────────────────────┘
```

**修复**:
- `iterm_panes_driver.py` 加 `mode: "tabs"` 选项（用 `window.async_create_tab()` 而非 `session.async_split_pane()`）
- `memories_payload()` 输出 `mode: "tabs"`
- memories rebuild 协议改成"ensure tab for this project exists"（add/remove 单 tab，不重建整窗）
- tab 标题 = 项目名（不带 "-memory" 后缀）

**Owner**: builder-codex（实施）+ planner-claude（review tab 命名约定）

---

### #5 brief 的 "session status" 检查 assertion 过时 — 🟡 MEDIUM

**症状**: install-memory 跑 Phase-A 时报 ARCH-VIOLATION:
> brief 期望 `install-ancestor` session 存在,实际只有 `install-memory`

**根因**: brief 是 v1 心智下渲染的，"session status check" 会跑 `agent_admin session-name ancestor --project install`，对 v2 minimal 返回 `ancestor has no session in project install`

**修复**:
- brief 模板的 session check 步骤改用 PRIMARY_SEAT_ID（与 #1 一起做）
- 或把 brief 拆成 v1 / v2 两个变体（不推荐，维护负担）

**Owner**: builder-codex

---

### #6 install.sh 当前 memories 窗口实现是 close+rebuild — 🟢 LOW

**症状**: `Step 7b: rebuild shared memories window` 的实现是
```bash
osascript -e 'tell application "iTerm2" to close (every window whose name is "clawseat-memories")'
open_iterm_window "$(memories_payload)" _mem_window_id
```
每次 install 都把整个 memories 窗口关掉重开。其他项目的 memory pane 里如果用户正在打字，会丢草稿。

**修复**: 实现"ensure tab for this project exists"协议（与 #4 tabs 一起做更自然）
- 若窗口不存在 → 创建带 1 tab
- 若窗口存在且当前项目 tab 不在 → 追加 1 tab
- 若 tab 已存在 → 无操作

**Owner**: builder-codex（与 #4 合并）

---

### #7 projects.json 注册表未实现 — 🟢 LOW

**症状**: RFC §3.5 说要有 `~/.clawseat/projects.json` 跟踪所有项目；当前 memories_payload 用 `tmux ls grep -memory$` 临时枚举

**修复**:
- install.sh 创建项目时 append 到 `~/.clawseat/projects.json`
- uninstall 时删除
- memories_payload 优先读这个文件，fallback tmux 枚举

**Owner**: builder-codex

**优先级低**: 现有 tmux 枚举工作，正式注册表是 nice-to-have

---

### #8 Tier 3 watchdog 集群未实现 — 🟢 LOW (M2 范围)

**症状**: RFC §4 Tier 3 设计了 5 个 watchdog daemons（iterm-grid / cron-drift / tmux-health / secrets-ttl / slash-injector），全部未实施

**修复**: 见 RFC §6 M2 milestones 清单

**Owner**: 整个 install team（builder 实现 + planner review + designer review）

---

### #9 v1 全局 machine-memory-claude 仍在跑 — 🟢 LOW (M4 范围)

**症状**: v2 RFC 说删除 v1 全局 memory seat，但当前 machine-memory-claude tmux session 仍在跑

**修复**: M4 阶段（v2 stable 后）正式 deprecate + 删除

---

### #10 (预留新 issue 编号)

---

## 修复批次规划

### 批次 1（4 seat 齐后立刻派）— 🔴+🟠

- #1 brief 模板动态化
- #2 auto-send 窗口扩展
- #4 memories 窗口 tabs 改造
- #5 brief session check 修复

### 批次 2（批次 1 验收通过后）— 🟡

- #3 banner 文案
- #6 memories 增量 rebuild

### 批次 3（M2 启动）— 🟢 LOW + M2

- #7 projects.json 正式注册表
- #8 watchdog 集群

### 批次 4（M4）— 清扫

- #9 删除 machine-memory-claude

---

## Operator 实时反馈记录区

> Operator 持续报告的新问题在这里 append，附时间戳 + 上下文。

### 2026-04-26 02:00 — memories 窗口应用 tabs 而非 panes

→ 已建为 issue #4（HIGH）

### 2026-04-26 02:05 — install-memory 报 ARCH-VIOLATION（brief assert install-ancestor 存在）

→ 已建为 issue #5（MEDIUM）。临时决策: ancestor 已发 "proceed" 让 memory 把 brief assertion 视为 stale 继续 Phase-A。

---
