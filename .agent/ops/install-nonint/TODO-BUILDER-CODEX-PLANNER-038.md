# TODO — PLANNER-038 (新建 core/skills/planner/SKILL.md)

```
task_id: PLANNER-038
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
queued: YES — WIRE-037 完成后再跑
subagent-mode: OPTIONAL (单 agent 即可，或 2-split 给更快)
scope: 1 个新文件 ≈150-180 行
```

## Context

AUDIT-027 已发现：**planner 没有专属 SKILL.md**（所有其他 seat 都有）。职责散落在 `gstack-harness/SKILL.md`、`clawseat-ancestor/SKILL.md`、`core/templates/gstack-harness/template.toml` 的 role_details。

planner 作为 **dispatch / consumption / merge hub**，单轮输出典型 2-3k 字符，上下游关系清晰。SKILL-031 已完成 ancestor / koder / memory / gstack 四个 SKILL.md 的 v0.7 改写；这次只建 planner 新的。

参考（已决策）：
- **v0.7 新范式**：operator ↔ ancestor = CLI 直接；planner 不直接接 operator
- **Fan-out OK**：planner 允许并发派多个 specialist（不强制串行）
- **决策阻塞瀑布**：planner hook → feishu → koder 尽量自决 → 不行则问用户（feishu）；feishu 不通时 fallback 给 ancestor；ancestor 不能决策时再问用户（CLI）
- **不持有 `active_loop_owner` 状态**：v0.7 删这个概念，planner 天然是唯一规划者
- **memory 交互只读**：planner 不写 memory，memory 自己定时巡检日志提炼
- **escalation → ancestor**：severe failure / seat_needed 都走 ancestor
- **stop-hook 广播**：每轮发**结构化摘要**（不是原始 transcript）到 feishu group，≤500 字，L1c 头尾保留兜底

## Deliverable — `core/skills/planner/SKILL.md`

### YAML 头

```yaml
---
name: planner
description: Dispatch / consumption / merge hub for ClawSeat chains. Owns dispatch_authority for builder/reviewer/qa/designer; does not own seat lifecycle or operator CLI surface.
---
```

### 10 节结构（目标行数）

1. **Identity / 身份约束** ≈15 行
   - planner = 唯一规划 + 编排 seat
   - 不直接接 operator（operator ↔ ancestor 是唯一 CLI 通道）
   - 不启动 / 删除 seat（ancestor 专属）
   - 不改项目配置 / profile / machine.toml
   - 不写 memory workspace
   - 不持有 active_loop_owner 状态（v0.7 删除）

2. **Upstream (任务入口)** ≈10 行
   - ancestor → planner via `tmux send-keys` + handoff JSON（`~/.agents/tasks/<project>/patrol/handoffs/`）
   - 读 `TODO.md` (planner inbox)
   - 不订阅飞书（若需要 operator 远程指令，走 koder 反向通道）
   - memory 查询只读（`query_memory.py`）

3. **Dispatch — 派 4 specialist** ≈25 行
   - `dispatch_task.py --profile ... --source planner --target <seat> --task-id <id> --title ... --objective ... --reply-to planner`
   - 可派 seats: `builder`（含 `builder-N`）/ `reviewer`（含 `reviewer-N`）/ `qa` / `designer`
   - **允许 fan-out**: 同一 chain 可同时派多个 specialist
   - notify 默认 ON（C15）
   - review-gate: 修改 code/docs/templates 必走 `builder → reviewer`
   - `--target-role <role>` + state.db `pick_least_busy_seat` 做 fan-out 调度

4. **Consumption / Merge** ≈20 行
   - `complete_handoff.py` 收 specialist 完成
   - 写 `DELIVERY.md`（planner inbox）
   - 标 `Consumed:` ACK 到 handoff receipt
   - 合并多 lane 摘要为 chain 级 delivery
   - 回 ancestor：`complete_handoff --target ancestor --source planner`

5. **Decision blocking (waterfall)** ≈20 行
   ```
   planner 需要 user 决策时
     → stop-hook 已发结构化摘要到 feishu group（每轮都发）
     ├─ [feishu OK & koder overlay 已装]
     │    koder 尽可能自己决策（读 context + history）
     │       不能 → koder 向 user 问（feishu）
     │          user 回复 → koder → tmux send-keys planner
     └─ [feishu 不通 / koder 未装]
          planner handoff → ancestor
             ancestor 调研（查 memory / logs）
                不能 → ancestor 问 user（CLI pane）
                   user 回复 → ancestor → tmux send-keys planner
   ```
   - **禁止** planner 自己直接 CLI prompt user（user 不 attach planner pane）
   - **禁止** planner 订阅 feishu 读 user 回复

6. **Broadcast (stop-hook)** ≈25 行
   - 每轮结束触发 `scripts/hooks/planner-stop-hook.sh`（未来任务实现）
   - hook 从 transcript 提取**结构化字段**：
     - `action` (e.g. "dispatched TASK-001 to builder-1")
     - `target` (e.g. "builder-1")
     - `UserSummary` (e.g. DELIVERY.md 的 UserSummary 行)
     - `next_action` (e.g. "await delivery")
   - 格式：`[planner@<project>] turn <N>: <action>\nnext: <next_action>`（≤500 字）
   - 发 feishu group via `lark-cli msg send`
   - 无 `feishu_group_id` 时静默 skip（CLI-only 模式）
   - 超 20000 字符（罕见）走 L1c 头尾保留 fallback

7. **Error / Escalation** ≈15 行
   - `seat_needed` (rc=3): 目标 specialist 不在 → 报 ancestor via handoff + stderr
   - 软失败: 重试 N 次（默认 3）+ 指数回退
   - 重度失败: escalate → ancestor（`complete_handoff --status blocked --target ancestor`）
   - **不** escalate 给 koder（v0.7 koder 不在 lifecycle 链上）

8. **Memory interaction (read-only)** ≈10 行
   - 查询: `query_memory.py --project <p> --kind decision|finding|...`
   - 注入: install-time UserPromptSubmit hook 已注入 `machine/*.json`（若配置）
   - **不调** `memory_write.py` — memory 自管知识提炼（通过定时巡检 events.log）

9. **Hard rules / 禁止清单** ≈15 行
   - ❌ 不运行 `start_seat.py` / `agent-launcher.sh`
   - ❌ 不直接派给 specialist 跳过 planner（builder → builder 禁止）
   - ❌ 不改 project config / profile / seats
   - ❌ 不接收 operator 飞书消息（koder 专属）
   - ❌ 不自己跑巡检 / heartbeat（ancestor / memory patrol）
   - ❌ 不 fan-out 工程任务给自己
   - ❌ 不写 memory workspace
   - ❌ 不持有 `active_loop_owner` 状态

10. **Environment variables** ≈10 行
    参考 `clawseat-ancestor/SKILL.md §7` 格式：

    | 变量 | 默认 | 作用 |
    |------|------|------|
    | `PLANNER_PROFILE` | `~/.agents/profiles/<project>-profile.toml` | profile 路径 |
    | `PLANNER_STOP_HOOK_ENABLED` | `1` | 关闭则跳过飞书广播 |
    | `PLANNER_MAX_FAN_OUT` | `4` | 同 chain 最大并发 specialist 数 |
    | `CLAWSEAT_ROOT` | `$HOME/ClawSeat` | repo 路径 |

## 约束

- **参考风格**：读 `core/skills/clawseat-ancestor/SKILL.md`（SKILL-031 刚更新为 v0.7 版本），保持 Phase / 通讯表 / 禁止清单的格式一致
- **行数预算**：150-200 行。超 220 则删冗余。
- 不要重复 ancestor SKILL.md 里已覆盖的内容（Phase-A 是 ancestor 的事，planner 只说自己）
- 引用现有 helper 脚本时用真实路径（`core/skills/gstack-harness/scripts/dispatch_task.py` 等）

## Verification

- `markdownlint` 若本机可用则跑
- Grep 验证：
  - 不含 `v0.5` / `v0.4` / `active_loop_owner` 正面定义
  - 不含 `koder → planner → ancestor` 路由链
  - 不含 `OC_DELEGATION_REPORT_V1 is primary`

## Deliverable

`DELIVERY-PLANNER-038.md`：

```
task_id: PLANNER-038
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## 改动
- core/skills/planner/SKILL.md (新建, N 行)

## Verification
<grep / 目视 / 渲染>

## Notes
<未解决项>
```

**不 commit，留给 planner 审**。
