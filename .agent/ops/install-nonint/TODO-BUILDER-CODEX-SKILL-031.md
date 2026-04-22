# TODO — SKILL-031 (SKILL.md v0.7 批量改写)

```
task_id: SKILL-031
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: REQUIRED — 4 parallel subagents (A/B/C/D) + 1 cleanup (E)
scope: 改 4 个 SKILL.md + 1 个 header 改
reference: .agent/ops/install-nonint/DELIVERY-SKILLSWEEP-032.md (逐条行号冲突)
```

## Context

SKILLSWEEP-032 已经给出**行级冲突清单**。这次任务按它的表逐条改。
不需要重新调研；**直接按 SKILLSWEEP-032 对照表改**。

**v0.7 核心范式**：
- operator ↔ ancestor = **CLI 直接交互**（主）
- 飞书 = **write-only 广播**（planner stop-hook，可选）+ **反向通道**（koder overlay，可选）
- `koder` = **OpenClaw 侧 agent** 的角色 overlay，**不是** ClawSeat seat，**不**在 install 关键路径
- OC_DELEGATION_REPORT_V1 = **当飞书启用时**的序列化格式，**不再**是"唯一 control packet"
- `UserPromptSubmit` 注入 `machine/` 5 文件的描述要改：hook 本身现已被证实是 dead pipe，machine/ 文件由 scan_environment.py 产出，memory 的新 **Stop-hook**（MEMORY-035 已交付）负责 `/clear` + auto-deliver

---

## Subagent A — `core/skills/clawseat-ancestor/SKILL.md` v0.7 改写

参考 SKILLSWEEP-032 §Subagent A (虽然原报告里 §A 是 clawseat-install；ancestor SKILL.md 分散在 AUDIT-027 + SKILLSWEEP-032 里，请综合处理):

1. **§2 Phase-A 表**：
   - 插入 **B1.5-env-scan** 步骤（15-20 行）：读 `~/.agents/memory/machine/*.json`，分析 harness / provider，向用户**CLI 交互式**推荐 + 确认；**不**走飞书 delegate report
   - 新增 **B2.5-bootstrap-tenants** 步骤：调用 `python3 core/scripts/bootstrap_machine_tenants.py ~/.agents/memory/` 把 agent 列表灌进 `~/.clawseat/machine.toml`
   - 修改 **B5-verify-feishu-binding**：从 "**halt Phase-A**" 改为 "如缺失则 **CLI prompt operator** 要 `feishu_group_id`；用户可 skip（CLI-only 模式）"——删除旧的 "不向 operator prompt（违反 N1）" 条款
   - 修改 **B6-smoke-dispatch**：从 "发 `OC_DELEGATION_REPORT_V1` 到群" 改为 "CLI 模式下验证本地 handoff；飞书模式下同时触发 planner 的一次 stop-hook 广播"
   - 修改 **B2/B3 失败处理**：从"Feishu 告警"改为"CLI stderr + 可选飞书广播（若 hook 配置）"
2. **§4 克隆项目**：
   - 整节**删除基于 `override_feishu_group_id` 的旧流程**
   - 新写法：调用 `agent_admin project bootstrap <name> --template default --local <path>` + `agent_admin project use <name>`
   - 不再要求 "same-group 禁止" 之类的飞书规则
3. **§5 通讯表**：
   - "我 → operator" 主通道从**飞书**改为 **CLI（tmux pane 直接对话）**；飞书降级为"可选异步广播（planner stop-hook 负责）"
   - "operator → 我" 从 "koder → planner → 我（间接）" 改为 "CLI 直接（tmux pane 粘贴 / 键入）"
4. **§8 决策表**：
   - 标记 "B5 不 prompt" 为 **superseded by v0.7**
   - 新增 "B3.5 逐个 CLI 澄清 provider" 决策

行数预算：当前 SKILL.md 大约 190 行；改后 200-220 行合理。

---

## Subagent B — `core/skills/clawseat-koder-frontstage/SKILL.md` v0.7 改写

参考 SKILLSWEEP-032 §Subagent B 的 10 条冲突。核心动作：

1. **L16**：`Lifecycle requests route: user → koder → planner → ancestor`
   → **改为**：`Lifecycle requests route: operator → ancestor via CLI. Koder is NOT in critical path.`
2. **L17, L27-33**：`chat_id → project` 路由
   → **改为**：`Project resolved via CURRENT_PROJECT env / CLI context; Feishu chat_id is not primary binding key.`
3. **L36-54（new-project intake via Feishu）**：
   → **删除整段**；新项目走 `agent_admin project bootstrap`
4. **L154-187（Planner Launch Follow-up）**：
   → **删除整段**；planner 初始化是 CLI-driven
5. **L188-222（Delegation Receipt Rule）**：
   → **改为**：`Optional — applies only when koder overlay is active. In CLI-only mode, delegation receipts go via state.db + handoff JSON, not Feishu envelopes.`
6. **L392-405（Heartbeat reception）**：
   → **改为**：`When koder overlay is active, post [HEARTBEAT_ACK] to Feishu group. In CLI-only mode, heartbeat ACK is written to state.db events instead.`
7. **L265-268（next-hop rule）**：
   → 保留但加注："在 v0.7 CLI-first 模式下，此规则是 koder 反向通道内部的 next-hop 规则，不约束 CLI-direct 的 operator↔ancestor 交互。"

**整体基调改写**：koder 不再是 "frontstage"，是 "optional Feishu reverse channel adapter"。整个文件的语气要改成"我是可选组件，运行时可能不启用"。

行数预算：当前 SKILL.md 大约 480 行；改后 380-420 行（删的多于加的）。

---

## Subagent C — `core/skills/memory-oracle/SKILL.md` v0.7 改写

参考 SKILLSWEEP-032 §Subagent C（memory-oracle 部分）+ MEMORY-035 交付。

1. **L17**：`UserPromptSubmit hook 已注入 machine/ 5 文件 + 当前 project dev_env.json`
   → **改为**：`scan_environment.py 产出 machine/ 5 文件（credentials/network/openclaw/github/current_context）；memory seat 启动时由 install.sh 同步调用。memory 运行时可按需 re-scan。`
   → 删除老 dead-pipe UserPromptSubmit 引用
2. **L43-48（[CLEAR-REQUESTED] watcher 依赖外部 orchestrator）**：
   → **改为**：`memory seat 的 Claude Code Stop-hook（scripts/hooks/memory-stop-hook.sh，MEMORY-035）监听本轮输出：
   - 发现 [CLEAR-REQUESTED] → 外部 shell 向 tmux 发送 /clear（外部 shell 敲的 /clear 会被 Claude Code 执行）
   - 发现 [DELIVER:seat=<X>] + task_id / profile → 自动调 memory_deliver.py 回执`
   → 注明：hook 已在 v0.7 落地，不再是"待外部 orchestrator 实现"
3. 保留所有 M1 / M2 scanner 说明和查询协议；那些是正确的
4. 若有"必须 planner 代发飞书"的措辞（应该没有，但检查一下），改为中立的"通过 complete_handoff / memory_deliver 交付"

行数预算：当前 81 行；改后 85-95 行。

---

## Subagent D — `core/skills/gstack-harness/SKILL.md` v0.7 改写

参考 SKILLSWEEP-032 §Subagent C（gstack-harness 部分）的 5 条冲突。核心：

1. **L45-46（Feishu delegation report 作为主 wake-up 通道假设）**：
   → **改为**：`Feishu delegation report 是其中一种可选 transport；当 koder overlay 未启用时，operator 直接在 ancestor/planner tmux pane CLI 交互。`
2. **L86-87, L95-97（`CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST` 唯一广播路径）**：
   → **改为**：`广播协议是通用的；Feishu group broadcast 是可选 transport 之一。v0.7 新增 planner stop-hook 结构化摘要广播作为主路径。`
3. **L99-101（OC_DELEGATION_REPORT_V1 + Feishu 是唯一 delegation 路径）**：
   → **改为**：`OC_DELEGATION_REPORT_V1 是 Feishu-side 的一种序列化格式；同样的 delegation 信息在 CLI-only 模式下通过 handoff JSON + state.db events 表达。`
4. **L220-222（Feishu user-message 是唯一 bypass 路径）**：
   → **改为**：`Feishu bypass 路径**仅当 koder overlay 启用时可用**。CLI-only 模式下无此路径，直接 CLI 交互或用 agent_admin CLI。`

行数预算：基本不变，只改措辞。

---

## Subagent E — `core/skills/clawseat-install/SKILL.md` header 清理

参考 SKILLSWEEP-032 §Subagent A (这部分是 clawseat-install 的)。小改：

1. **L3**：`v0.5 agent-driven flow` → `v0.7 CLI-first flow`
2. **L6**：`## ClawSeat Install (v0.5 — agent-driven)` → `## ClawSeat Install (v0.7 — CLI-first)`
3. **L68-74**：koder = Feishu frontstage → koder = OpenClaw-side Feishu reverse channel adapter (optional post-install overlay)
4. **L76, L78-84**：在 Subagent mode 段加一句："For 5 engineer seats provider clarification, must be done one-by-one via CLI prompt, never via Feishu delegate report."
5. **L90-105 "What to NOT do"**：加两条
   - "Do NOT use Feishu delegate report (OC_DELEGATION_REPORT_V1) as primary channel for seat provider clarification."
   - "Do NOT use Feishu chat_id as project identifier — use `agent_admin project bootstrap/use`."

行数预算：基本不变。

---

## 产出（全任务一次性交付）

`DELIVERY-SKILL-031.md`：

```
task_id: SKILL-031
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## Subagent A — clawseat-ancestor/SKILL.md
<改动 diff 摘录 + 行数变化>

## Subagent B — clawseat-koder-frontstage/SKILL.md
<改动 diff 摘录 + 行数变化>

## Subagent C — memory-oracle/SKILL.md
<改动 diff 摘录>

## Subagent D — gstack-harness/SKILL.md
<改动 diff 摘录>

## Subagent E — clawseat-install/SKILL.md header
<改动 diff 摘录>

## Verification
- 每个文件过一遍 markdown linter / 目视检查
- 没有残留 "v0.5" / "koder=frontstage" / "OC_DELEGATION_REPORT_V1 is primary" 字样（grep 验证）

## Notes
<未解决项>
```

**不 commit，留给 planner 审**。
