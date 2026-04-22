# TODO — KODER-033 (apply-koder-overlay.sh 交互菜单 + 编排)

```
task_id: KODER-033
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental worktree)
priority: P1
queued: YES — 先完成 INSTALLSH-030 再做此任务
subagent-mode: OK (1 主实现 + 1 test 子 agent 并行)
scope: 新增 1 个 shell 脚本 + 小改动到现有 python
```

## Context

Koder overlay 底层组件已在仓库里存在：
- `core/skills/clawseat-install/scripts/init_koder.py` — destructive 覆盖 OpenClaw agent workspace
- `agent_admin project koder-bind --project <p> --tenant <t>` — 绑项目
- `core/skills/clawseat-install/scripts/configure_koder_feishu.py` — 写飞书凭据

缺的只是 UX 层：
1. "列出 OpenClaw agent + 让用户选" 的交互菜单
2. 一键编排脚本把上面 3 步串起来

本任务要补上这两样。

## Deliverable 1 — `scripts/apply-koder-overlay.sh`

新建文件。行为：

```bash
#!/usr/bin/env bash
set -euo pipefail
PROJECT="${1:-install}"
FEISHU_GROUP_ID="${2:-}"

# Step 1: 列 OpenClaw tenants
AGENTS=$(python3 -c "from core.lib.machine_config import list_openclaw_tenants; print('\n'.join(list_openclaw_tenants()))")
if [ -z "$AGENTS" ]; then
  echo "ERR_NO_OPENCLAW_AGENTS: ~/.openclaw/ 下未找到可用 OpenClaw agent" >&2; exit 2
fi

# Step 2: CLI menu
echo "可选的 OpenClaw agent (作为 koder 身份)："
mapfile -t LIST <<< "$AGENTS"
for i in "${!LIST[@]}"; do echo "  [$((i+1))] ${LIST[i]}"; done
read -p "Pick number: " IDX
CHOSEN="${LIST[$((IDX-1))]}"
[ -z "$CHOSEN" ] && { echo "ERR_BAD_PICK"; exit 3; }

# Step 3: 确认 destructive 警告
echo "将把 '$CHOSEN' 的身份**完全覆盖**为 koder。此操作会改写 6 个核心文件（IDENTITY/SOUL/TOOLS/MEMORY/AGENTS/CONTRACT）。"
read -p "确认? [y/N]: " CONFIRM
[[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]] && { echo "aborted"; exit 0; }

# Step 4: init_koder.py
WORKSPACE="$HOME/.openclaw/workspace-$CHOSEN"
PROFILE="$HOME/.agents/profiles/${PROJECT}-profile.toml"
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/init_koder.py" \
  --workspace "$WORKSPACE" \
  --project "$PROJECT" \
  --profile "$PROFILE" \
  ${FEISHU_GROUP_ID:+--feishu-group-id "$FEISHU_GROUP_ID"} \
  --on-conflict backup

# Step 5: bind project
python3 -c "from core.scripts.agent_admin_layered import do_koder_bind; do_koder_bind('$PROJECT', '$CHOSEN')"

# Step 6: configure feishu creds (若提供 group_id)
if [ -n "$FEISHU_GROUP_ID" ]; then
  python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/configure_koder_feishu.py" \
    --agent "$CHOSEN" --openclaw-home "$HOME/.openclaw"
fi

echo "OK: '$CHOSEN' 已改造为 koder，绑定到项目 '$PROJECT'"
```

约束：
- `set -euo pipefail`，所有失败回退合理 exit code
- 每一步失败都要 print `ERR_<CODE>` 到 stderr（便于上层捕获）
- 支持 `--dry-run` 模式打印命令不执行
- 幂等：同一 agent 重复运行走 `--on-conflict backup` 不炸

## Deliverable 2 — `list_openclaw_tenants()` 验证

确认 `core/lib/machine_config.py`（或等价位置）有可调用的 `list_openclaw_tenants()` 函数；没有则补一个：

```python
def list_openclaw_tenants(openclaw_home: Path = Path("~/.openclaw").expanduser()) -> list[str]:
    """Return list of OpenClaw agent names discoverable in openclaw_home."""
    agents_dir = openclaw_home / "workspaces"  # or wherever
    if not agents_dir.exists(): return []
    return sorted(d.name.replace("workspace-", "") for d in agents_dir.iterdir() 
                  if d.is_dir() and d.name.startswith("workspace-"))
```

先查实际 OpenClaw 的 workspace 目录组织方式再定义；不要硬编码错路径。

## Deliverable 3 — 单元测试

`tests/test_apply_koder_overlay.py`：
- bats-ish 或 pytest + subprocess
- Mock `~/.openclaw/workspaces/{a,b,c}/` → 验证菜单出了 3 项
- 选 `1` → 验证 init_koder.py 被调（可 mock）
- `--dry-run` 不改任何文件

## Verification (你必须跑)

```bash
bash -n scripts/apply-koder-overlay.sh && echo "syntax ok"
bash scripts/apply-koder-overlay.sh --dry-run install   # 应打印 5 步命令不执行
python3 -c "from core.lib.machine_config import list_openclaw_tenants; print(list_openclaw_tenants())"
pytest tests/test_apply_koder_overlay.py -v
```

## Deliverable (交付)

写 `DELIVERY-KODER-033.md`：

```
task_id: KODER-033
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## 改动清单
- scripts/apply-koder-overlay.sh (新建, N 行)
- <其他改动>

## Verification
<bash -n / dry-run / pytest 输出>

## 已知限制
<没覆盖的 case>
```

**不要 commit，留给 planner 审。**
