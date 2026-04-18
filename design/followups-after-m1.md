# Follow-ups After Memory Seat v3 M1

**Status**: 设计阶段，只记录，**不实施**。待 M1 整体 closeout 后，由 koder 统一派发各修复任务。

**Origin**: 2026-04-18 Phase 7 环境全流程测试期间，M1 任务链执行过程中暴露出来的 bug / 协议漏洞 / 文档债务。

---

## 优先级说明

- **P0** — 立即威胁（重启会崩 / 正确性 / 安全）
- **P1** — 系统性破洞（高频踩 / 链路静默失败）
- **P2** — 可容忍但会累积（认知层不一致 / 文档膨胀）

---

## 11 条 Follow-ups

### 1. send-and-verify.sh retry 升级

**发现**: 当前 retry 只重发 1 次 Enter，sleep 2s。对高频繁忙 TUI 或并发 send 的场景保护不足。

**修复**:
- retry 上限 3 次，sleep 指数退避（2s / 4s / 8s）
- 每次 retry 发 `Enter Enter`（连发两次）
- 失败日志补 `"prior_pane_may_be_busy_or_modal"` 提示

**文件**: `core/shell-scripts/send-and-verify.sh`

**优先级**: P1

---

### 2. require_success 异常传播审计

**发现**: builder-1 在裸 `tmux send-keys` 失败（退出码 2 / 输出 `sent`）后继续跑。需审计所有调用 `require_success(result, "completion notify")` 的路径，确认异常未被静默吞。

**修复**:
- grep 所有 `require_success` / `result.returncode` 检查点
- 确认失败路径 raise 后不被 except 捕获
- 在 build-phase 加 assert：notify 失败 → 整个 complete_handoff.py 非零退出

**文件**: `core/skills/gstack-harness/scripts/complete_handoff.py`，`core/skills/gstack-harness/scripts/_utils.py`

**优先级**: P1

---

### 3. builder-1 M5 scope creep 观察 — 审查 path 常量合法性

**发现**: Bundle-B 的 builder-1 提前加了 `reflections_path()` 和 `events_log_path()` 路径常量到 `_memory_paths.py`。这些是 M5 (events.log 钩子) 的依赖。理由"为 M5 预留 import 注册"可辩论。

**修复**:
- reviewer-1 的 canonical review 明确仲裁：**允许 path 常量但禁止写入逻辑**
- 若仲裁保留，在 `_memory_paths.py` 注释里写明"M5 will add write hooks"
- 若仲裁拒绝，回滚这部分 diff，M5 时重新加

**文件**: `core/skills/memory-oracle/scripts/_memory_paths.py`

**优先级**: P2 (reviewer 最终仲裁)

---

### 4. Sandbox HOME vs real HOME 的 receipt 不可见

**发现**: planner / specialist 在各自 sandbox HOME 写 receipt，bash（或 koder 在 OpenClaw 侧）读 real HOME 看不到。已出现 2 次：
- `resolve_primary_feishu_group_id` 因 sandbox HOME `.lark-cli/config.json` 假阳性（已修 73885b6）
- 本次 dispatch receipt 都在 sandbox HOME，bash traceability 丢失

**修复候选**:
- **A**. dispatch_task / complete_handoff 写 receipt 时同时写 real HOME + sandbox HOME
- **B**. bootstrap 时把 sandbox HOME 的 `.agents/tasks/` 通过 symlink 指向 real HOME
- **C**. patrol 专有脚本聚合各 sandbox HOME 的 receipt → real HOME

**推荐**: B (最少脚本改动，一次 bootstrap 配好)

**文件**: `core/skills/gstack-harness/scripts/bootstrap_harness.py`

**优先级**: P1

---

### 5. complete_handoff.py 加 `--user-summary` 富文本参数

**发现**: canonical `complete_handoff.py` 的消息模板只有 `{task_id} complete from {src} to {tgt}. Read {delivery_path}...`。specialist 想在通知里带富文本（如 "10 tests green, commit 9370bb8, F1-writer done"），当前模板承载不下 → 绕道裸 `tmux send-keys`（见 #6）。

**修复**:
- `complete_handoff.py` 加 `--user-summary "text"` 参数
- `build_completion_message` 在 canonical 消息后追加 `\n\nSummary: {user_summary}` 块
- send-and-verify.sh 的 `\n` 处理保持单次提交（不拆 Enter）

**文件**: `core/skills/gstack-harness/scripts/complete_handoff.py`, `core/skills/gstack-harness/scripts/_task_io.py`

**优先级**: P0（堵死 #6 的根本动机）

---

### 6. Specialist role_details 硬化 — 禁止裸 tmux send-keys

**发现**: 本链路中 builder-1 **3 次违反**自己 AGENTS.md 第 62 行的规则，用裸 `tmux send-keys` 发富文本 FYI 给 planner，且**每次都忘了发 Enter**，造成 planner 输入框卡住（靠 reviewer-1 的后续 canonical send 的 Enter 误救）。

规则原文："treat raw `tmux send-keys` as a protocol violation unless the transport script is unavailable" —— **"unless unavailable"措辞被 builder-1 误读**为"已用过 transport 一次后可以 bonus 裸发"。

**修复**:
- template.toml 的 specialist role_details 硬化："**NEVER use raw `tmux send-keys` to notify peer seats. Full stop.** Rich detail must go through `complete_handoff.py --user-summary` (see followup #5) or embed in `DELIVERY.md` content."
- 去掉"unless unavailable"模糊表述

**文件**: `core/templates/gstack-harness/template.toml`

**优先级**: P0（与 #5 并发推，二者互为完整修复）

---

### 7. reviewer 审查清单加一条 — flag raw tmux send-keys 使用

**发现**: builder-1 的违规行为理论上应被 reviewer-1 捕获。但 reviewer-1 的审查清单里没显式"检查 bash 调用日志是否有裸 tmux"项目。需多一道守门。

**修复**:
- reviewer 的审查清单（SKILL.md 或 role_details）加一条："**在 bash 调用日志 / PR diff 中搜 `tmux send-keys`，如果来自 specialist 且 target 不是自己的 session，flag 为协议违规**"
- 违规样本应 verdict = `CHANGES_REQUESTED`，fix 要求改走 complete_handoff.py

**文件**: `core/skills/gstack-review/SKILL.md`（gstack skill 级别），`core/templates/gstack-harness/template.toml`（reviewer role_details）

**优先级**: P1

---

### 8. send-and-verify.sh 检测"prior_stuck_input"预清理

**发现**: 当 pane 输入框已有裸 tmux 残留的未提交文本时，新的 send-and-verify 会把自己的文本拼在后面，Enter 提交**混合消息**。已在本链路出现：fix2 DELIVERY (builder 裸) + rev3 complete (reviewer canonical) 拼接提交给 planner。

**修复**:
- send-and-verify.sh 发送前先 `capture_tail`，如果输入行已有非空内容 → 先按一次 Enter 清理 → 再 send
- 记录日志 `"prior_stuck_input_detected_cleaned"`，便于 patrol 追溯有多少次触发（量化 #6 的频率）

**文件**: `core/shell-scripts/send-and-verify.sh`

**优先级**: P1

---

### 9. agent_admin_crud.engineer_create 必须更新 profile

**发现**: `engineer_create` 创建 tmux + workspace + session.toml + identity 目录，但**不更新 profile 的 `seats` / `materialized_seats` / `seat_roles` / `seat_overrides`**。创建完的 seat 可以跑但 dispatch_task 永久拒（`profile.seats` 白名单检查）。本链路 qa-1 block 的 root cause 就是这个。

**修复**:
- `engineer_create` 里新增一步：读 profile TOML → append seat 名到四个字段 → 写回
- `[seat_overrides.<seat>]` 块用 session.toml 的 tool/auth/provider/model
- idempotent：如果 seat 已存在于 profile，跳过

**文件**: `core/scripts/agent_admin_crud.py`

**优先级**: P0（是本次链路唯一阻塞点的根源）

---

### 10. planner AGENTS.md 拆 TOOLS/\*.md

**发现**: planner AGENTS.md 210 行，单文件常驻上下文。内容混杂 intent dispatch / Feishu 规则 / seat lifecycle / verdict 协议 / handoff 协议 / Consumed ACK / scope creep / mid-chain decision push。每轮对话都塞 210 行。

**修复** (参考 koder e76eb81 commit 的拆分模式):
- AGENTS.md 压到 <100 行（核心身份 + quick reference）
- `TOOLS/intent.md` — intent table + 触发词清单
- `TOOLS/handoff.md` — receipt / verdict / ACK 格式
- `TOOLS/feishu.md` — decision-gate push 规则
- `TOOLS/seat-lifecycle.md` — seat 创建/重启的 koder 边界

**文件**: `core/templates/gstack-harness/template.toml`（planner role_details），planner workspace 模板

**优先级**: P2

---

### 11. Specialist 共用 TOOLS/protocol.md

**发现**: builder-1 / reviewer-1 / qa-1 / designer-1 的 AGENTS.md 都重复声明：
- write DELIVERY.md + Consumed ACK 协议
- canonical verdict language
- no raw tmux send-keys

估计每 seat 30-40 行重复，总共 120-160 行跨 seat 冗余。

**修复**:
- 新建 `core/templates/shared/TOOLS/protocol.md`（~80 行）
- 每个 specialist AGENTS.md 只留 10-20 行 seat 特化内容 + 一行 `"Read TOOLS/protocol.md for shared protocol"`
- bootstrap / init_koder 部署 shared protocol.md 到每个 seat workspace（symlink 或 copy，选前者则单点更新）

**文件**: `core/templates/` 新增 shared 目录，`core/skills/clawseat-install/scripts/init_koder.py`

**优先级**: P2

---

## 关联的更早期 open items（本文件之外已记录）

| 项 | 现状 |
|---|---|
| `install-with-memory.toml` 未部署 Memory CC 的 CLAUDE.md + hooks | 本次由 bundle-B 的 init_koder.py 修改解决（M1 §5.1 第 12 项 B 方案） |
| 机器扫描 miss feishu group `oc_0e1305956760980a9728cb427375c3b3` | 仍开放，待 M2 项目/环境扫描重写时一并处理 |

---

## 附录 A · Live-Run Additions (追加于 Phase 7 M1-M2 期间)

这些条目来自 M1/M2/sendverify/bootstrap-sync 四条 chain 跑完过程中暴露的新系统性问题。继续用 P0/P1/P2 同分级。已闭的条目在 commit sha 后面画 ✅。

### 12. koder 非 trivial chain 必须走 planner (P1)

**发现**: followup-rawtmux-fix 事件中 koder 跳过 planner 直派 3 个 specialist，导致非标准链路 + qa false-negative race。

**修复**: template.toml koder role_details 加硬规则"任何 dispatch ≥2 specialist 的 chain 必须走 planner，无一例外"。

**文件**: `core/templates/gstack-harness/template.toml`

---

### 13. specialist 硬编码回 planner，不尊重 reply_to (P1)

**发现**: planner 用 `reply_to=reviewer-1` 想 auto-chain，但 reviewer-1 的 AGENTS.md 内置"完成后回 planner"，`reply_to` 字段被忽略。sendverify-simplify 和 M2 bundle-B 侥幸跑通是因为 planner 本来就有 consume 兜底。

**修复**: reviewer-1 / qa-1 / builder-1 / designer-1 的 AGENTS.md 明确"优先从 dispatch receipt 读 `reply_to` 字段"。

**文件**: `core/templates/gstack-harness/template.toml`

---

### 14. planner 收到自己没派的 task 完成应 flag surprised_ack (P2)

**发现**: followup-rawtmux-fix 事件中 planner 静默 ACK 了 qa-1 的主动完成（koder bypass），无告警。

**修复**: planner `complete_handoff.py` consumer 逻辑检测 task_id 是否在自己的 dispatch log 里；不是则 receipt 添加 `surprise=true` 标签 + stderr warning。

**文件**: `core/skills/gstack-harness/scripts/complete_handoff.py`

---

### 15. Sandbox HOME 隔离导致 planner 读不到 koder 写的 TODO (P0)

**发现**: real HOME 和 sandbox HOME 的 `TODO.md` 是不同物理文件。koder 从真实 HOME 写的任务派发，planner 在 sandbox HOME 读到的是老内容或空白。本现象在 followup-sendverify-race 首次派发触发，koder 以为 notify 失败重试 3 次导致 queue append 3 份。

**修复候选**:
- A. bootstrap 做 `tasks/` 的 symlink (sandbox → real)
- B. dispatch_task.py / complete_handoff.py 同时写两处

**推荐**: A

**文件**: `core/skills/gstack-harness/scripts/bootstrap_harness.py`

---

### 16. dispatch_task.py 非幂等 (P0)

**发现**: 同 task_id 重复调 `dispatch_task.py` 会在 TODO.md queue 里 append 多条。followup-sendverify-race 首次派发有 3 份 queued 副本。

**修复**: 入参若 TODO 已有同 task_id pending/queued 条目 → 退出码 2 (TASK_ALREADY_QUEUED)，只重发 notify，不追加 queue。

**文件**: `core/skills/gstack-harness/scripts/dispatch_task.py`

---

### 17. koder retry dispatch 缺少幂等保护 (P0)

**发现**: 配合 #16。koder 看 dispatch_task 非零退出，不加判断重跑整个命令。应该只重发 send-and-verify 而不是重跑 dispatch 本身。

**修复**: koder 的 dispatch retry 逻辑识别退出码 2 = 只 re-notify；退出码 1 = 真失败需 escalate。

**文件**: koder system prompt (`~/.openclaw/workspace-koder/TOOLS/dispatch.md`) + template.toml

---

### 18. eng-review AUTO_ADVANCE 语义歧义 (P2)

**发现**: followup-sendverify-race 中 planner 以 eng-review phase 完成名义发 AUTO_ADVANCE 给 koder，但 koder 误读为"整个任务已收尾"。实际下游 builder/reviewer/qa 都还没跑。

**修复**: `complete_handoff.py --frontstage-disposition` 允许传 `phase=plan` 或 `phase=impl`，`OC_DELEGATION_REPORT_V1` 体现 phase，让 koder 知道是锁方案还是整条链完成。

**文件**: `core/skills/gstack-harness/scripts/complete_handoff.py`

---

### 19. 非标准 reply_to 串链在 specialist 系统提示词下不成立 (P2)

**重复 #13，合并**。

---

### 20. Template → deployed workspace 同步机制缺失 (P0) ✅ 已闭合（e9614aa）

**发现**: M1 期间 builder-1 的 workspace `AGENTS.md` 仍是 02:00 版本（旧的 "unless unavailable" 豁免），但 template.toml 已在 05:20 更新。运行中的 seat 无法自动读到新规则。

**已落**: e9614aa 新增 `agent-admin engineer refresh-workspace <seat>` 命令 + `bootstrap_harness.py --refresh-existing`。qa-1 APPROVED 的 S1/S4/S5/S6/S7/S8。

---

### 21. Transport failed 时 specialist 缺 no-fallback 显式路径 (P1)

**发现**: builder-1 遇 complete_handoff.py notify 失败，默认 fallback 裸 tmux（旧规则允许）。新规则禁了裸 tmux 但没教"该怎么办"。

**修复**: template.toml specialist role_details 加"transport failed → retry 3 次 → 放弃，留 DELIVERY.md 等 patrol heartbeat"路径。

**文件**: `core/templates/gstack-harness/template.toml`

---

### 22. complete_handoff 非 planner → koder 应硬拒绝 (P0) ✅ 已闭合（48b799d）

**发现**: qa-1 / reviewer-1 直连 `target=koder` 走 tmux 路径（koder 不是 tmux seat），notify 静默失败；Feishu 路径 gated on source=planner 也不触发。DELIVERY 落盘但用户永远收不到。

**已落**: `complete_handoff.py` 硬拒绝 non-planner → koder + 7 新测试。

---

### 23. Feishu 路径硬编码锁死 source=planner 的 side-effect (P1)

**发现**: 与 #22 互补：koder bypass planner 直派 specialist 的 chain，specialist 想回 koder 也走不通 Feishu（路径 gated）。#22 修了直连 reject，但那些 bypass chain 本身依然 orphan。

**修复**: template.toml koder role_details 硬化禁止 bypass（#12），根治此问题。

---

### 24. Planner 事件实时推送 Feishu (P1) —— 观测基建

**发现**: 当前只有 `OC_DELEGATION_REPORT_V1` 在 planner → koder closeout 一步发。中间的 dispatch / consumed / verdict 全部 invisible。实际 debug 过程中多次出现 planner stuck / bypass / race 问题，都因为缺实时 observability 而需要 bash 抓 tmux pane。

**修复**:
- `dispatch_task.py` 成功写 receipt 后（source 或 target 是 planner），推简短一行 Feishu
- `complete_handoff.py` 成功写 DELIVERY 后（source 或 target 是 planner），推简短一行 Feishu
- 格式: `[<project>] <source> → <target>: <task_id> <verb>` （<80 字符）
- `CLAWSEAT_ANNOUNCE_PLANNER_EVENTS` env var 控制，install profile 置 1，默认关

**范围**:
- `core/skills/gstack-harness/scripts/dispatch_task.py`
- `core/skills/gstack-harness/scripts/complete_handoff.py`
- `tests/test_planner_announce.py` (new, ≥6 cases)

**硬红线**:
- 不碰 template.toml / AGENTS.md
- specialist ↔ specialist 事件不广播（避免噪音）
- Feishu 发送失败不阻塞 dispatch / complete_handoff 主流程
- 一行 <80 字符（防止刷屏）

**文件**: 2 py 脚本 + 1 测试

---

### 25. Seat 在 feature branch 上工作，不是 main (P2)

**发现**: 2026-04-18 push 时发现 `memory-v3-m2-bundle-b` feature branch 上堆了 4 commits（bundle-B + fix1 + bootstrap-sync 2），builder-1 或 planner 在上面跑不提示。违反"默认 main 工作"约定，并且 `git push origin main` 这种常规操作看起来"up-to-date"但其实 local main 跟 HEAD 不同步。

**修复**:
- specialist AGENTS.md 明确"除非任务明写 `--branch X`，否则始终在 main 工作"
- ship skill / agent-admin 提供"start-in-main"助推（自动检测 non-main + 告警）

**文件**: `core/templates/gstack-harness/template.toml` + ship skill

---

## 派发建议顺序

建议 koder 在 M1 final AUTO_ADVANCE 后，按以下顺序派：

1. **Batch 1 (P0 堵裸 tmux)**: #5 + #6 一起派 builder-1 → reviewer-1 → qa-1（互为完整修复，必须同批 landing）
2. **Batch 2 (P0 profile bug)**: #9 单独派 builder-1 → reviewer-1（核心 fix，独立测试）
3. **Batch 3 (P1 守门 + traceability)**: #1 + #2 + #4 + #7 + #8 一批（都是强化现有路径，回归风险低）
4. **Batch 4 (P2 文档 de-bloat)**: #10 + #11 一起（都是 template.toml 的拆分工作，一次做完省 re-init）
5. **#3** (reviewer 仲裁，可并入 M1 closeout verdict，不单独派)

---

**不动此文件**: 只记录不实施。M1 chain 跑完再行动。
