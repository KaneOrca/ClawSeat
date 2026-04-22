# TODO — MEMORY-035 (memory seat Stop-hook：自 /clear + 自动回执)

```
task_id: MEMORY-035
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P1
queued: YES — 先完成 SCAN-034 再做
subagent-mode: OK (2 subagent：A=hook 脚本 + 安装，B=测试)
scope: 新增 1 个 shell + 1 处 python 改动 + 测试
```

## Context

AUDIT-027 已确认：memory SKILL.md 说每轮轮末应 `/clear`，但：
- 模型 output `/clear` 文本**不被 Claude Code 执行**（slash-cmd 只认用户键入）
- 实际没有任何 watcher / hook 监听 `[CLEAR-REQUESTED]` 标记
- 因此 memory 积累 context，跑几轮后失准

**解决方案**：给 memory 的 Claude Code settings.json 配 **Stop-hook**。Stop-hook 是**外部 shell** 敲的 `/clear`，属于"用户键入"范畴，Claude Code 认账。

同时顺便做：Stop-hook 也可检测 `[DELIVER:seat=<X>]` 标记，自动调 `memory_deliver.py` 把本轮产出投递给请求 seat，不再靠 memory 自己记得调。

## Subagent A — hook 脚本 + 安装

### A.1 — `scripts/hooks/memory-stop-hook.sh`（新建）

```bash
#!/usr/bin/env bash
# Memory seat Stop-hook. 运行在 memory 本轮结束之后。
# 输入：Claude Code 传入 transcript（stdin 或 ${CLAUDE_TRANSCRIPT_FILE}）
# 行为：
#   1. 若发现 [CLEAR-REQUESTED] 标记 → tmux send-keys /clear 给自己
#   2. 若发现 [DELIVER:seat=<X>] 标记 → 调 memory_deliver.py 投递给 <X>
set -euo pipefail

TRANSCRIPT_FILE="${CLAUDE_TRANSCRIPT_FILE:-/dev/stdin}"
SESSION_NAME="${TMUX_SESSION_NAME:-machine-memory-claude}"
CLAWSEAT_ROOT="${CLAWSEAT_ROOT:-$HOME/ClawSeat}"

# Read transcript (Claude Code 规范待确认——可能是 file path 或 stdin JSON)
CONTENT=$(cat "$TRANSCRIPT_FILE" 2>/dev/null || true)
[ -z "$CONTENT" ] && exit 0

# 1) Self /clear
if grep -q '\[CLEAR-REQUESTED\]' <<< "$CONTENT"; then
  sleep 0.5  # 让 Claude Code 完全 settle
  env -u TMUX tmux send-keys -t "$SESSION_NAME" "/clear" Enter 2>/dev/null || true
fi

# 2) Auto-deliver
while IFS= read -r LINE; do
  if [[ "$LINE" =~ \[DELIVER:seat=([a-zA-Z0-9_-]+)([^]]*)\] ]]; then
    TARGET="${BASH_REMATCH[1]}"
    python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/memory_deliver.py" \
      --to "$TARGET" --from memory --transcript "$TRANSCRIPT_FILE" 2>&1 \
      | while IFS= read -r L; do echo "[memory-hook] $L" >&2; done || true
    break  # 只投递一次
  fi
done <<< "$CONTENT"
```

**要点**：
- `set -euo pipefail` 但后面用 `|| true` 兜底（不能让 hook 失败阻塞 Claude Code 关闭）
- `env -u TMUX` 避免 nested tmux 混乱
- 前置 sleep 0.5 防止跟 Claude Code 自己的 settle 流程撞
- `memory_deliver.py` 的 `--transcript` 参数可能需要补（看脚本当前签名决定）

### A.2 — 安装流程：`init_memory_hook.py` 或改 `init_koder.py`

找出 memory seat 的 Claude Code workspace 路径（通常 `~/.openclaw/workspace-<memory-agent>/.claude/` 或 memory seat 自己的 `~/.claude/` 目录），在 `settings.json` 里注入：

```json
{
  "hooks": {
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "bash /path/to/clawseat/scripts/hooks/memory-stop-hook.sh",
        "timeout": 10
      }]
    }]
  }
}
```

改造点候选：
- 如果 memory 也走 `init_koder.py` 初始化：在其中加 `--install-stop-hook` flag
- 否则新建 `core/skills/memory-oracle/scripts/install_memory_hook.py`

**优先新建**，避免 init_koder.py 语义漂移。

### A.3 — Claude Code Stop hook 的真实协议

我（planner）不 100% 确定 Claude Code Stop hook 的 stdin / env var 协议。你先查：
1. `~/.claude/settings.json` 示例里 UserPromptSubmit hook 的 `command` 签名
2. Claude Code 官方文档 Stop hook 的 transcript 传递方式
3. 现有 `/Users/ywf/.pixel-agents/hooks/claude-hook.js` 看 UserPromptSubmit 是怎么读数据的（可能给 Stop hook 做参考）

实现时尊重实际协议，不要臆测。

---

## Subagent B — 测试

`tests/test_memory_stop_hook.py`：

```python
# 1) Mock transcript with [CLEAR-REQUESTED] → verify tmux send-keys被调用
# 2) Mock transcript with [DELIVER:seat=planner] → verify memory_deliver.py 被调
# 3) Mock transcript without 任何 marker → hook 静默退出 rc=0
# 4) Mock tmux 失败 → hook 不应非零退出（兜底 || true）
```

用 `subprocess` + mock 包装 tmux / python 实际命令。

---

## Deliverable

`DELIVERY-MEMORY-035.md`：

```
task_id: MEMORY-035
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## 改动清单
- scripts/hooks/memory-stop-hook.sh (新建, N 行)
- <install script>
- tests/test_memory_stop_hook.py (新建, N 行)

## Claude Code Stop hook 协议调研结论
<transcript 怎么传 / env vars>

## Verification
<bash -n / pytest / 手动触发 hook 看行为>

## 已知限制
<没覆盖 / 需要 SKILL-031 配合改 SKILL.md 的部分>
```

**不 commit，留给 planner 审。**
