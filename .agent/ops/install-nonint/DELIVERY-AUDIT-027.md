task_id: AUDIT-027
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 3 gaps found — memory hook is dead pipe, planner has no dedicated SKILL.md, experimental branch has completed legacy sweep.

## Subagent A — Memory UserPromptSubmit hook 部署状态

### Hook configuration files found

1. **`~/.claude/settings.json`** (lines 66-76) — `UserPromptSubmit` hook registered:
   ```json
   "UserPromptSubmit": [{
     "matcher": "",
     "hooks": [{
       "type": "command",
       "command": "node \"/Users/ywf/.pixel-agents/hooks/claude-hook.js\"",
       "timeout": 5
     }]
   }]
   ```

2. **`/Users/ywf/.pixel-agents/hooks/claude-hook.js`** — The hook script. Reads `~/.pixel-agents/server.json` for port/token, POSTs to `http://127.0.0.1:<port>/api/hooks/claude`.

### What the hook actually injects

**Nothing — it is a dead pipe.**

- The hook requires `~/.pixel-agents/server.json` to know which port/token to use.
- `server.json` **does not exist** — the pixel-agents backend server is not running.
- The hook silently fails on every prompt submit.
- SKILL.md line 17 ("`UserPromptSubmit` hook has injected `machine/` 5 files + `dev_env.json`") is **aspirational** — it describes what memory-oracle's overall data pipeline produces, not what the actual UserPromptSubmit hook does. The `machine/` 5 files are produced by `scan_environment.py` run manually/externally, not by this hook.

The 5 `machine/` files produced by a full `scan_environment.py` run:
- `credentials.json` — API keys, OAuth evidence
- `network.json` — proxy settings, endpoints
- `openclaw.json` — OpenClaw installation state
- `github.json` — git/GitHub/gh CLI identity
- `current_context.json` — current project pointer + last_refresh_ts

### `~/.agents/memory/machine/` status

**NOT FOUND** — directory does not exist on this machine. No scan has been run or results not persisted.

### [CLEAR-REQUESTED] watcher 实现状态

**Not implemented.**

- SKILL.md line 46 states: `[CLEAR-REQUESTED]` is handled by "external orchestrator (tmux watcher / Stop hook / operator key-in)" → triggers `tmux send-keys /clear`.
- The `Stop` hook in `settings.json` points to the same non-functional pixel-agents server.
- No tmux watcher script found in the codebase that monitors for `[CLEAR-REQUESTED]` and sends `/clear`.
- `test_memory_target_guard.py` line 3 asserts "Memory is a synchronous oracle — its Stop hook runs `/clear` after every turn" — this is a **design intent test, not a live implementation**.
- **Manual flow required**: operator must manually type `/clear` after memory output, since model-output `/clear` is not executed by Claude Code (slash commands only fire from user key input per SKILL.md line 48).

---

## Subagent B — Planner 多子 agent 规则现状

### Planner 专属 SKILL.md

**不存在。** 整个代码库中没有 `core/skills/planner/` 目录，也没有名为 planner 的 SKILL.md。Planner 角色没有专属 skill 文件。

### 多子 agent 规则现状

**部分存在，但分散在多处，非集中定义：**

1. **`core/skills/clawseat-install/SKILL.md`** (lines 78-87) — 提到 Planner 的 fan-out 职责：
   - "Planner fans out review lanes across reviewer + qa concurrently."
   - "Builder spawns focused subagents per file/module when the diff..."
2. **`core/skills/gstack-harness/SKILL.md`** (Design rules, lines 122-160) — 定义了 seat-to-seat dispatch/handoff 协议，但这是 **harness 编排层**规则，不是 Planner 专属的多子 agent 调度规则。
3. **`core/skills/clawseat-koder-frontstage/SKILL.md`** (lines 177-179) — 提到并行启动 `reviewer-1`。
4. 零星提及 parallel/fan-out 概念：`cs/SKILL.md`, `clawseat/SKILL.md`, `clawseat-ancestor/SKILL.md`。

**结论**：Planner 的多子 agent 调度规则（fan-out 到 reviewer/qa 的并发策略、子 agent 生命周期管理）没有集中定义，零散分布在 installer 和 harness skill 中。

### 推荐补全位置

**`core/skills/clawseat-install/SKILL.md`** 应作为 Planner 多子 agent 规则的承载文件：
- 该文件已明确提及 "Planner fans out review lanes" (line 82)
- Planner 属于 ClawSeat 安装/交付流程中的编排角色，与 `clawseat-install` 的设计目标高度吻合
- `gstack-harness/SKILL.md` 的 Design rules 应保持为 harness 运行时规则，不应承担业务编排逻辑

---

## Subagent C — main vs experimental 差异

### INSTALL.md 两版本核心差异

**两版本 INSTALL.md 内容完全一致，无差异。**

### experimental 新增 / 删除的关键文件

**删除 (experimental 已执行 legacy 清理 sweep)：**
- `core/skills/agent-monitor/SKILL.md` 及全部 script 子文件
- `core/skills/clawseat-koder-frontstage/SKILL.md` 及 agents 配置
- `design/followups-after-m1.md`, `design/memory-seat-v3/M2-SPEC.md`, `design/memory-seat-v3/SPEC.md`, `design/phase-7-retire.md`
- `docs/PACKAGING.md`, `docs/TEAM-INSTANTIATION-PLAN.md`, `docs/design/ancestor-responsibilities.md`
- `examples/arena-pretext-ui/` (整个目录)
- `examples/starter/profiles/legacy/` (整个目录)

**修改：**
- `README.md`, `manifest.toml`, `docs/ARCHITECTURE.md`
- `core/skill_registry.toml`, `core/skills/gstack-harness/SKILL.md`
- `core/templates/ancestor-engineer.toml`, `core/templates/gstack-harness/template.toml`
- `scripts/clean-slate.sh`, `tests/` 下多个测试文件

### 两个 branch 的分叉点

Commit `5d26fee` ("fix(install): align v0.5 runtime contract") — 之后 experimental 独有 commit `dfadb69` 执行了一次 legacy 清理 sweep。

### 各 branch 最新 commit

- **main**: `5d26fee` fix(install): align v0.5 runtime contract
- **experimental**: `dfadb69` chore(experimental): sweep legacy candidates per INST-RESEARCH-022

---

## 架构建议（各子 agent 发现的 gap + 推荐修复位置）

| Gap | Severity | Recommended fix location |
|-----|----------|------------------------|
| Memory UserPromptSubmit hook is dead pipe (`server.json` missing, pixel-agents not running) | **High** | Either start pixel-agents server, or replace hook with a simpler inline script that runs `scan_environment.py` directly |
| [CLEAR-REQUESTED] watcher not implemented — manual `/clear` required | **Medium** | Add a tmux watcher script in `core/shell-scripts/` that monitors for `[CLEAR-REQUESTED]` marker and fires `tmux send-keys /clear`; register as a background process |
| Planner has no dedicated SKILL.md — multi-subagent rules scattered | **Medium** | Add a `core/skills/planner/SKILL.md` or consolidate into `clawseat-install/SKILL.md` lines 78-87 as a formal "Planner dispatch protocol" section |
| `~/.agents/memory/machine/` never populated | **Low** | This is a runtime data directory, not a code gap — will be populated on first successful memory-oracle run; not a blocker |
