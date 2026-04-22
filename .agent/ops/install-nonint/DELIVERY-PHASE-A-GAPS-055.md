## Task
- task_id: PHASE-A-GAPS-055
- target: builder-codex
- repo: /Users/ywf/ClawSeat (experimental)
- scope: smoke02 Phase-A B0/B2.5/B3.5 暴露的 4 个 gap + 2 个延展 blocker

## 改动清单

### R1 · `install.sh` tomli 自愈
- [scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh)
  - 在 `scan_machine` 前新增 `ensure_python_tomllib_fallback()`
  - 运行顺序是 `import tomllib` -> `import tomli` -> `python -m pip install --user --quiet tomli`
  - 保持幂等，成功安装后不再重复触发

### R2 · sandbox HOME 多工具 seed + retroactive reseed
- [core/launchers/agent-launcher.sh](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh)
  - `seed_user_tool_dirs()` 追加 `.config/gemini`、`.gemini`、`.config/codex`、`.codex`
  - 现有 sandbox 内若已经有独立目录/文件，会备份到 `.sandbox-pre-seed-backup/` 后替换为 symlink
  - 目标是让 pre-R1 / pre-R2 的旧 sandbox 也能补回 user-level 工具目录
- [core/scripts/agent_admin_session.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py)
  - start-engineer 之前会先 reseed sandbox HOME
  - `_ancestor_brief_path()` 现在使用 `CLAWSEAT_REAL_HOME -> AGENT_HOME -> Path.home()` 回退链
  - 新增 `reseed_sandbox_user_tool_dirs()`
- [core/scripts/agent_admin_commands.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_commands.py)
  - 新增 `session reseed-sandbox`
- [core/scripts/agent_admin_parser.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py)
  - 新增对应 parser
- [core/scripts/agent_admin.py](/Users/ywf/ClawSeat/core/scripts/agent_admin.py)
  - 接上新 command hook

### R3 · ark provider 跨 seat 对齐
- [core/scripts/agent_admin_switch.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_switch.py)
  - 对 `provider == ark` 且 `tool != claude` 直接报错
  - 采用“明确拒绝”策略，不做 silent auto-migrate
  - 错误文案明确指向 `--tool claude --provider ark`

### R4 · ancestor brief / skill 强制 memory 查询
- [core/templates/ancestor-brief.template.md](/Users/ywf/ClawSeat/core/templates/ancestor-brief.template.md)
  - 在 B0 / B2.5 / B3.5 加入强制 memory query 子步
  - 增加 canonical memory 交互工具段，明确 `query_memory.py` / `memory_write.py`
  - 明确禁用 `tmux send-keys` 给 memory seat
- [core/skills/clawseat-ancestor/SKILL.md](/Users/ywf/ClawSeat/core/skills/clawseat-ancestor/SKILL.md)
  - Phase-A 表格新增 `memory_query` 约束列
  - 对外通讯段补齐 memory 只读/写的 ready-to-run 示例
  - 新增跨 seat 文本通讯 canonical 规则，所有 project seat 统一走 `send-and-verify.sh`

### R5 · memory singleton + reseed 命令化
- [scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh)
  - memory seat 改为 singleton 守门，已有 `machine-memory-claude` 时复用，不再 kill/relaunch
  - 只在不存在时启动 memory daemon
  - 仍保留 memory hook 安装与 iTerm window 幂等检查
- [core/scripts/agent_admin_session.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py)
  - `start_engineer()` 启动前先 reseed sandbox HOME
- [core/scripts/agent_admin_commands.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_commands.py)
  - `session reseed-sandbox --all` 可批量补种所有 seat

### R6 · 跨 seat 文本通讯硬规则
- [scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh)
  - Step 9.5 自动发送 Phase-A kickoff prompt
  - 由裸 `tmux send-keys` 改为 `core/shell-scripts/send-and-verify.sh`
- [core/templates/ancestor-patrol.plist.in](/Users/ywf/ClawSeat/core/templates/ancestor-patrol.plist.in)
  - patrol tick 改走 `send-and-verify.sh`
- [core/templates/ancestor-brief.template.md](/Users/ywf/ClawSeat/core/templates/ancestor-brief.template.md)
  - brief 里补齐 canonical 跨 seat 通讯模板，禁止裸 `tmux send-keys`
- [core/skills/clawseat-ancestor/SKILL.md](/Users/ywf/ClawSeat/core/skills/clawseat-ancestor/SKILL.md)
  - 加入 red-flag 识别清单与跨 seat 通讯硬规则

### 测试
- [tests/test_install_tomli_guard.py](/Users/ywf/ClawSeat/tests/test_install_tomli_guard.py)
- [tests/test_launcher_lark_cli_seed.py](/Users/ywf/ClawSeat/tests/test_launcher_lark_cli_seed.py)
- [tests/test_launcher_seed_reseed_existing.py](/Users/ywf/ClawSeat/tests/test_launcher_seed_reseed_existing.py)
- [tests/test_launcher_seed_user_tool_dirs.py](/Users/ywf/ClawSeat/tests/test_launcher_seed_user_tool_dirs.py)
- [tests/test_agent_admin_session_reseed.py](/Users/ywf/ClawSeat/tests/test_agent_admin_session_reseed.py)
- [tests/test_switch_harness_ark_cross_tool.py](/Users/ywf/ClawSeat/tests/test_switch_harness_ark_cross_tool.py)
- [tests/test_install_auto_kickoff.py](/Users/ywf/ClawSeat/tests/test_install_auto_kickoff.py)
- [tests/test_install_isolation.py](/Users/ywf/ClawSeat/tests/test_install_isolation.py)
- [tests/test_install_lazy_panes.py](/Users/ywf/ClawSeat/tests/test_install_lazy_panes.py)
- [tests/test_install_memory_singleton.py](/Users/ywf/ClawSeat/tests/test_install_memory_singleton.py)
- [tests/test_session_start_ancestor_env.py](/Users/ywf/ClawSeat/tests/test_session_start_ancestor_env.py)
- [tests/test_window_open_grid.py](/Users/ywf/ClawSeat/tests/test_window_open_grid.py)
- [tests/test_ancestor_brief_memory_query_steps.py](/Users/ywf/ClawSeat/tests/test_ancestor_brief_memory_query_steps.py)
- [tests/test_ancestor_skill_memory_query_column.py](/Users/ywf/ClawSeat/tests/test_ancestor_skill_memory_query_column.py)
- [tests/test_ancestor_skill_comm_discipline.py](/Users/ywf/ClawSeat/tests/test_ancestor_skill_comm_discipline.py)
- [tests/test_ancestor_brief_no_bare_send_keys.py](/Users/ywf/ClawSeat/tests/test_ancestor_brief_no_bare_send_keys.py)
- [tests/test_ancestor_brief_b5_substeps.py](/Users/ywf/ClawSeat/tests/test_ancestor_brief_b5_substeps.py)
- [tests/test_ancestor_auth_decision_tree.py](/Users/ywf/ClawSeat/tests/test_ancestor_auth_decision_tree.py)
- [tests/test_ancestor_brief_spawn49.py](/Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py)
- [tests/test_ancestor_brief_pyramid_rules.py](/Users/ywf/ClawSeat/tests/test_ancestor_brief_pyramid_rules.py)
- [tests/test_ancestor_rejects_arch_violations.py](/Users/ywf/ClawSeat/tests/test_ancestor_rejects_arch_violations.py)
- [tests/test_ancestor_brief_drift_check.py](/Users/ywf/ClawSeat/tests/test_ancestor_brief_drift_check.py)
- [tests/test_ancestor_skill_brief_drift_rules.py](/Users/ywf/ClawSeat/tests/test_ancestor_skill_brief_drift_rules.py)
- [tests/test_project_binding_schema_v2.py](/Users/ywf/ClawSeat/tests/test_project_binding_schema_v2.py)
- [tests/test_send_delegation_report_identity.py](/Users/ywf/ClawSeat/tests/test_send_delegation_report_identity.py)

## 顺手修了
- `tests/test_install_isolation.py` 里的 fake `tmux` 原先用 JSON grep 判定 session 存活，和 `send-and-verify.sh` 的先验检查不够稳定，导致 kickoff 发送看起来“没发生”
- 根因是 wrapper 先做 `has-session`，而 test shim 没有一个明确的 live-session registry；我改成纯文本 session registry，和 launcher 写入的 session 名单对齐
- 风险 / 影响：仅影响测试桩，不改生产路径；收益是把 `send-and-verify.sh` 的真实行为稳定地纳入回归测试

## 验证
- `bash -n scripts/install.sh`
- `bash -n core/launchers/agent-launcher.sh`
- `python -m py_compile` on all modified / untracked Python files in the worktree
- `pytest tests/test_install_isolation.py tests/test_install_lazy_panes.py tests/test_install_memory_singleton.py tests/test_install_auto_kickoff.py tests/test_install_tomli_guard.py tests/test_ark_provider_support.py tests/test_launcher_lark_cli_seed.py tests/test_launcher_seed_reseed_existing.py tests/test_launcher_seed_user_tool_dirs.py tests/test_agent_admin_session_reseed.py tests/test_session_start_ancestor_env.py tests/test_switch_harness_ark_cross_tool.py tests/test_window_open_grid.py tests/test_ancestor_brief_memory_query_steps.py tests/test_ancestor_skill_memory_query_column.py tests/test_ancestor_skill_comm_discipline.py tests/test_ancestor_brief_no_bare_send_keys.py tests/test_ancestor_brief_b5_substeps.py tests/test_ancestor_auth_decision_tree.py tests/test_ancestor_brief_spawn49.py tests/test_ancestor_brief_pyramid_rules.py tests/test_ancestor_rejects_arch_violations.py tests/test_ancestor_brief_drift_check.py tests/test_ancestor_skill_brief_drift_rules.py tests/test_project_binding_schema_v2.py tests/test_send_delegation_report_identity.py -q`
  - result: `68 passed`
- `markdownlint` not installed in this workspace

## Patch 历程
- 1. 先补了 install / launcher / agent_admin / brief / skill 的主链路改动，覆盖 R1-R6。
- 2. 之后发现 auto-kickoff regression 的测试桩仍按旧的裸 `tmux send-keys` 假设写法，补了 session registry，让 `send-and-verify.sh` 的 liveness check 在测试里可稳定通过。
- 3. 收口时删掉了临时调试输出，保留最小可观测的测试桩实现。

## Notes
- 这批改动是建立在前序 `ARK-050`、`MEMORY-IO-051`、`BRIEF-SYNC-052`、`FEISHU-AUTH-053`、`WINDOW-OPS-054` 的基础上，当前交付只记录本 TODO 的增量。
- `install.sh` 现在更早做 `tomli` fallback，自愈目标是避免 Phase-A B0/B2.5 在 sandbox Python 上因为缺依赖而卡死。
- `send-and-verify.sh` 已成为跨 seat 文本通讯唯一入口，brief / skill / launchd 都已同步到 canonical 路径。

## Followup suggestions
- 若 planner 想进一步收紧约束，可以把更多裸 `tmux send-keys` 的调用点继续收敛到 `send-and-verify.sh`。
- `session reseed-sandbox` 现在是 operator 可手动触发的修复入口，后续如果需要，也可以再加一层自动巡检。
