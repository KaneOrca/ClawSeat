# TODO — SMOKE-040 (非破坏性 smoke 测试)

```
task_id: SMOKE-040
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: OK (2-3 parallel subagents: A=pytest/syntax, B=shell dry-run, C=hook/template)
do-not-modify: 只读 + 在 /tmp/ 下建临时文件；不碰 ~/.agents/ 或 ~/.openclaw/ 或 ~/.clawseat/
```

## Context

v0.7 一批代码已交付（uncommitted），planner 已亲自过审发现无真 bug。minimax 专职**测试**（而非 review）——现在跑一轮全量非破坏性 smoke，**看到实际报错才反馈**，不推测不揣测。

你（minimax）的 repo 是 `/Users/ywf/ClawSeat`（experimental worktree）。**禁止**动真实的 `~/.agents/memory/`、`~/.openclaw/`、`~/.clawseat/` — 所有测试产物写到 `/tmp/smoke-040/` 下。

---

## Subagent A — 全量 pytest + 语法检查

```bash
cd /Users/ywf/ClawSeat

# 1. 语法
bash -n scripts/install.sh
bash -n scripts/apply-koder-overlay.sh
bash -n scripts/hooks/memory-stop-hook.sh
python3 -m py_compile core/scripts/bootstrap_machine_tenants.py \
                    core/lib/openclaw_home.py \
                    core/skills/memory-oracle/scripts/scan_environment.py \
                    core/skills/memory-oracle/scripts/install_memory_hook.py

# 2. pytest 全量
pytest tests/ -v --timeout=30 2>&1 | tee /tmp/smoke-040/pytest-full.log
# 记录: 总数, pass, fail, skip

# 3. 新加的测试单跑一遍
pytest tests/test_scan_openclaw.py \
       tests/test_bootstrap_machine_tenants.py \
       tests/test_apply_koder_overlay.py \
       tests/test_memory_stop_hook.py \
       -v
```

输出：pass/fail 数字 + 所有 fail 的 test 名 + 原文报错摘录（每条 ≤10 行）。

---

## Subagent B — install.sh / apply-koder-overlay.sh dry-run

```bash
mkdir -p /tmp/smoke-040

# 1. install.sh dry-run (不触碰真环境)
bash scripts/install.sh --dry-run --project smoketest 2>&1 | tee /tmp/smoke-040/install-dryrun.log

# 验证清单（grep 确认存在）：
# - "Step 1: host deps"
# - "Step 2: environment scan"
# - "Step 3: ancestor provider"
# - "Step 4: render ancestor brief"
# - "Step 5: create install tmux sessions"
# - "Step 6: launch ancestor Claude"
# - "Step 7: open six-pane iTerm grid"
# - "Step 8: start memory session + iTerm window"
# - "Step 9: focus ancestor and flush"
# - 不应出现实际 brew install / tmux new-session (因为 dry-run)

# 2. apply-koder-overlay.sh dry-run
bash scripts/apply-koder-overlay.sh --dry-run smoketest 2>&1 | tee /tmp/smoke-040/overlay-dryrun.log

# 验证清单：
# - 列出至少一个 tenant (你机器上应该有 13 个)
# - "[dry-run] auto-selecting [1] <name>"
# - "Step 4: init_koder" dry-run 命令
# - "Step 5: project koder-bind" dry-run 命令
# - 没有 "Step 6: configure koder feishu" (因为没传 feishu_group_id)
```

输出：每步 grep 命中/未命中 + 任何非预期 warning/error。

---

## Subagent C — scan + hook + template 单项测

```bash
mkdir -p /tmp/smoke-040

# 1. scan_environment.py 真跑（只 openclaw 部分，不影响其他）
python3 core/skills/memory-oracle/scripts/scan_environment.py \
  --only openclaw --output /tmp/smoke-040/memory/ 2>&1 | tee /tmp/smoke-040/scan.log

# 验证：
python3 -c "
import json
from pathlib import Path
d = json.loads(Path('/tmp/smoke-040/memory/machine/openclaw.json').read_text())
print('home:', d.get('home'))
print('exists:', d.get('exists'))
print('agents count:', len(d.get('agents', [])))
print('first agent:', d.get('agents', [{}])[0])
"
# 期望: home 存在, agents 数量 > 0 (你机器上应该是 13 左右)

# 2. bootstrap_machine_tenants 到 tmp machine.toml
# 需要 fake CLAWSEAT_REAL_HOME
CLAWSEAT_REAL_HOME=/tmp/smoke-040/clawseat-fakehome python3 core/scripts/bootstrap_machine_tenants.py /tmp/smoke-040/memory/
# 期望 stdout: "OK: N tenant(s) added; M total"
# 验证: cat /tmp/smoke-040/clawseat-fakehome/.clawseat/machine.toml
cat /tmp/smoke-040/clawseat-fakehome/.clawseat/machine.toml 2>&1 | head -40

# 3. install_memory_hook.py dry-run
python3 core/skills/memory-oracle/scripts/install_memory_hook.py \
  --workspace /tmp/smoke-040/fake-memory-workspace \
  --dry-run 2>&1 | tee /tmp/smoke-040/hook-install-dryrun.log
# 期望: 打印 JSON settings with Stop hook

# 4. memory-stop-hook.sh 手动喂 payload
echo '{"transcript_path": "/tmp/smoke-040/fake-transcript.md", "last_assistant_message": "Done. [CLEAR-REQUESTED]"}' \
  | bash scripts/hooks/memory-stop-hook.sh 2>&1 | tee /tmp/smoke-040/hook-clear.log
# 期望: 不报错退出（可能会尝试 tmux send-keys 但因为 session 不存在会静默）

echo '{"transcript_path": "/tmp/smoke-040/fake-transcript.md", "last_assistant_message": "task_id: TEST-1\nproject: smoketest\n[DELIVER:seat=planner]"}' \
  | bash scripts/hooks/memory-stop-hook.sh 2>&1 | tee /tmp/smoke-040/hook-deliver.log
# 期望: 看到 [memory-hook] deliver_skipped 或真尝试调 memory_deliver.py

# 5. ancestor-brief template 渲染
python3 - <<'PY' 2>&1 | tee /tmp/smoke-040/brief-render.log
from pathlib import Path
from string import Template
t = Path('/Users/ywf/ClawSeat/core/templates/ancestor-brief.template.md')
rendered = Template(t.read_text()).safe_substitute(PROJECT_NAME='smoketest', CLAWSEAT_ROOT='/Users/ywf/ClawSeat')
print(rendered[:500])  # 前 500 字
print('---')
print('lines:', len(rendered.splitlines()))
# 验证: $PROJECT_NAME 和 $CLAWSEAT_ROOT 都被替换掉
import re
unsubbed = re.findall(r'\$\{[A-Z_]+\}', rendered)
print('unresolved placeholders:', unsubbed)
PY
```

输出：每项命令 rc + 关键输出摘录 + 任何报错原文。

---

## 产出

写 `DELIVERY-SMOKE-040.md`：

```
task_id: SMOKE-040
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话: X tests pass / Y fail / Z issues 观察到>

## Subagent A — pytest + syntax
- 总 pytest 数: X pass / Y fail / Z skip
- 任何 fail 的原文:
- 所有 bash -n / py_compile rc 是否为 0

## Subagent B — shell dry-run
- install.sh dry-run: 全部步骤到齐 / 缺哪几步
- apply-koder-overlay.sh dry-run: tenant 列表正常 / 菜单正常

## Subagent C — scan + hook + template
- scan_openclaw: home=?, agents count=?
- bootstrap_machine_tenants: N added
- install_memory_hook dry-run: JSON 结构正常
- memory-stop-hook CLEAR-REQUESTED: rc=?
- memory-stop-hook DELIVER marker: rc=?
- ancestor-brief 渲染: unresolved placeholders = ?

## 发现的问题
- 按严重度排序（FAIL / WARN / INFO）
- 每条给：触发命令 + 原文报错 + 你的猜测（可选）

## 没发现问题的地方
- 明确说"这部分没 fail / 没 warn"
```

完成后通知 planner: "DELIVERY-SMOKE-040 ready"。

## 约束

- **绝不**动 `~/.agents/`, `~/.openclaw/`, `~/.clawseat/`, `~/ClawSeat/`（真实目录）
- **绝不** `tmux new-session` / `brew install` / 真 claude 启动
- 所有产物 `/tmp/smoke-040/` 下
- 跑完后 `rm -rf /tmp/smoke-040/` 清理（最后一步）
- 看到失败**不要尝试修**，只报告给 planner
