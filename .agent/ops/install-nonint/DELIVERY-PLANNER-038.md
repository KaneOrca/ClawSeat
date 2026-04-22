task_id: PLANNER-038
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 已新建 planner 专属 SKILL.md，收口到 v0.7 CLI-first 模型下的 dispatch / merge / escalation / stop-hook contract。

## 改动

- `core/skills/planner/SKILL.md`（新建，192 行）

文件结构按 TODO 的 10 节落地：

1. Identity / 身份约束
2. Upstream（任务入口）
3. Dispatch（派 4 类 specialist）
4. Consumption / Merge
5. Decision Blocking（瀑布式决策回路）
6. Broadcast（planner Stop-hook）
7. Error / Escalation
8. Memory Interaction（read-only）
9. Hard Rules / 禁止清单
10. Environment Variables

核心语义：

- planner 是唯一规划 + 编排 seat
- operator 只能经 ancestor 触达 planner，planner 不直接接 operator
- planner 不碰 lifecycle / profile / machine config / memory workspace
- specialist 支持 fan-out，planner 负责最终 merge
- 决策阻塞走 waterfall：stop-hook 摘要 -> optional koder overlay -> ancestor -> operator CLI
- Feishu 只是 optional broadcast，不是 planner 的主控制通道

## Verification

- 行数检查：
  - `wc -l core/skills/planner/SKILL.md` -> `192`
- grep 检查：
  - 不含 `v0.5`
  - 不含 `v0.4`
  - 不含 `active_loop_owner`
  - 不含 `koder -> planner -> ancestor`
  - 不含 `OC_DELEGATION_REPORT_V1 is primary`
- `markdownlint`
  - 本机不可用：`NO_MARKDOWNLINT`
- 目视检查：
  - 结构、语气、表述边界已对齐 `clawseat-ancestor/SKILL.md` 的 v0.7 风格

## Notes

- 这次只新建了 skill 文件，没有顺手改 `core/skill_registry.toml` / `manifest.toml` 做 wiring。
- stop-hook 路径 `scripts/hooks/planner-stop-hook.sh` 目前作为 contract 写入 skill，本任务没有实现该脚本。
- 未 commit。
