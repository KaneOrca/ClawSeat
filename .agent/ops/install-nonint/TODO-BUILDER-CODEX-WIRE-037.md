# TODO — WIRE-037 (install.sh 集成 SCAN-034 + MEMORY-035)

```
task_id: WIRE-037
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P1
queued: YES — 先完成 SKILL-031 再做
subagent-mode: OPTIONAL (可单 agent)
scope: 改 scripts/install.sh + core/templates/ancestor-brief.template.md
```

## Context

SCAN-034 交付了：
- `core/scripts/bootstrap_machine_tenants.py`（把 memory scan 出来的 agents 灌进 `~/.clawseat/machine.toml`）

MEMORY-035 交付了：
- `scripts/hooks/memory-stop-hook.sh`（监听 `[CLEAR-REQUESTED]` / `[DELIVER:seat=X]`）
- `core/skills/memory-oracle/scripts/install_memory_hook.py`（幂等装 hook 到 workspace settings.json）

这两份现成零件要接进 install 流程里，不然还是孤岛。

## 任务

### T1 — install.sh 增加一步：装 memory Stop-hook

在 `scripts/install.sh` 里，**在启动 memory tmux session 之前**（Step 8 之前，因为装 hook 是在 memory 起来之前定 settings.json）：

```bash
# Step 7.5: Install memory Stop-hook
MEMORY_WORKSPACE="${MEMORY_WORKSPACE:-$HOME/.agents/engineers/memory/_machine}"  # 或现有 memory workspace 约定
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/install_memory_hook.py" \
  --workspace "$MEMORY_WORKSPACE" \
  --clawseat-root "$CLAWSEAT_ROOT"
```

**请先查清 memory workspace 的实际路径约定**（可能是 `~/.agents/engineers/memory/<project>/` 或 `~/.agents/memory/_workspace/` 或其他）。读 `agent_admin_layered.py`（或相关），找 memory 的 workspace 组织方式。不要臆测路径。

### T2 — ancestor-brief.template.md 增加 B2.5

在 `core/templates/ancestor-brief.template.md` 里 **B2-verify-memory 之后、B3-verify-openclaw-binding 之前** 插 B2.5：

```markdown
### B2.5 — Bootstrap machine tenants from memory scan

读 `~/.agents/memory/machine/openclaw.json` 的 `agents` 列表并灌进 `~/.clawseat/machine.toml [openclaw_tenants.*]`：

```bash
python3 core/scripts/bootstrap_machine_tenants.py ~/.agents/memory/
```

成功判据：`list_openclaw_tenants()` 返回非空（若本机装了 OpenClaw）。

失败：记录 `B2.5_BOOTSTRAP_FAILED`，继续（后续 B3.5 如果需要选 agent 会再次提醒；不阻塞）。
```

### T3 — install.sh dry-run / 新 Step 检查

- `bash scripts/install.sh --dry-run` 要能打印 Step 7.5 的命令
- 失败码单独加：`MEMORY_HOOK_INSTALL_FAILED`

### T4 — 可选：bootstrap 调用也进 install.sh

争论点：是让 ancestor 在 Phase-A B2.5 调 bootstrap_machine_tenants，还是 install.sh 直接调？

**决策**：让 ancestor 调（更符合 v0.7 "install.sh 搭架子、ancestor 做智能操作" 分工）。所以 install.sh **不** 自己调 bootstrap，只确保脚本存在可用。

## Verification

```bash
bash -n scripts/install.sh && echo "syntax ok"
bash scripts/install.sh --dry-run --project install 2>&1 | grep -E "install_memory_hook|MEMORY_HOOK"
# 应看到 install_memory_hook.py 调用 (dry-run 模式)

# ancestor-brief 渲染
python3 - <<'PY'
from pathlib import Path
from string import Template
p = Path('core/templates/ancestor-brief.template.md')
t = Template(p.read_text()).safe_substitute(PROJECT_NAME='install', CLAWSEAT_ROOT='/Users/ywf/ClawSeat')
assert 'B2.5' in t, "B2.5 not rendered"
assert 'bootstrap_machine_tenants' in t, "bootstrap not referenced"
print("ok")
PY
```

## Deliverable

`DELIVERY-WIRE-037.md`：

```
task_id: WIRE-037
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## 改动清单
- scripts/install.sh (diff 摘录)
- core/templates/ancestor-brief.template.md (diff 摘录)

## memory workspace 路径调研结论
<说明实际路径从哪查到的、最终填了什么>

## Verification
<bash -n / dry-run / 渲染测试>
```

**不 commit，留给 planner 审**。
