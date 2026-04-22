task_id: SKILL-031
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 已把 4 个目标 SKILL.md 收口到 v0.7 CLI-first 语义，并完成 clawseat-install header 清理；WIRE-037 未触碰。

## Subagent A — clawseat-ancestor/SKILL.md

- 行数变化：`193 -> 200`
- 关键改动：
  - Phase-A 表重写为 v0.7 checklist，加入 `B1.5-env-scan`、`B2.5-bootstrap-tenants`、`B3.5-clarify-providers`
  - `B5` 改为 CLI prompt / skip `feishu_group_id`
  - `B6` 改为本地 handoff smoke + 可选 planner stop-hook 广播
  - `B2/B3` 失败处理改为 `stderr + optional broadcast`
  - 项目入口改成 `agent_admin project bootstrap/use`
  - 通讯表改成 `operator <-> ancestor` CLI-direct primary
- 额外主线程修正：
  - 把 `CLAWSEAT_ROOT` 默认值从错误的 `~/.clawseat` 改回 repo-root 语义
  - 把头部描述里的“Phase-A 7 步”改成 expanded checklist，避免和 `.5` 子步自相矛盾

## Subagent B — clawseat-koder-frontstage/SKILL.md

- 行数变化：`0 -> 79`（当前 `HEAD` 已被 `dfadb69` 删除；本任务按 TODO 显式回补为 slim v0.7 skill）
- 关键改动：
  - 重写为 **optional Feishu reverse-channel adapter**
  - 生命周期主链明确为 `operator -> ancestor` via CLI；`koder` 不在 critical path
  - 项目标识改为 `CURRENT_PROJECT` / active CLI context / adapter resolution；`chat_id` 仅为 transport metadata
  - 删除旧的 Feishu new-project intake / planner follow-up / receipt-heavy frontstage 语义
  - `OC_DELEGATION_REPORT_V1` 仅保留为 overlay-on 时的 machine receipt 格式
  - heartbeat ACK 改为 overlay-on 才发 Feishu；overlay-off 走 `state.db` / CLI receipt
- 说明：
  - 子 agent 最初把文件写到了 `/Users/ywf/coding/ClawSeat`；主线程已把最终内容落到目标 repo `/Users/ywf/ClawSeat`

## Subagent C — memory-oracle/SKILL.md

- 行数变化：`80 -> 131`
- 关键改动：
  - 删除旧的 `UserPromptSubmit` / dead-pipe 说法
  - 改成 `scan_environment.py` 产出 `machine/{credentials,network,openclaw,github,current_context}.json`
  - 明确 v0.7 install 路径会由 `scripts/install.sh` 同步调用一次 env scan
  - 新增已落地的 Stop-hook 说明：`scripts/hooks/memory-stop-hook.sh`
  - 写清 `[CLEAR-REQUESTED]` 与 `[DELIVER:seat=<X>]` 的实际行为
  - 保留 M1/M2 scanner、query protocol、`memory_deliver.py` / `complete_handoff.py` 的中性交付口径

## Subagent D — gstack-harness/SKILL.md

- 行数变化：`250 -> 273`
- 关键改动：
  - 把 transport 总述改成 `CLI-first transport plus optional async adapters`
  - `Feishu delegation report` 改成仅在 koder overlay / Feishu-side async sink 激活时才需要加载
  - `dispatch_task.py` / `complete_handoff.py` 文案统一改成 durable `handoff JSON + state.db events` 为主事实链
  - `send_delegation_report.py` 改成 Feishu-side async path only；`OC_DELEGATION_REPORT_V1` 不再是 primary / only packet
  - bypass 规则改成：Feishu bypass 仅当 overlay 激活；CLI-only 模式走 CLI / handoff / `state.db`
  - closeout 主语从 `koder` 改成 `active frontstage`

## Subagent E — clawseat-install/SKILL.md header

- 行数变化：`124 -> 133`
- 关键改动：
  - 头部 description / title 从 `v0.5 agent-driven` 改到 `v0.7 CLI-first`
  - 把 `koder` 定位改成 optional OpenClaw-side Feishu reverse channel adapter / async notification sink
  - `Subagent mode` 增加五个 engineer seats 必须逐个 CLI 澄清 provider，不能走 Feishu delegate report
  - `What to NOT do` 新增两条禁令：
    - 不要用 `OC_DELEGATION_REPORT_V1` 作为 provider clarification 主通道
    - 不要用 Feishu `chat_id` 作为 project identifier；改用 `agent_admin project bootstrap/use`

## Verification

- 目视检查：已逐个复核 5 个目标文件的头部、核心段落和关键表格
- `markdownlint`：本机未安装（`NO_MARKDOWNLINT`），因此未跑 linter
- grep 验证：
  - 5 个目标文件无残留 `v0.5`
  - 无残留 `user -> koder -> planner -> ancestor`
  - 无残留 `resolve_project_from_chat_id`
  - 无残留 `Planner Launch Follow-up`
  - 无残留 `Feishu Delegation Receipt Rule`
  - `memory-oracle/SKILL.md` 无残留 `UserPromptSubmit`
  - `override_feishu_group_id` 仅在 `clawseat-ancestor/SKILL.md` 中作为“旧流程退场说明”保留，不再作为现行流程
- git 状态（目标集合）：
  - `M core/skills/clawseat-ancestor/SKILL.md`
  - `?? core/skills/clawseat-koder-frontstage/SKILL.md`
  - `M core/skills/memory-oracle/SKILL.md`
  - `M core/skills/gstack-harness/SKILL.md`
  - `M core/skills/clawseat-install/SKILL.md`

## Notes

- 本任务未 commit。
- `WIRE-037` 保持 queued，未开始。
- 当前 repo 的 `core/skill_registry.toml` / `manifest.toml` 仍未重新挂回 `clawseat-koder-frontstage`；本任务按 TODO 只处理 SKILL.md 文本，不扩到 wiring。
