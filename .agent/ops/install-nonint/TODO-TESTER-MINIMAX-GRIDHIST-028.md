# TODO — GRIDHIST-028 (找回可交互六宫格实现)

```
task_id: GRIDHIST-028
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/coding/ClawSeat (main worktree, all branches available)
priority: P0
subagent-mode: REQUIRED — spawn 3 parallel subagents (A/B/C)
do-not-modify: read-only; only 报告 + git show 摘录
```

## Context (必读)

当前 `scripts/launch-grid.sh` 配合 `templates/clawseat-monitor.yaml` 拉起的六宫格**不可交互**：
- monitor pane 里 nested `tmux attach -t clawseat-<seat>` 需要双 prefix 才能切 pane
- 用户反馈"完全不对"

**用户明确说**："我之前已实现了直接拉起可交互的六宫格"——所以某个 claude 分支里有一份能用的实现。

已知线索（planner 初查）：
- `2a4ec71 feat(v0.4): Phase 2 — TUI launcher + ancestor skill + chat-id routing` ← 可能含 TUI 六宫格
- `f846625 chore(install): drop v0.4 TUI + legacy bootstrap surface` ← 这个 commit 把 TUI 拆掉了
- `e229f0a fix: 6 iTerm/tmux script issues from audit` ← 六宫格审计修了 6 处
- `3b84f26 feat(tmux): two-layer tmux knowledge injection for all seats`
- 搜关键词 `6-pane / 六宫格 / monitor / tiled / iterm / tmuxp` 都可能命中

claude/* 本地分支列表（部分）：
- claude/audit-p0-clean, claude/audit-p1-cli-config, claude/audit-p1b-bugs
- claude/audit-p2-hardening, claude/audit-p2-polish, claude/audit-p2-smoke-coverage
- claude/b1-install-auth-choice, claude/c8~c16 系列
- claude/p1-layered-engine, claude/r6-k6-fix, claude/fix-ci-smoke-gating

---

## Subagent A — v0.4 TUI 源码考古

查 commit `2a4ec71` 和 `f846625` 之间：

```bash
cd /Users/ywf/coding/ClawSeat

# 看 2a4ec71 加了哪些文件（就是 v0.4 TUI 实现）
git show --stat 2a4ec71 2>&1 | head -60

# 看 f846625 删了哪些（就是被移除的 TUI 文件）
git show --stat f846625 2>&1 | head -60

# 关键：把 TUI 启动器文件的完整内容从 2a4ec71 拉出来
# （先用 --stat 看文件名，再 git show <commit>:<path>）
```

重点要找到的东西：
1. **TUI launcher 脚本文件**（可能在 `scripts/` 或 `core/scripts/` 下，名字含 tui/launcher/monitor）
2. 它拉起 6 个 seat 的具体方式（split-window? tmuxp? iTerm osascript?）
3. 它是怎么让每个 pane 变成"可直接在 monitor 里打字到对应 seat"的

把核心的 10-30 行 tmux/osascript 命令段直接摘录到报告里。

---

## Subagent B — 跨 branch 扫描：所有"可交互六宫格"候选

```bash
cd /Users/ywf/coding/ClawSeat

# 搜所有 branch 里含 tmux split-window + 6 的脚本
git grep -lnE "split-window|iTerm|tmuxp|tiled" $(git branch -a --format='%(refname:short)' | grep -v HEAD) \
  -- '*.sh' '*.py' '*.yaml' '*.yml' '*.applescript' 2>&1 | sort -u | head -50

# 搜 monitor/grid/六宫格 关键词
git grep -lnE "monitor.*pane|6.pane|six.pane|grid.*layout|六宫格" $(git branch -a --format='%(refname:short)' | grep -v HEAD) 2>&1 | head -30

# 各 claude/* 分支最新 commit 扫一眼
for b in $(git branch | grep 'claude/' | tr -d '+* '); do
  echo "=== $b ==="
  git log --oneline -3 "$b" 2>/dev/null
done
```

找出 2-3 个最可能包含"可交互六宫格"实现的 branch，每个给出：
- branch 名
- 关键文件路径
- 为什么它看起来是用户说的那个版本（证据）

---

## Subagent C — 当前实现对比分析

对比 `scripts/launch-grid.sh` + `templates/clawseat-monitor.yaml`（experimental 已提交/未提交），
分析为什么它不可交互：

1. monitor session 的 layout 是 `tiled` + 每 pane `exec tmux attach -t clawseat-<seat>`，
   这种 nested tmux attach 在实际使用时有哪些交互障碍？（prefix 冲突、scrollback 丢失、mouse 等）
2. v0.4 TUI 的做法（subagent A 找出来的）怎么解决这些障碍？
   - 是用 iTerm native panes 而不是 tmux？
   - 还是 tmux split-window 直接把 seat 进程放进 pane（不 nested）？
   - 还是用 tmux `link-window` / `swap-pane`？
3. 推荐迁移路径（不写代码，只给架构建议）

---

## Deliverable

写 `DELIVERY-GRIDHIST-028.md` to `/Users/ywf/ClawSeat/.agent/ops/install-nonint/`:

```
task_id: GRIDHIST-028
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话：可交互实现在 <branch>/<commit>，核心是用 <机制>>

## Subagent A — v0.4 TUI 源码（含 10-30 行关键代码摘录）
## Subagent B — 候选 branch 列表（2-3 个，每个给证据）
## Subagent C — 当前实现 vs 历史实现对比 + 迁移建议
## 最终推荐：哪个 commit/branch 直接 cherry-pick 最省事
```

**完成后**通知 planner: "DELIVERY-GRIDHIST-028 ready"。
