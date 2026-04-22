# TODO — PROJGROUP-029 (项目组管理脚本 + ancestor 模板知识审计)

```
task_id: PROJGROUP-029
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P1
subagent-mode: REQUIRED — spawn 2 parallel subagents (A/B)
do-not-modify: read-only
```

## Context

用户确认了 v0.7 install 流程的剩余决策点：
- G1（ancestor brief）固化为模板文件
- G2（engineer seat provider）一个一个交互式拉起
- G3（项目组管理脚本）待调研 ← **Subagent A**
- G4（env_scan LLM 分析）用户要求始祖 CC 自己读 machine/ 文件后分析推荐

新增需求：
- install 项目（默认名）完成后，用户可能要求"杀掉 install 组、起个新项目组 foo"
- 始祖 CC 的模板必须内含足够知识让它懂 env_scan 结果 / provider 澄清 / Phase-A 全流程

---

## Subagent A — 项目组管理脚本调研

在 `/Users/ywf/ClawSeat` 仓库里找：

1. **有没有创建/切换项目的脚本？**
   ```bash
   find . -type f \( -name "*.sh" -o -name "*.py" \) | xargs grep -l "project.*create\|project.*new\|kill.*project\|new_project\|create_project\|switch_project" 2>/dev/null | head -20
   ```

2. **`core/scripts/agent_admin.py` 的 `project` 子命令**：
   - 读 `core/scripts/agent_admin_project.py`（如果存在）或同级 admin 相关文件
   - 它支持哪些子命令？（create / delete / list / switch / rename 等）
   - delete 是否会杀对应的 tmux sessions？

3. **`core/launchers/agent-launcher.sh`**：
   - 支持 --kill-project / --switch-project 吗？
   - 多项目并存时 session 命名冲突怎么处理？

4. **现有的项目目录结构**：
   ```bash
   find ~/.agents/tasks -maxdepth 2 -type d 2>/dev/null | head -20
   find ~/.agents/projects -maxdepth 2 -type d 2>/dev/null | head -20
   ```
   - 如果有多个项目目录，它们怎么共存？

报告：
- 现有项目管理子命令列表（若存在）
- "杀 install 组、起 foo 项目组"可行路径：
  - (a) 现有脚本能直接完成 → 列命令
  - (b) 需要组合几个现有命令 → 给 shell 脚本草稿（8-15 行）
  - (c) 完全没有相关支持 → 需要从头设计

---

## Subagent B — 始祖 CC 模板知识审计

阅读：

1. **`core/skills/clawseat-ancestor/SKILL.md`** — 始祖 CC 的 skill 文件
2. **`core/templates/ancestor-engineer.toml`**（SWEEP-023 清理后的版本）
3. 如果存在：`core/templates/ancestor-brief.template.md` 或类似命名的 brief 模板

审计以下能力是否在模板中**已写明**（不是隐含、不是"应该懂"）：

| 能力 | 是否在模板中？ | 证据（引用路径+行号） |
|------|--------------|---------------------|
| 读 `~/.agents/memory/machine/*.json` 5 文件并分析（credentials/network/openclaw/github/current_context） | ? | ? |
| 基于 env_scan 推荐 provider 组合（claude-code + 国产 API）+ 说明根因 | ? | ? |
| 向用户交互式澄清 5 个 engineer seat 的 provider（每个一个确认） | ? | ? |
| 在每个 seat 拉起后 wait + verify（而不是 fire-and-forget） | ? | ? |
| Phase-A B1-B7 完整流程（含失败重试策略） | ? | ? |
| 写 `~/.agents/tasks/install/STATUS.md` phase=ready 的格式 | ? | ? |
| 飞书 smoke report 的触发方式（需不需要先配 chat_id？） | ? | ? |

报告：
- 模板当前已有哪些能力（列举 + 证据）
- 缺哪些能力（具体到哪条 Phase-A 步骤没写明）
- 推荐补丁（写在 SKILL.md 哪个 section，大致几行）

---

## Deliverable

写 `DELIVERY-PROJGROUP-029.md` 到 `/Users/ywf/ClawSeat/.agent/ops/install-nonint/`：

```
task_id: PROJGROUP-029
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## Subagent A — 项目组管理脚本
<现状 + 命令列表 / 脚本草稿 / gap>

## Subagent B — 始祖模板知识审计
<能力对照表 + 缺项 + 补丁建议>

## 最终建议（给 planner 定 v0.7 流程用）
```

完成后通知 planner: "DELIVERY-PROJGROUP-029 ready"。
