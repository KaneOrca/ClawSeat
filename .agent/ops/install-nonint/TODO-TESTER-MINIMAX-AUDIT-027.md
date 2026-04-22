# TODO — AUDIT-027 (coding/ClawSeat 源码调研)

```
task_id: AUDIT-027
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/coding/ClawSeat (main branch)
priority: P0
subagent-mode: REQUIRED — spawn 3 parallel subagents (A/B/C)
do-not-modify: read-only audit only
```

## Context

我们正在重建 ClawSeat 安装流程，需要了解 main branch 当前状态。
重点调研三个架构问题，这些问题直接影响下一步设计决策。

---

## Subagent A — Memory UserPromptSubmit hook 部署状态

调研路径：`/Users/ywf/coding/ClawSeat`

1. **Hook 配置文件在哪？**
   - 查找所有 hook 相关文件：
     ```bash
     grep -rn "UserPromptSubmit\|user_prompt_submit\|hook" /Users/ywf/coding/ClawSeat \
       --include="*.toml" --include="*.json" --include="*.sh" --include="*.py" \
       --include="*.md" -l
     ```
   - 特别检查 `~/.agents/engineers/memory/` 或 `core/templates/` 下是否有 engineer.toml 含 hook 配置

2. **hook 实际注入了什么？**
   - memory-oracle/SKILL.md 说注入 `machine/` 5 个文件 + `dev_env.json`
   - 找到实际执行注入的脚本/配置，读取其内容
   - `machine/` 5 个文件（credentials/network/openclaw/github/current_context）是否已被 `scan_environment.py` 生成过？检查 `~/.agents/memory/machine/` 是否存在

3. **[CLEAR-REQUESTED] watcher 是否实现？**
   - 查找监听 `[CLEAR-REQUESTED]` 标记的脚本：
     ```bash
     grep -rn "CLEAR-REQUESTED\|clear.requested\|patrol.*clear\|stop.*hook" \
       /Users/ywf/coding/ClawSeat --include="*.sh" --include="*.py" --include="*.md"
     ```
   - 是否有 Stop hook / tmux watcher 在 memory 输出后自动触发 `/clear`？
   - 如果没有：手动流程是什么？

报告：
- hook 配置文件路径 + 内容摘要
- machine/ 目录是否存在 + 文件列表
- [CLEAR-REQUESTED] watcher 实现状态：已实现 / 未实现 / 部分实现

---

## Subagent B — Planner SKILL.md 与多子 agent 规则

调研路径：`/Users/ywf/coding/ClawSeat`

1. **Planner 有没有专属 SKILL.md？**
   ```bash
   find /Users/ywf/coding/ClawSeat -name "SKILL.md" | xargs grep -l "planner\|dispatcher" 2>/dev/null
   find /Users/ywf/coding/ClawSeat -path "*/planner*" -name "*.md" 2>/dev/null
   ```

2. **现有 SKILL.md 中有无多子 agent 规则？**
   ```bash
   grep -rn "subagent\|sub-agent\|多子\|parallel\|fan.out\|并发\|concurrent" \
     /Users/ywf/coding/ClawSeat/core/skills/ --include="*.md"
   ```

3. **gstack-harness dispatch playbook 现状**
   - 读 `core/skills/gstack-harness/SKILL.md` 的 Design rules 部分
   - 有没有 references/ 目录（`ls core/skills/gstack-harness/references/ 2>/dev/null`）
   - 如果没有，references 是否在别处

报告：
- planner 专属 SKILL.md 是否存在 + 路径
- 多子 agent 规则：完全缺失 / 部分存在（引用哪里）
- 推荐的补全位置（写进哪个 SKILL.md 最合适）

---

## Subagent C — main vs experimental 架构差异速览

对比两个 branch 的关键文件差异（只读）：

```bash
# 在 main worktree 执行
cd /Users/ywf/coding/ClawSeat

# 1. 两个 branch 的 docs/INSTALL.md 差异
git diff main..experimental -- docs/INSTALL.md | head -80

# 2. 关键文件在 experimental 有但 main 没有（或反之）
git diff --name-status main..experimental | head -40

# 3. 各自的最新 3 个 commit
git log main --oneline -5
git log experimental --oneline -5
```

报告：
- INSTALL.md 两版本的核心差异（不超过 10 行总结）
- experimental 新增 / 删除了哪些关键文件（不列琐碎文件）
- 两个 branch 的分叉点

---

## Deliverable

Write `DELIVERY-AUDIT-027.md` in `/Users/ywf/ClawSeat/.agent/ops/install-nonint/`:

```
task_id: AUDIT-027
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <one line>

## Subagent A — Memory hook 部署状态
## Subagent B — Planner 多子 agent 规则现状
## Subagent C — main vs experimental 差异
## 架构建议（各子 agent 发现的 gap + 推荐修复位置）
```

Notify planner: "DELIVERY-AUDIT-027 ready".
