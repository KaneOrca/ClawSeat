# TODO — ARCH-CLARITY-047 (Seat lifecycle entry points 文档化)

```
task_id: ARCH-CLARITY-047
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P1
queued: YES — 等 ISOLATION-046 落地（这次 docs 反映 post-046 的事实）
subagent-mode: OPTIONAL (单 agent 即可)
scope: 只改文档 + 加注释，不改代码逻辑
```

## Context

ClawSeat 现在有 4 个看似平行的"启 seat"入口（install.sh / agent-launcher.sh / agent_admin / init_*.py），任何新手 agent（含 minimax）读 docs 选不出唯一路径。

planner 已经定方案 P（Pyramid 分层）：
```
顶层（user/agent 入口）：scripts/install.sh + scripts/apply-koder-overlay.sh
中层（CLI 操作）：agent_admin session/project subcommands
底层（执行）：core/launchers/agent-launcher.sh —— INTERNAL，不直接用
```

ISOLATION-046 已经把 install.sh 改成走 agent-launcher（即把 (A) 拉进 Pyramid 顶层）。本任务把这个分层**写进文档**，让 minimax 看一眼就懂。

## 改动 1 — `docs/ARCHITECTURE.md` 新增章节

在 §3 Skill Layer 之后、§4 Adapter Layer 之前插入：

```markdown
## §3z — Seat lifecycle entry points (v0.7 Pyramid)

ClawSeat exposes **three layers** for seat lifecycle. Use the highest layer
that fits your scenario; never call a lower layer directly unless you have
read the ones above and confirmed they don't cover your case.

| Layer | Component | When to use | Don't use when |
|-------|-----------|-------------|---------------|
| **L1 — User-facing entry** | `scripts/install.sh` (bootstrap), `scripts/apply-koder-overlay.sh` (post-install Feishu reverse channel) | Operator wants to bootstrap a fresh project, or apply koder overlay after install | You only need to (re)start one seat — use L2 instead |
| **L2 — CLI operations** | `agent_admin session start-engineer`, `agent_admin project bootstrap`, `agent_admin project use`, `agent_admin project delete` | Restarting one seat, switching project context, killing a project group | Doing one-time install — use L1 |
| **L3 — Execution primitive** | `core/launchers/agent-launcher.sh` | **INTERNAL only**. Called by L1 / L2 when actually launching a seat process. Handles sandbox HOME, secrets file, runtime_dir under `~/.agent-runtime/identities/<tool>/<auth>/<id>/home/` | You're a user or agent — go through L1 / L2 |

### Sandbox HOME isolation contract

Every seat launched via L1 or L2 inherits a sandbox HOME at
`~/.agent-runtime/identities/<tool>/<auth>/<auth_mode>-<session_name>/home/`,
giving per-seat credential / config isolation. Direct `tmux new-session bash`
from a script bypasses this contract — never do it for a seat that runs
`claude` / `codex` / `gemini`.

### When to call which init_*.py

These are NOT user-facing entry points. They are called from L1 / L2 / Phase-A:

| Script | Called by | Purpose |
|--------|-----------|---------|
| `init_koder.py` | `apply-koder-overlay.sh` | Destructive overlay onto an OpenClaw agent workspace |
| `init_specialist.py` | (legacy v0.5 path) | Materialize a specialist seat workspace |
| `install_memory_hook.py` | `install.sh` Step 7.5 | Install Stop hook into memory's workspace |
| `install_planner_hook.py` | `ancestor` Phase-A B3.5 | Install Stop hook into planner's workspace |
```

## 改动 2 — `core/launchers/agent-launcher.sh` 顶部加 INTERNAL 注释

在 shebang 之后、第一段代码之前插入（替换或新增）：

```bash
# INTERNAL — do not call directly.
# This is the L3 execution primitive in the v0.7 Seat Lifecycle Pyramid:
#   L1 (user-facing): scripts/install.sh, scripts/apply-koder-overlay.sh
#   L2 (CLI ops):     agent_admin session start-engineer, agent_admin project ...
#   L3 (this file):   agent-launcher.sh — sandbox HOME + secrets + runtime_dir
# See docs/ARCHITECTURE.md §3z for the full contract.
# If you find yourself calling this script directly from a TODO or doc,
# reconsider — L1 or L2 should already cover your case.
```

## 改动 3 — `docs/INSTALL.md` 在 Overview 表格下新增一行说明

在 Overview 表格之后、§Broadcast model 之前插入：

```markdown
> **Why `install.sh` instead of `agent_admin` or `agent-launcher.sh` directly?**
> `install.sh` is the L1 user-facing entry for *fresh-machine bootstrap*
> (host deps + scan + provider pick + 6 sessions + memory window + brief render).
> For per-seat operations on an existing project, use `agent_admin session
> start-engineer`. For executing a single seat process with sandbox HOME,
> the system internally calls `agent-launcher.sh` (you don't). See
> [docs/ARCHITECTURE.md §3z](ARCHITECTURE.md) for the full layering.
```

## 改动 4 — `docs/CANONICAL-FLOW.md` 加一句

在 §1 Dispatch 之前的 Overview 段（如果存在）或 §1 顶部注释，加：

```markdown
> Seat lifecycle entry points are documented in
> [docs/ARCHITECTURE.md §3z](ARCHITECTURE.md). This file (CANONICAL-FLOW)
> describes the dispatch / completion / ACK protocol *between already-launched
> seats*; it does not describe how to launch them.
```

## 验证

- `markdownlint` 若可用就跑（不可用 NO_MARKDOWNLINT 即可）
- grep 验证：4 个改动文件都更新了
- 目视检查：链接 `[docs/ARCHITECTURE.md §3z]` 在 INSTALL.md 和 CANONICAL-FLOW.md 都跳转正确

## 约束

- **不改任何代码逻辑**
- 只动 4 个文件：`docs/ARCHITECTURE.md` / `docs/INSTALL.md` / `docs/CANONICAL-FLOW.md` / `core/launchers/agent-launcher.sh`（仅顶部注释）
- 注释和文档**对齐 ISOLATION-046 落地后的事实**——如 ISOLATION-046 改了 install.sh 的具体实现，这里的措辞要相应调整

## Deliverable

`DELIVERY-ARCH-CLARITY-047.md`：

```
task_id: ARCH-CLARITY-047
owner: builder-codex
target: planner

## 改动清单
- docs/ARCHITECTURE.md (新增 §3z, N 行)
- docs/INSTALL.md (Overview 后插入 N 行)
- docs/CANONICAL-FLOW.md (§1 前插入 N 行)
- core/launchers/agent-launcher.sh (顶部 INTERNAL 注释)

## Verification
<grep / 目视>

## Notes
<和 ISOLATION-046 措辞对齐如何处理>
```

**不 commit**。
