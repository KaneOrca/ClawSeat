# TODO — DEADREF-036 (残留硬编码路径扫描)

```
task_id: DEADREF-036
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P2
subagent-mode: OPTIONAL (小任务，可单 agent)
do-not-modify: read-only
```

## Context

SWEEP-023 删除了 `core/skills/agent-monitor/` 整个目录，其中包含副本 `core/skills/agent-monitor/script/send-and-verify.sh`。
主本 `core/shell-scripts/send-and-verify.sh` 仍存在。

担心：有其他脚本 / Python / 文档硬编码了已删的副本路径，SWEEP 没检测到，运行时会 FileNotFoundError。

## 任务

全仓扫残留引用。

```bash
cd /Users/ywf/ClawSeat

# 1) send-and-verify.sh 旧副本
grep -rln "agent-monitor/script/send-and-verify\|skills/agent-monitor/script" \
  --include="*.py" --include="*.sh" --include="*.md" --include="*.toml" --include="*.json" \
  --include="*.yaml" --include="*.yml" . 2>/dev/null

# 2) 其他 SWEEP-023 删掉的路径（参考 DELIVERY-SWEEP-023.md 删除列表）
# 如果 DELIVERY-SWEEP-023.md 有具体删除清单，逐一 grep
cat .agent/ops/install-nonint/DELIVERY-SWEEP-023.md | head -60

# 3) screenshot-to-feishu.sh（同批被删）
grep -rln "screenshot-to-feishu" --include="*.py" --include="*.sh" --include="*.md" . 2>/dev/null
```

## 产出

写 `DELIVERY-DEADREF-036.md`：

```
task_id: DEADREF-036
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话：N 处残留 / 0 处残留>

## 扫描结果
- 命中文件清单（路径 + 行号 + 原文摘录）
- 对每条命中判断：
  - A) 真死引用（代码/脚本会在运行时炸）
  - B) 文档引用（只是提到，不会运行时炸，但可能误导）
  - C) 误报（通配符匹配到别的）

## 建议
- A 类必须修（列具体文件 + 应改成什么）
- B 类建议 planner 顺便清（在 docs 重写时扫）
- C 类忽略
```

发现 0 处残留就说"clean"结案。

完成后通知 planner: "DELIVERY-DEADREF-036 ready"。
