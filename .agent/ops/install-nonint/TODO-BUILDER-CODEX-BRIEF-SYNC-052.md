# TODO — BRIEF-SYNC-052 (ancestor brief drift 检测 + 文档化)

```
task_id: BRIEF-SYNC-052
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P2
subagent-mode: OPTIONAL (单 agent)
scope: 解决运行中 ancestor 不感知 brief template 更新的 drift 问题（detect + alert + doc，不 hot-reload）
queued: 在 ARK-050 + MEMORY-IO-051 之后
```

## Context

smoke01-ancestor 暴露 brief 版本锁定问题：
- smoke01 启动于 2026-04-23 01:09:27
- SPAWN-049 commit `f304118` 在 01:58:10（晚于 smoke01）
- 运行中 ancestor 读的是启动时缓存在 context 里的旧版 brief，不感知 template 后续更新
- 结果：smoke01-ancestor 在 B5 跑 pre-SPAWN-049 简化版（只问 "chat_id or skip"），不是 SPAWN-049 的 5 步 UX（自读 agents → 菜单 → 拉群 → bind）

**根本原因**：Claude Code 的 system prompt / CLAWSEAT_ANCESTOR_BRIEF 都是启动时 load，运行中无 hot-reload 机制。这是 Claude Code 固有架构限制，**不能**通过"让 ancestor re-read brief"真解决（即便 re-read，context 里旧版还在，LLM 可能凭旧记忆）。

**选中方案**：C (mtime detect + CLI warn) + E (文档化)。

不选 A (brief 瘦身)、B (每步 cat)、D (runbook 分层)——前两者治标不治本 / 过度消耗 token，D 是大 refactor 留给 v0.8。

## 修复

### P1 · SKILL.md §2 加每个 B 步开头的 brief mtime check

`core/skills/clawseat-ancestor/SKILL.md` §2 "启动序列 (Phase A)" 段在 "严格按下表执行" 表格之前加：

```markdown
**Brief drift 自检（每个 B 步开始前）**：

每个 B 子步开始时，先跑一次：
```bash
bash ${CLAWSEAT_ROOT}/scripts/ancestor-brief-mtime-check.sh
```

如输出 `BRIEF_DRIFT_DETECTED` → 向 operator CLI 输出明显警告：
```
⚠ BRIEF_DRIFT_DETECTED
  你启动时 load 的 brief 是 <ancestor_start_iso>
  brief 文件已在 <brief_mtime_iso> 更新
  我脑子里是旧版 Phase-A checklist，可能漏 SPAWN-049/MEMORY-IO-051 等 post-<start> 的改动
  建议：operator 决定是否 `tmux kill-session -t ${PROJECT_NAME}-ancestor` 后 restart，用新 brief 继续
  或：继续按当前（旧）brief 走（不保证和最新 canonical flow 一致）
```

然后等 operator 决定继续 / restart，不自动 halt。
```

### P2 · 新建 `scripts/ancestor-brief-mtime-check.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

BRIEF="${CLAWSEAT_ANCESTOR_BRIEF:-}"
if [[ -z "$BRIEF" || ! -f "$BRIEF" ]]; then
  # brief 缺失是另一个问题，不归本脚本
  exit 0
fi

# 读 ancestor 启动时 timestamp（launcher 起 seat 时写一个 file）
# 或 fallback 用 tmux session 的 #{session_created}
SESSION_NAME="${CLAWSEAT_ANCESTOR_SESSION:-$(basename "${TMUX_PANE:-}" | cut -d. -f1)}"
ANCESTOR_STARTED=""
if [[ -n "$SESSION_NAME" ]] && command -v tmux >/dev/null 2>&1; then
  ANCESTOR_STARTED="$(tmux display-message -p -t "=$SESSION_NAME" '#{session_created}' 2>/dev/null || echo 0)"
fi

BRIEF_MTIME="$(stat -f %m "$BRIEF" 2>/dev/null || stat -c %Y "$BRIEF" 2>/dev/null || echo 0)"

if [[ -n "$ANCESTOR_STARTED" && "$ANCESTOR_STARTED" != "0" && "$BRIEF_MTIME" -gt "$ANCESTOR_STARTED" ]]; then
  printf 'BRIEF_DRIFT_DETECTED\n'
  printf '  ancestor_started_unix=%s\n' "$ANCESTOR_STARTED"
  printf '  brief_mtime_unix=%s\n' "$BRIEF_MTIME"
  printf '  brief_path=%s\n' "$BRIEF"
  exit 1  # non-zero → ancestor 看到 return code 非零 → SKILL.md 逻辑触发 CLI warn
fi

exit 0
```

放 `scripts/ancestor-brief-mtime-check.sh`，chmod 755。

**注意**：
- `TMUX_PANE` 是 tmux 自动注入的 env var
- `tmux display-message #{session_created}` 返回 session 创建的 unix timestamp
- macOS 用 `stat -f %m`，Linux 用 `stat -c %Y`，两个都 fallback

### P3 · OPERATOR-START-HERE.md 加 "brief drift" 段

`scripts/install.sh` 的 `OPERATOR-START-HERE.md` 模板尾部加：

```markdown
## 如果 ancestor 报 BRIEF_DRIFT_DETECTED

已启动的 ancestor 读到的是启动时 load 的 brief 旧版，不会感知后续 install.sh / brief template 的更新。如果 Phase-A 跑到一半发现 brief 改了：

**方案 A（推荐，最安全）**：
  tmux kill-session -t ${PROJECT_NAME}-ancestor
  bash ${CLAWSEAT_ROOT}/core/launchers/agent-launcher.sh --headless --tool claude --auth custom --dir ${CLAWSEAT_ROOT} --session ${PROJECT_NAME}-ancestor ...
  # 重新进 ancestor pane，它会 re-load 新 brief

**方案 B（轻量 override）**：
  直接在 ancestor CLI 里告诉它："brief 已改，请 cat $CLAWSEAT_ANCESTOR_BRIEF 重新读一遍，按新内容继续"
  注意 ancestor 可能仍凭旧 context 里记忆做决策，不如 A 可靠

**方案 C（忽略）**：
  接受 ancestor 继续走旧 brief，结果可能和当前 canonical flow 不一致
```

### P4 · SKILL.md §2 文档化 brief immutability

SKILL.md §2 加一段 "Brief immutability" 说明：

```markdown
### Brief immutability（架构约束）

你启动时 load 的 brief 和 SKILL.md 都是 Claude Code 启动时注入的 system context，**运行中无 hot-reload**。如果 operator 改了 brief template 或 SKILL.md 源文件，你脑子里是旧版。

处理方式：
- 每个 B 步开始前跑 brief mtime check（见上）
- 检测到 drift → CLI warn operator
- operator 决定 restart（最可靠）或 override prompt 让你继续（凭剩余上下文尽力）
- 不要自己尝试"re-read brief to refresh memory" —— 即便你真 re-read，LLM context 里旧内容已占位置，LLM 很难完全忽略
```

## 测试

`tests/test_ancestor_brief_drift_check.py`:

1. 跑 `ancestor-brief-mtime-check.sh`：brief 存在且 mtime > ancestor start → exit 1 + 输出 `BRIEF_DRIFT_DETECTED`
2. brief 存在且 mtime <= ancestor start → exit 0
3. brief 不存在 → exit 0（不归本脚本）
4. TMUX_PANE 未设置 → exit 0（降级不报错）

`tests/test_ancestor_skill_brief_drift_rules.py`:

1. SKILL.md §2 含 "Brief drift 自检"
2. SKILL.md §2 含 "Brief immutability"
3. install.sh OPERATOR-START-HERE.md 模板含 "BRIEF_DRIFT_DETECTED" 处理段
4. grep `scripts/ancestor-brief-mtime-check.sh` 确认存在 + 可执行

## 约束

- 不改 brief template 结构（P3 / P4 只是在 SKILL.md 和 OPERATOR-START-HERE.md 加段）
- 不改 agent-launcher.sh / agent_admin 的启动流程
- mtime check 的失败（如 stat 不可用）降级为 exit 0，不阻塞 Phase-A
- ancestor 现有 B1-B7 流程不变，只是每步前加一次 mtime check

## Deliverable

`.agent/ops/install-nonint/DELIVERY-BRIEF-SYNC-052.md`:

```
task_id: BRIEF-SYNC-052
owner: builder-codex
target: planner

## 改动清单
- scripts/ancestor-brief-mtime-check.sh (新增)
- core/skills/clawseat-ancestor/SKILL.md (§2 加 drift check + immutability)
- scripts/install.sh (OPERATOR-START-HERE.md 模板加 drift 处理段)
- tests/test_ancestor_brief_drift_check.py (新增)
- tests/test_ancestor_skill_brief_drift_rules.py (新增)

## Verification
<bash + pytest 输出>

## Notes
- 不动 brief template / agent_admin / launcher
- 架构限制由 SKILL.md 文档化（Claude Code 无 system prompt hot-reload）
- 真正 hot-reload 的 runbook 分层方案留给 v0.8（BRIEF-SYNC-052 不做）
```

**不 commit**。
