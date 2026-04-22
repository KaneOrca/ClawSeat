task_id: PROJGROUP-029
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 项目管理可组合现有命令实现（杀 install 组需 8 行脚本）；始祖 SKILL.md 缺 B1.5 env_scan + provider 推荐逻辑，建议在 Phase-A B1-B2 间插入 15-20 行补丁。

## Subagent A — 项目组管理脚本

### 现有项目管理子命令列表

`agent_admin project` 子命令（`agent_admin_parser.py:129-264`）：

| 子命令 | 功能 |
|--------|------|
| `list` | 列出所有项目 |
| `current` | 显示当前项目 |
| `use <project>` | 切换当前项目 |
| `show [project]` | 显示项目详情 |
| `open <project>` | 打开项目 |
| `create <project> <repo_root>` | 创建项目 |
| `bootstrap --template <T> --local <L>` | 从模板引导创建项目 |
| `delete <project>` | 删除项目 |
| `layout [project]` | 设置项目窗口布局 |
| `bind / binding-show / binding-list / unbind` | Feishu 绑定管理 |
| `koder-bind` | 绑定 OpenClaw tenant |
| `seat list` | 列出项目所有 seat |
| `validate` | 校验项目 profile |

### delete 是否杀 tmux sessions？

**YES** — `project delete` 会杀该项目所有 tmux sessions。

证据（`agent_admin_crud.py:384-420`）：
- 对每个工程师调用 `session_service.stop_engineer(session)`
- `agent_admin_session.py:283-304` (`stop_engineer`) 执行 `tmux kill-session -t <session>`
- 同时杀 `project-{project}-monitor`

### agent-launcher.sh project flags

**NO** — `agent-launcher.sh` 不支持 `--kill-project`、`--switch-project`。仅支持 `--tool`, `--auth`, `--dir`, `--session`, `--headless`, `--exec-agent` 等。

### 多项目 session 命名冲突处理

**通过项目名前缀隔离**：
- 工程师 session：`session_name_for(project, engineer_id, tool)` 生成唯一名称
- Monitor session：`project-{project_name}-monitor`
- 例：`project-install-monitor`、`project-foo-monitor`

多项目可共存，session 名互不冲突。

### "杀 install 组、起 foo 项目组"可行路径

**(b) 需组合现有命令 — 8 行 shell 脚本草稿：**

```bash
#!/bin/bash
# 杀 install tmux sessions，切换到 foo 项目
set -euo pipefail

INSTALL="install"
FOO="foo"

# 1. 杀 install 所有 tmux sessions（stop_engineer 发 kill-session）
for seat in $(agent_admin session list --project "$INSTALL" 2>/dev/null | grep "^running" | cut -f2); do
  agent_admin session stop-engineer "$seat" --project "$INSTALL" 2>/dev/null || true
done

# 2. 杀 install monitor session
tmux kill-session -t "project-${INSTALL}-monitor" 2>/dev/null || true

# 3. 切换当前项目到 foo
agent_admin project use "$FOO"

# 4. 启动 foo monitor + autostart seats
agent_admin session start-project "$FOO" --reset
```

> 注意：`project delete` 会删除项目目录（`shutil.rmtree`），而上面脚本只杀 session、不断项目——适合"切换工作上下文"场景。如需完全清理，再加一行 `agent_admin project delete "$INSTALL"`。

---

## Subagent B — 始祖模板知识审计

### 能力对照表

| 能力 | 在模板中？ | 证据 |
|------|-----------|------|
| 读 `~/.agents/memory/machine/*.json` 5 文件并分析 | **NO** | SKILL.md 无任何提及 `machine/` 目录或 credentials/network/openclaw/github/current_context |
| env_scan 推荐 provider 组合 | **NO** | 无任何提及 env_scan 或 domestic API 推荐逻辑 |
| 交互式澄清 5 seat provider（逐个确认） | **NO** | §4 seat 生命周期只有 add/reconfigure/restart，无交互确认流程 |
| wait+verify 而非 fire-and-forget | **YES** | SKILL.md §2 B4: "30s 内 `tmux has-session` 检查；每 session 重试一次" |
| Phase-A B1-B7 完整流程 | **YES** | SKILL.md §2 + `ancestor-bootstrap-brief.md` §Phase-A checklist 完整覆盖（含失败策略） |
| 写 `STATUS.md phase=ready` | **YES** | SKILL.md §2 B7: "`~/.agents/tasks/<project>/STATUS.md` 写入 `phase=ready`" |
| 飞书 smoke report 触发 | **YES** | SKILL.md §2 B6: "发 `OC_DELEGATION_REPORT_V1 report_type=smoke` 到 group" |

### 缺失的能力

**核心缺失 — ancestor SKILL.md 不含机器环境感知步骤：**

1. **B0 env_scan 步骤完全缺失**：Phase-A 直接从 B1-read-brief 开始，无"启动后先扫描 `~/.agents/memory/machine/*.json`"的步骤。
2. **provider 推荐逻辑缺失**：无基于 env_scan 结果推荐 `claude-code + 国内 API` 组合并解释根因的逻辑。
3. **交互式 seat provider 澄清缺失**：B4 是纯自动 fan-out，无"逐个 seat 向 operator 确认 provider"的交互步骤。

**后果**：新机器上，ancestor 不知道要推荐 provider 组合，也不会停下来问 operator，直接按 profile 默认值全烧上去。

### 补丁建议

**在 SKILL.md §2 Phase-A 表格中 B1-read-brief 之后、B2-verify-or-launch-memory 之前插入 B1.5（约 15-20 行）：**

```
B1.5-env-scan (新增)
  动作: 读 `~/.agents/memory/machine/*.json` 全部 5 文件（credentials / network / openclaw / github / current_context），文件缺失则视为空 dict 继续
  成功判据: 全部文件可读（哪怕某些为空）
  失败策略: 任意文件读取失败 → Feishu 告警 operator，continue（不阻塞 Phase-A）
  输出: 在 journal 记录 env_snapshot，供后续 B4 查用

  若 machine/*.json 中 domestic API 配置缺失或不完整：
  → 发 `OC_DELEGATION_REPORT_V1 report_type=provider_recommendation`
    含 env_scan 结果摘要 + 推荐 provider 组合 + 根因说明
  → 等待 operator 逐 seat 确认（每个 seat 回复 Y/N）
  → 超时未确认 → 按 profile 默认值继续，不永久阻塞
```

§4 seat 生命周期也需小补：在 Add seat 步骤中加"若 provider 未配置则触发 B1.5 clarification 流程"。

---

## 最终建议（给 planner 定 v0.7 流程用）

| 决策点 | 建议 |
|--------|------|
| G3 项目组管理 | 用 Subagent A 的 8 行脚本草稿，杀 install tmux session + `agent_admin project use foo` + `start-project` 即可。无需新写 `kill-project` flag。 |
| G4 env_scan 始祖知识 | 在 `clawseat-ancestor/SKILL.md` §2 Phase-A B1 和 B2 之间插入 B1.5 env_scan 步骤（15-20 行），含文件读取 + provider 推荐 + 交互确认逻辑。 |
| 多项目共存 | 已有项目名前缀隔离，`project use` 切换上下文但不断旧项目 session — 符合预期行为。 |
| 下一步 | 将 B1.5 补丁写入 `clawseat-ancestor/SKILL.md`，然后做一次 smoke test 验证 ancestor 在无 domestic API 配置机器上的行为是否符合预期。 |
