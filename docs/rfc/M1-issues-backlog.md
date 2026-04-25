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

**追加 (2026-04-26 Package A audit)**：planner 跑 grep 时发现更多同类 stale，Package A 有意超出 TODO scope 未动；合并到 #3 一起修：
- `scripts/install.sh` L1305, L1338, L1351, L1479, L1505 (operator-guide message strings)
- `scripts/launch-grid.sh:27` — v1 5-seat `SEATS=(ancestor planner builder reviewer qa designer)`
- `scripts/launch_ancestor.sh:149` — v1 ancestor launcher
- `core/launchers/agent-launcher.sh:683` — comment
- `core/scripts/agent_admin_session.py:683` — comment
均为非运行时关键路径，不阻塞功能，批次 2 处理。

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

### #10 workers_payload planner pane 错用 tmux attach 而非 wait-for-seat — 🔴 BLOCKER

**症状**:
- v2 workers_payload() 把 planner pane 的 command 写成 `tmux attach -t '={project}-planner-claude'`
- 但 planner-claude tmux session 在 install.sh 跑完时**还不存在**（要等 memory seat 在 Phase-A 中 spawn）
- 结果 planner pane 立刻 tmux attach 失败 → fall through 到 zsh，不会自动 attach 成功后的 planner

**对比 builder/designer**: 它们用 `bash wait-for-seat.sh install builder` 正确轮询直到 session 存在再 attach

**根因**:
- 我写 workers_payload 时沿用了 v1 grid_payload 的"第一个 pane 是 primary seat 用 tmux attach"模式
- 但 v1 primary seat (ancestor) 是 Step 5 install.sh 直接 launch 的，已经存在
- v2 workers 窗口里 planner 不是 primary seat (memory 才是, 在另一个窗口), planner 是要被 memory spawn 的 worker, 与 builder/designer 同地位

**修复**: workers_payload() 把 planner 的 command 也改成 `bash wait-for-seat.sh <project> planner`

**Owner**: ancestor 自己立刻修（这是我新引入的 bug, 不是历史债）

**临时缓解**: install-memory 完成 Phase-A spawn planner-claude 后, operator 手动 close workers 窗口 + 重开（此时 planner-claude session 已存在）

---

### #11 agent_admin window reseed-pane iterm2 API send_text 失效 — 🟠 HIGH

**症状**:
- `agent_admin window reseed-pane <project> <seat>` 走 iterm2 Python API 路径
- API 返回 success，但 send_text 序列（Ctrl-C + Ctrl-B+d + 命令）**没真正写入空闲 zsh shell**
- 直接用 iTerm AppleScript `write text` 才生效

**对比**: install.sh 主流程 open_iterm_window 用的是 iterm_panes_driver.py，用 `async_send_text()` 也是 API 路径——但首次创建 pane 时（pane 刚开就发命令）OK；reseed-pane 是对**已有 idle pane** 发命令时失败

**可能根因**: iterm2 Python API 的 send_text 对刚 attached 的 session 工作，但对 idle 的 zsh 可能需要先获取 keyboard focus 或 send_keys 而不是 send_text

**修复方案候选**:
- a. reseed-pane 改用 osascript AppleScript "tell application iTerm2 ... write text" (绕开 Python API bug)
- b. send_text 前先 `await session.async_activate()` 取 focus
- c. 用 send_keys 模拟物理键盘事件而非文本注入

**Owner**: builder-codex (实施) + planner-claude (测试 reseed-pane 在 v2 minimal 各场景下都工作)

---

### #12 recover-grid.sh + grid-recovery 路径硬编码 install-ancestor — 🟠 HIGH

**症状**:
- `scripts/recover-grid.sh` 和 `agent_admin_session.py` 内部 grid_recovery_log 等路径全部假设 `${PROJECT}-ancestor`
- v2 minimal 用 `${PROJECT}-memory`，recover-grid 找不到对的 session 名

**与 issue #10 关系**: 都属于"我之前 PRIMARY_SEAT_ID 重构漏改的硬编码点"批次。我审过 install.sh + agent_admin 主路径但没审 recover-grid.sh 等辅助脚本

**修复**: recover-grid.sh + 所有相关辅助脚本统一查 PRIMARY_SEAT_ID（从 `~/.agents/projects/<project>/project.toml` 或 session.toml 读 first engineer.id）

**Owner**: builder-codex

**关联**: 跟 #10 同根（PRIMARY_SEAT_ID 重构不彻底），可一起 PR

---

### #13 v2 split topology 漂移 — 5 个偏离点 — 🟠 HIGH

**operator 实证 (2026-04-26 03:00)**: 跑 `recover-grid.sh install` 后, install-memory 被双 attach (出现在 v1 风格 `clawseat-install` 单窗 + v2 风格 `clawseat-memories` 双窗)。

**根因**: v2 双窗逻辑只在 install.sh shell 函数里 (workers_payload/memories_payload), 没下沉到 Python `agent_admin_window` 模块。任何绕过 install.sh main() 的调用方都回到 v1 单窗。

**5 个偏离点**:

| # | 位置 | 问题 |
|---|------|------|
| 漂移 1 | `core/scripts/agent_admin_window.py:215-256` `build_grid_payload()` | 只懂 v1 单窗 (panes[0]=primary seat, panes[N+1]=machine-memory-claude); 没有 v2 split 选项 |
| 漂移 2 | `core/scripts/agent_admin_window.py:366` `open_grid_window()` | 不区分模板, 永远调 build_grid_payload |
| 漂移 3 | `scripts/recover-grid.sh:65` | 通过 `agent_admin.py window open-grid` 间接落入漂移 1+2 |
| 漂移 4 | 缺少 Python API `open_workers_window()` + `ensure_memories_pane()` | v2 双窗逻辑只在 install.sh, 其他调用方没法复用 |
| 漂移 5 | `agent_admin_window.py:254-255` 把 v1 `machine-memory-claude` 加进 grid | 与 v2 "删除全局 memory seat" 矛盾, 应该不加 |

**统一修复策略**:

1. 把 install.sh 的 `workers_payload()` + `memories_payload()` 逻辑**下沉到 Python**:
   - 新增 `agent_admin_window.build_workers_payload(project)` (planner main + N-1 workers grid, recipe 含 PRIMARY_SEAT_ID-aware 跳过 primary seat)
   - 新增 `agent_admin_window.build_memories_payload()` (扫所有 `<project>-memory` tmux session 排 grid_for_n)
   - 删除 `build_grid_payload()` 里的 v1 行为 OR 加 `template_kind` 参数分支

2. 改 `open_grid_window(project)` 入口:
   - 读 project 的 template_name (从 `~/.agents/projects/<project>/project.toml`)
   - clawseat-minimal → 调 `build_workers_payload + ensure_memories_pane` (v2 双窗)
   - clawseat-{default,engineering,creative} → 保留 `build_grid_payload` (v1 单窗)

3. 新增 `agent_admin_window.ensure_memories_pane(project)` 协议:
   - 检测 `clawseat-memories` 窗口存在? 不存在则创建带本项目 1 pane
   - 已存在但本项目 pane 不在? append pane (split or new tab 看 #4 决议)
   - 已存在且 pane 已在? no-op

4. `recover-grid.sh` 不需要改 (调 open-grid 自动走对路径)

5. install.sh main() clawseat-minimal 分支可以改用 Python helper (代码复用)

**追加修复**:
- 删除 `agent_admin_window.py:254-255` 把 machine-memory-claude 加进 grid 的代码 (v2 没这个)

**Owner**: builder-codex (实施) + planner-claude (review API 设计)

**关联**:
- 跟 #4 (memories tabs) 一起做, ensure_memories_pane 实现要支持 tabs 模式
- 跟 #11 (reseed-pane AppleScript) 不冲突, AppleScript 用法分开

**验收**:
- `bash scripts/recover-grid.sh install` 后: clawseat-install 窗口**不存在**; install-memory **只 attach 一次** (在 clawseat-memories); clawseat-install-workers 3-pane (planner + builder + designer)
- `agent_admin window open-grid testbed` 在新项目上同样产出双窗
- v1 模板 (engineering/default) 仍能正常 open-grid 单窗

---

### #14 wait-for-seat.sh TMUX 环境变量继承导致 switch-client fallback — 🟠 HIGH

**症状**: designer (或任何 worker) seat session 死掉后，对应 iTerm pane 自动 attach 到 `install-memory` TUI；operator 在那个 pane 的键入进入 memory 输入框。

**根因 (2026-04-26 03:35 install-memory 调研确认)**:
1. install.sh 在 install-memory tmux session 里运行，spawn workers 窗口时 iTerm 继承了 `TMUX` 环境变量（实测 designer pane tty124 里 `TMUX=/private/tmp/tmux-501/default,29587,162`）
2. wait-for-seat.sh line 207 跑 `tmux attach -t "=install-designer-gemini"`
3. tmux 检测到 `TMUX` 已设定 → 把 `attach` 解读为 `switch-client`，而非新建独立 client
4. 当 designer session 死亡 → tmux 自动把该 client 切回"上一个 session"（install-memory）
5. pane 显示 install-memory TUI，operator 键入进入 memory 输入框

**修复**: `wait-for-seat.sh` line 207，在 `tmux attach` 前清除 `TMUX`：
```bash
# 修复前
if tmux attach -t "=$TARGET_SESSION"; then
# 修复后
if env -u TMUX tmux attach -t "=$TARGET_SESSION"; then
```

**Owner**: builder-codex（1 行 fix）
**批次**: 批次 1 补丁（HIGH，与 Package B #2 同批或 micro-PR）

---

### #15 v1→v2 词汇漂移大批量清扫 — 🟠 HIGH

**症状**: v1 vocab 在 60+ 文件里残留，导致：
- skill 自我描述跟 v2 实际行为脱节（如 ancestor SKILL.md:229 说"默认六宫格 Row1-Col1=ancestor"）
- planner SKILL.md 列死 reviewer/qa 可派 seat（v2 minimal 没有这俩）
- preflight + skill_registry + profile_validator 硬编码 5-worker
- README.md 顶层声明 "6 seat roster"

**根因**: v2 RFC §1 §2 vocab（始祖=memory seat / workers+memories 双窗 / template-driven roster）只在新写的代码/文档对齐，老文件没批量同步。

**完整审计**: 见 [docs/rfc/V2-VOCAB-DRIFT-AUDIT.md](V2-VOCAB-DRIFT-AUDIT.md)，6 类分类 + 文件级清单 + 清扫策略。

**修复**: 分 3 个子批次实施
- **#15.a (批次 2)**: ancestor → memory seat id 重命名 + skill rename + brief 自称统一 + planner SKILL roster 解耦（不再列死 reviewer/qa）
- **#15.b (批次 3)**: README + ARCHITECTURE + INSTALL.md + ITERM_TMUX_REFERENCE.md + 各 skill 的"六宫格"段全删
- **#15.c (M4)**: 全局 machine-memory-claude 删除 + PROJECT_BINDING.toml 废弃确认

**Owner**: builder-codex 实施 + planner-claude review + memory 做 vocab 词典 + 验收
**批次**: 批次 2 (#15.a) / 批次 3 (#15.b) / M4 (#15.c)

**验收**:
- `grep -r "ancestor" core/ scripts/` 只出现在：兼容性 alias、migration 工具、CHANGELOG/RFC/handoff
- `grep -r "六宫格\|six-pane" docs/ core/skills/` 返回 0 行
- `grep -r "machine-memory-claude" core/ scripts/` 每处都有 `# v1 LEGACY (M4 remove)` 注释

---

### #16 memory 汇报协议缺失 — 🟠 HIGH

**症状**: operator 实证 (2026-04-26 03:50) memory chat 是 flowing transcript，混着工具调用块、internal thinking、长 sed、receipt JSON；要滚 80+ 行才知道当前状态。

**根因**: memory 没有显式的汇报协议；现有 `clawseat-ancestor` skill 覆盖 Phase-A bootstrap，但 Phase-B（持续运营）的 reporting / dispatch / backlog ops 没规范化。

**修复**: 落地 [clawseat-memory-reporting skill](../../core/skills/clawseat-memory-reporting/SKILL.md) v1（已写）:
- L1 STATUS.md 持久状态（schema 见 [references/status-md-schema.md](../../core/skills/clawseat-memory-reporting/references/status-md-schema.md)）
- L2 chat 尾块 ≤ 5 行结构化
- L3 backlog detail 文件归属 + issue 模板
- L4 dispatch 1 行收据

**派工内容**:
- **memory 立即生效**: 自我规训按本协议汇报（不需 install team 介入）
- **批次 2 派 builder-codex**: 改 dispatch_task.py / agent_admin 自动 append STATUS.md dispatch log，避免 memory 手动维护出错
- **批次 2 派 planner-claude**: 把现存 `~/.agents/tasks/install/STATUS.md` 迁移到本 schema

**Owner**: memory（自我规训立即） + builder-codex（自动化）+ planner-claude（migration）
**批次**: 立即（memory 自律） / 批次 2（自动化 + migration）

**验收**:
- operator `cat ~/.agents/tasks/install/STATUS.md` ≤ 30s 知道当前状态
- memory chat 任意一次回复尾块完整
- 新 issue 发现后 ≤ 5min 出现在 backlog

---

### #17 install.sh Step 9.5 auto-send 不可靠 — 改 confirm-then-dispatch UX — 🟠 HIGH

**症状（2026-04-26 04:36 arena 实证）**:
- arena 安装期间 `auto_send_phase_a_kickoff` 卡 2:34，max_polls 走完都没成功 paste
- 根因可能：arena-memory 用 host oauth 复用 host login 直接 ready，不经过 OAuth 弹窗→关闭流程；send-and-verify 的 ready 检测画面不匹配
- arena-memory pane 长时间停在 Claude Code start screen（"Welcome back Yu!" + 空 ❯）
- 等 max_polls 到 fallback 到 banner 也得 3min，UX 差

**operator 提案（2026-04-26 04:38）**:
> 移除 auto-send 的逻辑，等用户确认项目-memory 就绪；由负责安装的 agent（install-memory）发送同时告诉用户如果失败可以手动复制粘贴 prompt

**修复设计**:
1. 删除 install.sh `auto_send_phase_a_kickoff()` + Step 9.5 整段
2. 改成：install.sh 跑完 Step 9（focus pane）后**直接退出**，把 kickoff prompt 写到 `~/.agents/tasks/<project>/patrol/handoffs/ancestor-kickoff.txt`
3. install.sh 末尾 banner 给 operator 3 个明确选项:
   ```
   ✔ Install complete. <project>-memory pane is ready.
   To start Phase-A, choose one:
     A) Existing install-memory will dispatch kickoff to <project>-memory:
        bash <path>/send-and-verify.sh --project <project> <project>-memory \
          "$(cat ~/.agents/tasks/<project>/patrol/handoffs/ancestor-kickoff.txt)"
     B) Manual paste — open <project>-memory pane, copy the prompt from:
        cat ~/.agents/tasks/<project>/patrol/handoffs/ancestor-kickoff.txt
        and paste into the Claude Code prompt
     C) install-memory dispatches automatically:
        say "dispatch arena kickoff" to install-memory in chat
   ```
4. 临时手动验证（arena 已用此模式）:
   ```bash
   bash send-and-verify.sh --project arena arena-memory "<kickoff text>"
   ```

**Owner**: builder-codex（删 auto_send + 改 banner） + memory（更新 brief 让新 memory 知道自己是被外部 dispatch 启动的）
**批次**: batch 2 后续（Package E 可顺手做，operator 拍）

**验收**:
- 新项目 install 完不再有 9.5 卡死 → install.sh 退出 ≤ 60s
- operator 看到清晰的 3 选项 banner
- 选项 A 通过 send-and-verify 一行即发
- 选项 B 真的能 cat 出可贴的纯文本 prompt（无 ANSI / 编码问题）

**关联**:
- 这个修法**取代** #2（auto_send 72s→180s 不再相关，整段删了）— #2 可标 superseded by #17
- 跟 #1 (brief render dynamic) 配合：brief 里描述 spawn worker 的 phase 不变，只是触发方式变 user-initiated

---

### #18 (预留新 issue 编号)

---

## 修复批次规划

### 批次 0（ancestor 立刻自修, 不等 install team）— 🔴 BLOCKER

- **#10** workers_payload planner pane 错用 tmux attach → 改 wait-for-seat（ancestor 自己 fix, 是新引入 bug）

### 批次 1（4 seat 齐后立刻派）— 🟠 HIGH

- #1 brief 模板动态化
- #2 auto-send 窗口扩展
- #4 memories 窗口 tabs 改造
- #5 brief session check 修复
- #11 reseed-pane iterm2 API send_text 失效（改 AppleScript 或加 activate）
- #12 recover-grid.sh + 辅助脚本 PRIMARY_SEAT_ID 重构漏改
- #13 agent_admin window open-grid 仍用 v1 单窗 (operator 实证: recover-grid.sh 跑出 v1 拓扑)

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

### 2026-04-26 02:25 — install-memory 报 3 个根因（在 phase-a-decisions 之前先告诉 operator）

1. iTerm clawseat-install-workers 创建时 planner pane 没启动 wait-for-seat（builder/designer 启动了，planner 漏了）→ 已建为 #10 BLOCKER
2. agent_admin window reseed-pane 走 iterm2 API 路径有 bug：返回成功但 send_text 序列没真正写入空闲 zsh shell。直接用 iTerm AppleScript write text 才生效 → 已建为 #11 HIGH
3. 这个 bug + 所有 recover-grid.sh / grid-recovery 路径硬编码 install-ancestor 是 v2 minimal 的两个已知 stale 点 → 已建为 #12 HIGH

### 2026-04-26 03:00 — operator 让 ancestor 跑 recover-grid.sh install 救回 workers 视图

**实证发现**: recover-grid.sh + agent_admin window open-grid 走 v1 grid_payload 单窗口路径，与 install.sh main() 已实现的 v2 双窗口拓扑不一致。结果 install-memory 被 attach 了 2 次（v1 风格 clawseat-install + v2 风格 clawseat-memories）→ 已建为 #13 HIGH

---
