task_id: WIRE-037
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 已把 memory Stop-hook 接入 install 流程，并在 ancestor brief 模板补上 B2.5 tenant bootstrap 提示。

## 改动清单

- `scripts/install.sh`
  - 新增 `CLAWSEAT_ROOT` / `MEMORY_HOOK_INSTALLER` / `MEMORY_WORKSPACE`
  - `parse_args()` 现在把 memory workspace 解析为 `~/.agents/workspaces/<project>/memory`
  - 新增 `install_memory_hook()`，在 Step 8 前执行，并在失败时抛 `MEMORY_HOOK_INSTALL_FAILED`
  - `recreate_session()` 现在支持自定义 `cwd`
  - memory tmux session 现在起在 memory workspace，而不是 repo root
  - `claude_command()` 现在显式导出 `CLAWSEAT_ROOT`
- `core/templates/ancestor-brief.template.md`
  - 在 `B2` 与 `B3` 之间插入 `B2.5 — Bootstrap machine tenants from memory scan`
- `core/skills/memory-oracle/scripts/install_memory_hook.py`
  - 补加 `--clawseat-root` 参数，供 `install.sh` 显式传入 repo root 解析默认 hook 路径

## memory workspace 路径调研结论

实际路径约定不是 `~/.agents/engineers/...`，而是：

- `core/scripts/agent_admin_config.py:96`
  - `WORKSPACES_ROOT = AGENTS_ROOT / "workspaces"`
- `core/scripts/agent_admin_store.py:524`
  - session record 的 workspace = `workspaces_root / project.name / engineer_id`

因此 memory seat 的 workspace 约定为：

- `~/.agents/workspaces/<project>/memory`

本机现状也符合这个约定：

- 发现真实目录：`/Users/ywf/.agents/workspaces/install/memory`

最终 `install.sh` 采用的就是这条路径，而不是猜测型 `_machine` / `engineers/memory/...` 目录。

## Verification

- `bash -n scripts/install.sh`
  - `syntax ok`
- `bash scripts/install.sh --dry-run --project install | grep -E "install_memory_hook|MEMORY_HOOK|Step 7.5|\\.agents/workspaces/install/memory"`
  - 看到了 Step 7.5
  - 看到了 `install_memory_hook.py --workspace /Users/ywf/.agents/workspaces/install/memory --clawseat-root /Users/ywf/ClawSeat --dry-run`
  - 看到了 `tmux new-session -d -s machine-memory-claude -c /Users/ywf/.agents/workspaces/install/memory bash`
- ancestor brief 渲染验证：
  - `B2.5` 已出现
  - `bootstrap_machine_tenants` 已出现
  - 输出：`brief ok`

## Notes

- 按 TODO 决策，`install.sh` 没有直接调用 `bootstrap_machine_tenants.py`；智能 bootstrap 仍留给 ancestor 的 `B2.5`。
- 这次顺手修了一个隐藏接线问题：如果 memory session 仍起在 repo root，workspace 下的 `.claude/settings.json` hook 实际不会生效。
- 未 commit。
