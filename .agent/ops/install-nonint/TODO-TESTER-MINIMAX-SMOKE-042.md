# TODO — SMOKE-042 (PLANNERHOOK-041 增量 + v0.5 清理 verify)

```
task_id: SMOKE-042
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: OK (2 subagents: A=pytest+hook dry-run, B=整合验证)
do-not-modify: 只读 + 在 /tmp/ 下建临时文件；不碰 ~/.agents/ 或 ~/.openclaw/ 或 ~/.clawseat/
```

## Context

继 SMOKE-040 后：
- PLANNERHOOK-041 新交付：`planner-stop-hook.sh` + `install_planner_hook.py` + ancestor-brief B3.5 接入 + v0.5 legacy smoke 删除
- 现在跑 **增量 smoke** 确认这些新东西不坏 + 老东西没退化

**禁止触碰**：`~/.agents/`, `~/.openclaw/`, `~/.clawseat/`。所有 /tmp/smoke-042/ 下。

---

## Subagent A — pytest 全量 + 新增语法

```bash
cd /Users/ywf/ClawSeat
mkdir -p /tmp/smoke-042

# 1. 语法
bash -n scripts/hooks/planner-stop-hook.sh
python3 -m py_compile core/skills/planner/scripts/install_planner_hook.py

# 2. pytest 全量（SMOKE-040 是 1645；v0.5 smoke 删了 1 个 → 应该是 1651 或 1644 左右）
pytest tests/ -v --timeout=30 2>&1 | tee /tmp/smoke-042/pytest-full.log

# 3. 新增测试单跑
pytest tests/test_planner_stop_hook.py tests/test_install_planner_hook.py -v 2>&1 | tee /tmp/smoke-042/pytest-planner-new.log
# 期望: 8 passed

# 4. v0.5 legacy 测试确认已删
test ! -f tests/test_v05_smoke.py && test ! -f tests/smoke/test_v05_install.sh && echo "legacy_v05_deleted: YES" || echo "legacy_v05_deleted: NO"
```

输出：
- bash -n / py_compile rc
- pytest 总数 pass/fail（对比 SMOKE-040 的 1644/1645，现在应该 passes 增加 8 因为新测试 + fail 降到 0 因为 v0.5 删了）
- 任何 fail 的原文
- legacy v0.5 删除确认

---

## Subagent B — 整合 + hook 行为验证

```bash
cd /Users/ywf/ClawSeat
mkdir -p /tmp/smoke-042

# 1. install.sh dry-run 回归（确保 SMOKE-040 里过的 10 步仍在）
bash scripts/install.sh --dry-run --project smoketest 2>&1 | tee /tmp/smoke-042/install-dryrun.log
grep -E "Step [0-9]+(\.5)?:" /tmp/smoke-042/install-dryrun.log | sort -u
# 期望: Steps 1-9 + 7.5 全在

# 2. ancestor-brief 渲染新 B3.5 hook 行
python3 - <<'PY' 2>&1 | tee /tmp/smoke-042/brief-render.log
from pathlib import Path
from string import Template
t = Path('/Users/ywf/ClawSeat/core/templates/ancestor-brief.template.md').read_text()
rendered = Template(t).safe_substitute(PROJECT_NAME='smoketest', CLAWSEAT_ROOT='/Users/ywf/ClawSeat')
checks = {
    'B2.5 present': 'B2.5' in rendered,
    'bootstrap_machine_tenants mentioned': 'bootstrap_machine_tenants' in rendered,
    'install_planner_hook mentioned': 'install_planner_hook' in rendered,
    'smoketest/planner path mentioned': 'workspaces/smoketest/planner' in rendered,
    'CLAWSEAT_ROOT substituted': '/Users/ywf/ClawSeat' in rendered,
}
for k, v in checks.items():
    print(f'{"OK  " if v else "FAIL"} {k}')
import re
unresolved = re.findall(r'\$\{[A-Z_]+\}', rendered)
print(f'unresolved_placeholders: {unresolved}')
PY

# 3. planner-stop-hook.sh 各 edge case
# 3a. PLANNER_STOP_HOOK_ENABLED=0 → 立即退出
PLANNER_STOP_HOOK_ENABLED=0 echo 'test' | bash scripts/hooks/planner-stop-hook.sh
echo "case_3a_rc=$?"

# 3b. 无 stdin JSON → 退出 rc=0
echo '' | bash scripts/hooks/planner-stop-hook.sh 2>&1 | head -5
echo "case_3b_rc=$?"

# 3c. 缺 PROJECT_BINDING.toml → silent skip
echo '{"last_assistant_message":"hello","transcript_path":""}' | CLAWSEAT_PROJECT=smoketest_nonexist bash scripts/hooks/planner-stop-hook.sh 2>&1 | tee /tmp/smoke-042/hook-no-binding.log
echo "case_3c_rc=$?"
# 期望 stderr: "[planner-hook] no PROJECT_BINDING.toml; skip"; rc=0

# 3d. 长消息截断（> 18000 字符）
python3 -c 'import json; print(json.dumps({"last_assistant_message": "X"*30000, "transcript_path": ""}))' \
  | CLAWSEAT_PROJECT=smoketest_nonexist bash scripts/hooks/planner-stop-hook.sh 2>&1 | tee /tmp/smoke-042/hook-truncate.log
echo "case_3d_rc=$?"
# 期望: rc=0；可能看 "no PROJECT_BINDING.toml; skip" (因为测试场景)

# 4. install_planner_hook.py dry-run
python3 core/skills/planner/scripts/install_planner_hook.py \
  --workspace /tmp/smoke-042/fake-planner-workspace \
  --clawseat-root /Users/ywf/ClawSeat \
  --dry-run 2>&1 | tee /tmp/smoke-042/planner-hook-install-dryrun.log
echo "installer_rc=$?"
# 期望: 打印 JSON with Stop hook pointing to scripts/hooks/planner-stop-hook.sh

# 5. 幂等性：installer 跑两次，第二次不写
python3 core/skills/planner/scripts/install_planner_hook.py \
  --workspace /tmp/smoke-042/real-planner-workspace \
  --clawseat-root /Users/ywf/ClawSeat 2>&1 | tee /tmp/smoke-042/planner-install-1.log
MT1=$(stat -f %m /tmp/smoke-042/real-planner-workspace/.claude/settings.json 2>/dev/null || stat -c %Y /tmp/smoke-042/real-planner-workspace/.claude/settings.json)
sleep 1
python3 core/skills/planner/scripts/install_planner_hook.py \
  --workspace /tmp/smoke-042/real-planner-workspace \
  --clawseat-root /Users/ywf/ClawSeat 2>&1 | tee /tmp/smoke-042/planner-install-2.log
MT2=$(stat -f %m /tmp/smoke-042/real-planner-workspace/.claude/settings.json 2>/dev/null || stat -c %Y /tmp/smoke-042/real-planner-workspace/.claude/settings.json)
echo "idempotent: MT1=$MT1 MT2=$MT2 diff=$((MT2-MT1))"
# 期望: MT1 == MT2（不重写）或差 0-1 秒（可接受）
cat /tmp/smoke-042/real-planner-workspace/.claude/settings.json | python3 -m json.tool 2>&1 | head -20
# 确认只有一个 Stop hook 条目
```

---

## 产出

`DELIVERY-SMOKE-042.md`：

```
task_id: SMOKE-042
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话: X passed, Y failed, v0.5 legacy cleaned: YES/NO>

## Subagent A — pytest + 语法
- 总 pytest: X pass / Y fail / Z skip
- 新增测试 8 passed: ✓/✗
- v0.5 legacy 删除: ✓/✗
- 任何 fail 原文摘录

## Subagent B — 行为验证
- install.sh dry-run 10 steps: ✓/✗
- ancestor-brief B3.5 install_planner_hook 行: ✓/✗
- hook enabled=0 early exit: rc=?
- hook no-binding silent skip: rc=?, stderr 内容
- hook 长消息截断: rc=?
- installer dry-run: JSON 结构
- installer 幂等: MT1 vs MT2 差值

## 发现的问题
<FAIL / WARN / INFO 分级>

## 没发现问题的地方
<明确说 X 没 fail>

## 清理
<跑完 rm -rf /tmp/smoke-042/>
```

完成后通知 planner: "DELIVERY-SMOKE-042 ready"。

## 约束

- 不碰真实 ~/.agents/ / ~/.openclaw/ / ~/.clawseat/
- 不真跑 install.sh（只 dry-run）
- 看到 fail 只报告不改
- 跑完必须 `rm -rf /tmp/smoke-042/`
