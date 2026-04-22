# TODO — PLANNERHOOK-041 (planner stop-hook 实装)

```
task_id: PLANNERHOOK-041
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: OK (2 subagents: A=hook+installer, B=tests)
scope: 2 新文件 + 1 个清理 + tests
```

## Context

`core/skills/planner/SKILL.md §6` 声称每轮 stop-hook 发飞书结构化摘要。但**实际脚本根本不存在**。这是 v0.7 承诺但未交付的 gap，用户要求写完再测试。

参考：已交付的 `scripts/hooks/memory-stop-hook.sh` + `core/skills/memory-oracle/scripts/install_memory_hook.py`（MEMORY-035）。可以**镜像**它的结构和风格。

## Decision / 设计

- **广播内容**：`last_assistant_message` 全量（head+tail 18000 字截断兜底）
  - 以后可以做结构化提取，这一版简化
- **目标群**：从 `~/.agents/tasks/<project>/PROJECT_BINDING.toml` 读 `feishu_group_id`
- **工具**：`lark-cli im +messages-send --chat-id <X> --text <Y>`（参考 gstack-harness 里已有用法）
- **失败静默**：`feishu_group_id` 缺失 / `lark-cli` 没装 / 网络不通 — 全部 `|| true`，hook 不阻塞 Claude Code
- **启用开关**：env `PLANNER_STOP_HOOK_ENABLED`（默认 `1`，`0` 时 hook 立即退出）
- **Project 识别**：从 `$CLAWSEAT_PROJECT` env 读；缺失则从 Claude Code workspace 目录路径反推（`~/.agents/workspaces/<project>/planner`）

## Deliverable 1 — `scripts/hooks/planner-stop-hook.sh`

新建。大致 80-120 行。镜像 memory-stop-hook.sh 的风格：

```bash
#!/usr/bin/env bash
# planner stop-hook: broadcast last assistant message to feishu.
# Silent no-op if no feishu_group_id configured or lark-cli missing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CLAWSEAT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLAWSEAT_ROOT="${CLAWSEAT_ROOT:-${CLAUDE_PROJECT_DIR:-$DEFAULT_CLAWSEAT_ROOT}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PROJECT="${CLAWSEAT_PROJECT:-}"
MAX_CHARS=18000

# Enable gate
[[ "${PLANNER_STOP_HOOK_ENABLED:-1}" == "1" ]] || exit 0

# 1. Read stdin Claude Code Stop-hook JSON
payload="$(cat || true)"
[[ -n "$payload" ]] || exit 0

# 2. Extract text (transcript or last_assistant_message), head+tail truncate
TEXT="$(HOOK_PAYLOAD="$payload" MAX="$MAX_CHARS" "$PYTHON_BIN" - <<'PY' || true
import json, os, sys
from pathlib import Path
raw = os.environ.get("HOOK_PAYLOAD","")
try:
    p = json.loads(raw)
except Exception:
    sys.exit(0)
tp = str(p.get("transcript_path","") or "").strip()
last = str(p.get("last_assistant_message","") or "")
text = ""
if tp:
    try:
        text = Path(tp).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
if not text:
    text = last
max_chars = int(os.environ.get("MAX","18000"))
if len(text) > max_chars:
    half = max_chars // 2
    text = f"{text[:half]}\n...[omitted {len(text)-max_chars} chars]...\n{text[-half:]}"
sys.stdout.write(text)
PY
)"
[[ -n "$TEXT" ]] || exit 0

# 3. Determine project (env > workspace-path reverse-lookup)
if [[ -z "$PROJECT" ]]; then
  # Try: CWD or $CLAUDE_PROJECT_DIR parent matches ~/.agents/workspaces/<project>/planner
  for candidate in "${CLAUDE_PROJECT_DIR:-}" "$PWD"; do
    if [[ "$candidate" == *"/.agents/workspaces/"* ]]; then
      PROJECT="$(echo "$candidate" | sed -E 's|.*\.agents/workspaces/([^/]+)/.*|\1|')"
      break
    fi
  done
fi
[[ -n "$PROJECT" ]] || { echo "[planner-hook] no project resolvable; skip" >&2; exit 0; }

# 4. Read feishu_group_id from PROJECT_BINDING.toml
BINDING="$HOME/.agents/tasks/$PROJECT/PROJECT_BINDING.toml"
[[ -f "$BINDING" ]] || { echo "[planner-hook] no PROJECT_BINDING.toml; skip" >&2; exit 0; }
GROUP="$("$PYTHON_BIN" - "$BINDING" <<'PY' || true
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path
data = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
g = data.get("feishu_group_id") or data.get("bridge", {}).get("group_id") or ""
print(g)
PY
)"
[[ -n "$GROUP" ]] || { echo "[planner-hook] no feishu_group_id; skip" >&2; exit 0; }

# 5. Check lark-cli available
command -v lark-cli >/dev/null 2>&1 || { echo "[planner-hook] lark-cli not installed; skip" >&2; exit 0; }

# 6. Send (best-effort; never fail)
HEADER="[planner@$PROJECT]"
BODY="$HEADER"$'\n'"$TEXT"
lark-cli im +messages-send --chat-id "$GROUP" --text "$BODY" 2>&1 | while IFS= read -r line; do
  echo "[planner-hook] $line" >&2
done || true

exit 0
```

## Deliverable 2 — `core/skills/planner/scripts/install_planner_hook.py`

新建。**镜像 `core/skills/memory-oracle/scripts/install_memory_hook.py`** 的结构，只改：
- 默认 hook script path: `scripts/hooks/planner-stop-hook.sh`
- 默认 workspace path: `~/.agents/workspaces/<project>/planner`
- 幂等写 `<workspace>/.claude/settings.json` `hooks.Stop`
- `--dry-run` 打印 JSON 不写

`--workspace <path>`, `--clawseat-root <path>`, `--dry-run`, `--hook-script <path>`（默认从 clawseat-root 推）。

## Deliverable 3 — 接进 install.sh

**不要改 install.sh 主流程**。改由 ancestor 的 Phase-A 在 B4 engineer seat 拉起时为 planner 调用一次。

改 `core/templates/ancestor-brief.template.md`：在 B3.5 澄清 provider + 拉起 planner seat 之后、进入下一个 seat 之前，加一行：

```
如果当前拉起的是 planner seat，跑：
  python3 core/skills/planner/scripts/install_planner_hook.py \
    --workspace ~/.agents/workspaces/${PROJECT_NAME}/planner \
    --clawseat-root ${CLAWSEAT_ROOT}
```

## Deliverable 4 — 清理 v0.5 legacy smoke

删或跳过：`tests/smoke/test_v05_install.sh` + `tests/test_v05_smoke.py`

原因：
- line 147 bash 语法 bug
- assertion 指向已删的 v0.5 名（`launch_ancestor` / `anthropic-console`）
- SMOKE-040 已证实这是衰退

推荐：**删两个文件**（v0.5 时代已过，SWEEP-023 遗漏）；或加 `@pytest.mark.skip(reason="legacy v0.5, removed in v0.7")` 保留 for 考古。你判断哪种保底。

## Deliverable 5 — 测试

`tests/test_planner_stop_hook.py` + `tests/test_install_planner_hook.py`（镜像 memory 对应测试，4-5 个 pytest）。覆盖：
- hook 读 stdin JSON + 截断 + feishu_group_id 缺失 silent skip + lark-cli 缺失 silent skip + PLANNER_STOP_HOOK_ENABLED=0 早退
- installer dry-run 不改文件 + 幂等 + 写 Stop hook 条目

## 验证

```bash
bash -n scripts/hooks/planner-stop-hook.sh
python3 -m py_compile core/skills/planner/scripts/install_planner_hook.py
pytest tests/test_planner_stop_hook.py tests/test_install_planner_hook.py -v
# 手动 smoke:
echo '{"last_assistant_message":"test","transcript_path":""}' | CLAWSEAT_PROJECT=smoketest bash scripts/hooks/planner-stop-hook.sh
# 期望: 要么打印 "[planner-hook] no PROJECT_BINDING.toml; skip" 要么 "no feishu_group_id"，rc=0
```

## Deliverable

`DELIVERY-PLANNERHOOK-041.md`：

```
task_id: PLANNERHOOK-041
owner: builder-codex
target: planner

## 改动清单
- scripts/hooks/planner-stop-hook.sh (N 行)
- core/skills/planner/scripts/install_planner_hook.py (N 行)
- core/templates/ancestor-brief.template.md (B3.5 加 hook install 行)
- tests/ ... (新增测试)
- 删/skip v0.5 legacy smoke

## Verification
<bash -n / pytest / 手动 smoke>

## Notes
<未解决项>
```

**不 commit**。
