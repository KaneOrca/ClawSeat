task_id: FEISHU-AUTH-053
owner: builder-codex
target: planner

## 改动清单

### Subagent B

- `core/lib/project_binding.py`
  - `PROJECT_BINDING.toml` 升到 v2。
  - 新增 `feishu_sender_app_id`、`feishu_sender_mode`、`openclaw_koder_agent`。
  - 保留旧 `feishu_bot_account` 兼容读，写出时改为 v2 新字段。
  - `ProjectBinding.from_toml()` 兼容 legacy `feishu_bot_account=cli_*` 和非 `cli_*` 两种迁移路径。
- `core/scripts/agent_admin_parser.py`
  - `project bind` 新增 `--feishu-sender-app-id`、`--feishu-sender-mode`、`--openclaw-koder-agent`。
  - 保留 `--feishu-bot-account` 旧 alias，默认 `None` 以便 handler 识别是否显式使用。
- `core/scripts/agent_admin.py`
  - `cmd_project_bind()` 对旧 alias 打 deprecated warning，并按 `cli_*` / 非 `cli_*` 路由到新字段。
  - `project binding-list` 输出改为显示 `sender_app_id` / `sender_mode` / `koder_agent`。
- `core/scripts/agent_admin_layered.py`
  - `koder-bind` 写入新 schema 字段，不再只复制 legacy bot account。
- `core/skills/clawseat-ancestor/SKILL.md`
  - 新增 `### 5.x` Feishu/lark-cli canonical 命令卡片。
  - 新增 `### 5.y` auth 决策树。
  - 明确 `lark-cli app / OpenClaw agent app` 不混。
- `core/templates/ancestor-brief.template.md`
  - B5 重写为 5 子步。
  - B5.4 写入 v2 四字段 bind 命令。
  - B5.5 改为 `send_delegation_report.py --as auto` smoke。
- `tests/`
  - 新增 `tests/test_project_binding_schema_v2.py`
  - 新增 `tests/test_ancestor_skill_lark_cli_cheat_sheet.py`
  - 新增 `tests/test_ancestor_auth_decision_tree.py`
  - 新增 `tests/test_ancestor_brief_b5_substeps.py`
  - 更新 `tests/test_ancestor_brief_spawn49.py`

## 验证

- `python -m py_compile /Users/ywf/ClawSeat/core/lib/project_binding.py /Users/ywf/ClawSeat/core/scripts/agent_admin.py /Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py /Users/ywf/ClawSeat/core/scripts/agent_admin_layered.py /Users/ywf/ClawSeat/tests/test_project_binding_schema_v2.py /Users/ywf/ClawSeat/tests/test_ancestor_skill_lark_cli_cheat_sheet.py /Users/ywf/ClawSeat/tests/test_ancestor_auth_decision_tree.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_b5_substeps.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py`
- `pytest tests/test_project_binding.py tests/test_project_binding_resolver.py tests/test_bridge_preflight.py tests/test_project_binding_schema_v2.py tests/test_ancestor_skill_lark_cli_cheat_sheet.py tests/test_ancestor_auth_decision_tree.py tests/test_ancestor_brief_b5_substeps.py tests/test_ancestor_brief_spawn49.py -q` -> `43 passed`
- `pytest tests/test_ancestor_brief_memory_tools.py tests/test_ancestor_brief_pyramid_rules.py tests/test_ancestor_rejects_arch_violations.py tests/test_ancestor_brief_drift_check.py tests/test_ancestor_skill_brief_drift_rules.py tests/test_ancestor_brief_spawn49.py -q` -> `13 passed`

## Notes

- 这次只动 B 线允许范围内的文件，没有回滚或覆盖 A 线改动。
- legacy `feishu_bot_account` 仍可读，写回时会落到 v2 新字段。
- `openclaw_koder_agent` 不是默认强塞 `koder`，只有显式需要时才写。

## Followup suggestions

- 若 planner 认可，可再做一轮旧 `PROJECT_BINDING.toml` 的批量迁移 CLI。
