# TODO — LIVE-043 (端到端真链路安装测试 — co-driven)

```
task_id: LIVE-043
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
mode: CO-DRIVEN (你跑命令、监控、报告；用户做交互式选择)
absolute paths: /Users/ywf/ClawSeat (CLAWSEAT_ROOT), /Users/ywf/.agents/, /Users/ywf/.openclaw/
total timeout: 45 minutes
```

## 任务定位

你（minimax）是"笨用户"的替身。**只看 `/Users/ywf/ClawSeat/docs/INSTALL.md`**，按它端到端跑一遍 ClawSeat 安装 + Phase-A 配置。
- 项目名固定 `smoketest`（隔离于真 install 项目）
- 任何**选择题 / 决策点**：报告给 planner，等用户回复
- 任何**机械命令**：你自己跑
- 看到**任何报错**：立刻停下报告，**不要尝试修**

成功标准：`/Users/ywf/.agents/tasks/smoketest/STATUS.md` 出现 `phase=ready` 行。

---

## Phase 1 — Pre-cleanup（你自己跑，10 秒）

```bash
tmux kill-session -t machine-memory-claude 2>/dev/null || true
rm -rf /Users/ywf/.agents/workspaces/smoketest /Users/ywf/.agents/tasks/smoketest
echo "=== verify clean ==="
tmux has-session -t machine-memory-claude 2>/dev/null && echo "memory: STILL ALIVE (BAD)" || echo "memory: killed OK"
test -e /Users/ywf/.agents/workspaces/smoketest && echo "workspaces: STILL EXISTS (BAD)" || echo "workspaces: clean OK"
test -e /Users/ywf/.agents/tasks/smoketest && echo "tasks: STILL EXISTS (BAD)" || echo "tasks: clean OK"
```

报告 "Phase 1 clean" 后进入 Phase 2。

---

## Phase 2 — 跑 install.sh，监控 + 报告

```bash
# 启动 install.sh 在独立 tmux session 里（不要让它阻塞你的 shell）
tmux new-session -d -s install-runner -c /Users/ywf/ClawSeat \
  "bash scripts/install.sh --project smoketest 2>&1 | tee /tmp/install-runner.log; sleep 3600"

# 等 3 秒让它启动
sleep 3

# 然后**每隔 5 秒** capture-pane 一次，看输出，连续 capture 直到看到下面任一情况：
#   (a) "==> Step 9" 后跟 "ClawSeat install: 始祖 CC 已起" → install.sh 完成
#   (b) read prompt（如 "Detected ... [Y]/[c]"）→ 报告给用户等回答
#   (c) ERR_CODE: ... → 报错，停下
#   (d) 超过 90 秒没新输出 → 卡住，报告

# 推荐 capture 方式
tmux capture-pane -t install-runner -p
```

**遇到 prompt 时报告格式**：
```
[LIVE-043 Phase 2] install.sh 卡在 prompt: <精确文字>
请用户：
  tmux send-keys -t =install-runner "<答案>" Enter
（在你自己的 terminal 跑此命令，从这台机器的任意 shell）
我等 30 秒后再 capture-pane 看是否前进
```

**install.sh 完成时**（看到 "ClawSeat install:" + "machine-memory-claude" 等字样）：
- 报告：`Phase 2 done. install.sh exited cleanly.`
- 验证：`tmux ls | grep -E "smoketest-(ancestor|planner|builder|reviewer|qa|designer)|machine-memory-claude" | wc -l` 应该 = 7
- 提取最后那段 paste prompt（介于 `---` 之间），作为 Phase 3 输入

---

## Phase 3 — 模拟 operator 粘贴 prompt 到 ancestor

minimax 不要试着自己驱动 Phase-A。你只做一件事：**把 install.sh 印的那段 prompt 通过 tmux send-keys 送进 smoketest-ancestor pane**。

```bash
# install.sh 印出来的 prompt 大概是:
#   读 $CLAWSEAT_ANCESTOR_BRIEF，开始 Phase-A。每步向我确认或报告。
# 把它 send-keys 到 ancestor pane

PROMPT='读 $CLAWSEAT_ANCESTOR_BRIEF，开始 Phase-A。每步向我确认或报告。'
tmux send-keys -t =smoketest-ancestor -l "$PROMPT"
sleep 0.5
tmux send-keys -t =smoketest-ancestor Enter
```

**注意**：`-l` 是 literal 模式，避免 `$CLAWSEAT_ANCESTOR_BRIEF` 被本地 shell 提前展开。让 ancestor pane 里的 claude 自己解析。

报告 "Phase 3 prompt sent. ancestor 应已开始 Phase-A. 用户接管。"

---

## Phase 4 — 用户驱动 Phase-A（你只是被动观察）

**你在这一阶段不主动驱动**。用户会亲自 attach 到 smoketest-ancestor pane，回答 ancestor 的所有 Phase-A 问题（B0 → B7）。

你的工作：
- 每隔 60 秒 `tmux capture-pane -t =smoketest-ancestor -p | tail -30` 一次，简短报告 ancestor 当前在哪步
- 监测 `/Users/ywf/.agents/tasks/smoketest/STATUS.md` 是否出现 `phase=ready`
- 看到 `phase=ready` → 进 Phase 5
- 看到 `phase=blocked` 或卡住 > 5 分钟 → 报告状态

**不要替用户回答 Phase-A 的问题。**

---

## Phase 5 — Post-validation（你自己跑）

```bash
echo "=== STATUS ==="
cat /Users/ywf/.agents/tasks/smoketest/STATUS.md

echo "=== tmux sessions ==="
for s in smoketest-ancestor smoketest-planner smoketest-builder smoketest-reviewer smoketest-qa smoketest-designer machine-memory-claude; do
  tmux has-session -t "=$s" 2>/dev/null && echo "$s: alive" || echo "$s: DEAD"
done

echo "=== hooks installed ==="
test -f /Users/ywf/.agents/workspaces/smoketest/memory/.claude/settings.json && echo "memory hook: file exists" || echo "memory hook: MISSING"
test -f /Users/ywf/.agents/workspaces/smoketest/planner/.claude/settings.json && echo "planner hook: file exists" || echo "planner hook: MISSING"

echo "=== brief rendered ==="
test -f /Users/ywf/.agents/tasks/smoketest/patrol/handoffs/ancestor-bootstrap.md && wc -l /Users/ywf/.agents/tasks/smoketest/patrol/handoffs/ancestor-bootstrap.md || echo "brief: MISSING"

echo "=== claude processes ==="
pgrep -f "claude --dangerously-skip" | wc -l
```

报告全量验证结果。

---

## Phase 6 — Teardown（**等用户明确说"OK to teardown"再跑**）

```bash
for s in smoketest-ancestor smoketest-planner smoketest-builder smoketest-reviewer smoketest-qa smoketest-designer machine-memory-claude install-runner; do
  tmux kill-session -t "=$s" 2>/dev/null || true
done
rm -rf /Users/ywf/.agents/workspaces/smoketest /Users/ywf/.agents/tasks/smoketest
rm -f /tmp/install-runner.log
echo "teardown done. iTerm windows 用户手动关。"
```

---

## 交付

写 `DELIVERY-LIVE-043.md`：

```
task_id: LIVE-043
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话: phase=ready ✓ / 卡在 X / FAIL at Y>

## Phase 1 — Pre-cleanup
<结果>

## Phase 2 — install.sh
- 触发的 interactive prompts 列表 + 用户回答
- install.sh 最终状态（成功 / 失败 / 卡住）
- 7 tmux sessions 创建情况

## Phase 3 — Prompt sent to ancestor
<状态>

## Phase 4 — Phase-A 进展（被动观察）
- ancestor 各 B step 时间线
- 用户回答的关键决策点
- 最终 STATUS.md 内容

## Phase 5 — Validation
- 全验证清单结果

## Phase 6 — Teardown
<状态 / 等待用户授权>

## 发现的问题
- 任何代码 / docs gap / UX 不顺
```

完成 Phase 5 验证后通知 planner: "DELIVERY-LIVE-043 ready (awaiting teardown auth)"。

---

## 硬约束

1. **绝对禁止**自己 patch 代码 / 改 docs / 改任何文件
2. **绝对禁止**回答 Phase-A 的语义问题（哪个 provider、哪个 seat 跑哪个工具）
3. **绝对禁止**未经用户允许 teardown
4. 任何**意外**：立刻停下报告
5. 报告言简意赅，每条 ≤ 5 行
