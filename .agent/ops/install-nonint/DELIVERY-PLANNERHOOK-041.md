task_id: PLANNERHOOK-041
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 已补齐 planner stop-hook 的脚本与 installer，接入 ancestor brief 的 planner 分支，并删除失效的 v0.5 smoke。

## 改动清单

- `scripts/hooks/planner-stop-hook.sh`（153 行）
  - 新增 planner Stop-hook
  - `PLANNER_STOP_HOOK_ENABLED=0` 早退
  - 优先广播 `last_assistant_message`，超过 18000 字做 head+tail 截断
  - project 解析顺序：`CLAWSEAT_PROJECT` -> `~/.agents/workspaces/<project>/planner` 路径反推
  - 从 `PROJECT_BINDING.toml` 读取 `feishu_group_id`
  - `lark-cli im +messages-send --chat-id <gid> --text <body>` best-effort 发送
  - 缺 binding / 缺 group / 缺 lark-cli / 发送失败全部静默不阻塞

- `core/skills/planner/scripts/install_planner_hook.py`（121 行）
  - 新增 planner hook installer
  - 结构镜像 `install_memory_hook.py`
  - 幂等写 `<workspace>/.claude/settings.json` 的 `hooks.Stop`
  - 支持 `--workspace` / `--clawseat-root` / `--hook-script` / `--dry-run`

- `core/templates/ancestor-brief.template.md`
  - 在 `B3.5` 的 planner seat 分支新增：
    - `python3 core/skills/planner/scripts/install_planner_hook.py --workspace ~/.agents/workspaces/${PROJECT_NAME}/planner --clawseat-root ${CLAWSEAT_ROOT}`

- `tests/test_planner_stop_hook.py`（160 行）
  - 新增 planner hook 合同测试

- `tests/test_install_planner_hook.py`（91 行）
  - 新增 planner hook installer 测试

- 删除 legacy v0.5 smoke
  - `tests/smoke/test_v05_install.sh`
  - `tests/test_v05_smoke.py`

## Verification

- `bash -n scripts/hooks/planner-stop-hook.sh`
  - pass
- `python3 -m py_compile core/skills/planner/scripts/install_planner_hook.py`
  - pass
- `pytest tests/test_planner_stop_hook.py tests/test_install_planner_hook.py -v`
  - `8 passed`
- 手动 smoke
  - `echo '{"last_assistant_message":"test","transcript_path":""}' | CLAWSEAT_PROJECT=smoketest bash scripts/hooks/planner-stop-hook.sh`
  - 输出：`[planner-hook] no PROJECT_BINDING.toml; skip`
  - `rc=0`
- `markdownlint`
  - 本机无：`NO_MARKDOWNLINT`

## Notes

- planner hook 当前按 TODO 的简化版实现：广播正文直接用 `last_assistant_message`，不是结构化字段提取。
- brief 只接入了 planner seat 的 hook install；`install.sh` 主流程未改。
- project / binding 路径解析优先利用 `~/.agents/workspaces/<project>/planner` 反推，避免在 sandbox HOME 下读错地方。
- 未 commit。
