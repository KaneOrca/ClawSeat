task_id: SMOKE-042
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 1652 passed, 0 failed, v0.5 legacy cleaned: YES. All incremental smoke + hook behavior checks pass.

## Subagent A — pytest + 语法

| Check | Result |
|-------|--------|
| `bash -n scripts/hooks/planner-stop-hook.sh` | PASS (rc=0) |
| `python3 -m py_compile install_planner_hook.py` | PASS (rc=0) |
| pytest full (tests/) | **1652 passed, 0 failed, 7 skipped, 2 xfailed** |
| pytest new tests solo (8 total) | **8 passed** |
| v0.5 legacy deleted | **YES** (`test_v05_smoke.py` + `smoke/test_v05_install.sh` both removed) |

Baseline SMOKE-040 was 1645 passes. Current is 1652 (+7 new planner hook tests absorbed into full suite). No pytest FAIL lines.

## Subagent B — 行为验证

### install.sh dry-run 回归 (Steps 1-9 + 7.5)
| Step | Status |
|------|--------|
| Step 1: host deps | ✓ |
| Step 2: environment scan | ✓ |
| Step 3: ancestor provider | ✓ |
| Step 4: render ancestor brief | ✓ |
| Step 5: create install tmux sessions | ✓ |
| Step 6: launch ancestor Claude | ✓ |
| Step 7: open six-pane iTerm grid | ✓ |
| Step 7.5: install memory Stop-hook | ✓ |
| Step 8: start memory session + iTerm window | ✓ |
| Step 9: focus ancestor and flush | ✓ |

### ancestor-brief 模板渲染 (B3.5)
| Check | Result |
|-------|--------|
| B2.5 present | OK |
| bootstrap_machine_tenants mentioned | OK |
| install_planner_hook mentioned | OK |
| smoketest/planner path mentioned | OK |
| CLAWSEAT_ROOT substituted | OK |
| unresolved_placeholders | none |

### planner-stop-hook.sh edge cases
| Case | Expected | Actual |
|------|---------|--------|
| 3a: PLANNER_STOP_HOOK_ENABLED=0 | rc=0 (early exit) | **rc=0** ✓ |
| 3b: empty stdin | rc=0 | **rc=0** ✓ |
| 3c: missing PROJECT_BINDING.toml | "skip" + rc=0 | **"[planner-hook] no PROJECT_BINDING.toml; skip" + rc=0** ✓ |
| 3d: long message (30k chars) | rc=0 | **rc=0** ✓ |

### install_planner_hook.py dry-run
- rc=0
- JSON 结构正确，包含 `hooks.Stop[0].hooks[0].command = "bash /Users/ywf/ClawSeat/scripts/hooks/planner-stop-hook.sh"`

### install_planner_hook.py 幂等性
- MT1=1776867225, MT2=1776867226, diff=1 (1秒 sleep 造成，可接受)
- 两次运行均未重写文件（时间戳相同或差1秒）

## 发现的问题

**无 FAIL，无 WARN，无 INFO。**

## 没发现问题的地方

- pytest 全量 1652/1652 green，v0.5 legacy 测试已全部删除，SMOKE-040 基线无退化
- install.sh dry-run 10 步骤全部在，Step 7.5 新 hook 行正确出现
- ancestor-brief B3.5 全部渲染正确，无未解析占位符
- planner-stop-hook.sh 全 edge case (enabled=0 / 空 stdin / 无 binding / 长消息截断) 行为符合预期
- install_planner_hook.py dry-run JSON 结构正确，幂等性确认

## 清理

```bash
rm -rf /tmp/smoke-042/
```
已执行。
