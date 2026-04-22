task_id: SPAWN-049
owner: builder-codex
target: planner

## 结果

- `scripts/install.sh` 已从“fan-out 6 seat”改成“只起 `ancestor + memory`”。
- 六宫格保留；`planner/builder/reviewer/qa/designer` 五个 pane 现在跑 `scripts/wait-for-seat.sh`，等 ancestor 后续 `agent_admin session start-engineer` 时自动 attach。
- install Step 5.5 已接上 `agent_admin project bootstrap`，只建 project / engineer / session records，不起 tmux。
- ancestor brief 的 B3.5 已改成真实可用路径：`session switch-harness` → `session start-engineer` → `session-name` 等待，不再引用不存在的 `agent-launcher.sh --engineer ...`。
- 追加 patch 4b 已落地：`install.sh` 新增 `--base-url` / `--api-key` / `--model`；显式 custom API 会在 `select_provider()` 顶部短路，优先于 `--provider` 和自动探测。
- 追加 patch 4c 已落地：`--provider minimax --api-key ...` 会自动补 `https://api.minimaxi.com/anthropic` + 默认 model；`--provider anthropic_console --api-key ...` 也能在无 env / 无 tty 时直接走通。
- 追加 patch 4d 已落地：ancestor brief 不再包含 `~/...`；`render_brief()` 现在把 `AGENT_HOME=REAL_HOME` 注入模板，seat 在 sandbox HOME 下读到的仍是宿主真实路径。
- 追加 patch 4e 已落地：`wait-for-seat.sh` 现在按 `base`、`base-claude`、`base-codex`、`base-gemini` 四个名字轮询 `tmux has-session`，不会再因为 `session_name_for()` 带 tool 后缀而永远等不到。
- 追加 patch 4j 已落地，并 supersede 4f / 4i：Phase-A 不再让 memory 做 ad-hoc 调研；B2.6 已撤销，B5 改成 ancestor 自读 binding/openclaw/lark 现状，memory 在 Phase-A 的唯一位置是 B7 后接收 `${PROJECT_NAME}-phase-a-decisions.md` 单向交付。

## 改动清单

- `scripts/install.sh`
  - Step 5 只 launch `ancestor`
  - 新增 Step 5.5 bootstrap project roster
  - 六宫格改成 `ancestor attach + 5 lazy panes`
  - 新增 `--provider`
  - 新增 `--base-url` / `--api-key` / `--model`
  - `parse_args()` 增加互斥/成对校验
  - `select_provider()` 顶部增加 explicit custom API 短路
  - `select_provider()` 新增 `--provider minimax|anthropic_console + --api-key` 便利用法
  - `render_brief()` 改为向 `Template.safe_substitute()` 传 `AGENT_HOME="$REAL_HOME"`
  - `OPERATOR-START-HERE.md` 改成 post-4j 事实：Phase-A 不让 memory 做同步调研，B2.5 / B5 由 ancestor 自读，B7 后再单向写 `phase-a-decisions` learnings
  - 顺手修了两处 `set -e` 空值写文件 live bug：
    - `launcher_custom_env_file_for_session()`
    - `write_bootstrap_secret_file()`
  - `project-local.toml` 现在写 6 个 `[[overrides]]`，并给 ancestor 写 `session_name = "<project>-ancestor"`
- `scripts/wait-for-seat.sh`
  - 新建，支持 `<project-seat>` 或 `<project> <seat>`
  - 轮询 exact session + `-claude/-codex/-gemini` 三个 tool 后缀
- `core/templates/ancestor-brief.template.md`
  - 更新上下文快照与 B3.5 spawn 路径
  - 所有 `~/...` 改成 `${AGENT_HOME}/...`
  - B2.5 改为 `bootstrap_machine_tenants.py` 后由 ancestor 自己 Read `openclaw.json` / `workspace.toml` / `machine.toml` 做一行摘要
  - 撤销 B2.6；不再有 memory send-keys / bootstrap-report / `MEMORY_REPORT_READY`
  - 重写 B5：ancestor 自己读 `project binding-list`、`openclaw.json agents[] + accounts[]`、`lark-cli/config.json`，再呈现可用 openclaw agent / 占用状态；operator 选 agent、拉群并粘贴 chat_id，最后用 `project bind --feishu-group --feishu-bot-account --require-mention`
  - 新增 B7.5：ancestor 单向写 `${PROJECT_NAME}-phase-a-decisions.md` 到 memory learnings；不等待回执
- `core/scripts/agent_admin.py`
  - `create_session_record()` wrapper 透传 `session_name`
  - `StoreHooks` 接入 repo-root `templates/`
- `core/scripts/agent_admin_store.py`
  - `load_template()` 支持 repo-root `templates/clawseat-default.toml`
  - `create_session_record()` 支持显式 `session_name`
- `core/scripts/agent_admin_crud.py`
  - `project_bootstrap()` 把 template override 里的 `session_name` 传进 session record
- `templates/clawseat-default.toml`
  - 新增 6-seat bootstrap 模板（ancestor/planner/builder/reviewer/qa/designer）
- `docs/INSTALL.md`
  - 对齐 post-049 事实：只起 ancestor + memory，其他 5 pane lazy attach
  - 补充 `--provider` / `--base-url` / `--api-key` / `--model` 用法
  - 补充 minimax / anthropic-console 的 `--provider + --api-key` 便利用法
  - 增加安全提示：`--api-key` 会出现在 `ps` / shell history，推荐优先 `export ...; bash scripts/install.sh --provider custom_api`
- 测试
  - `tests/test_install_isolation.py`
  - `tests/test_install_lazy_panes.py`
  - `tests/test_project_bootstrap_repo_template.py`
  - `tests/test_ancestor_brief_spawn49.py`
  - 兼容 `StoreHooks` 新字段的夹具更新：
    - `tests/test_launch_permissions.py`
    - `tests/test_openclaw_koder_workspace.py`

## 兼容性说明

- 保守兼容线保持不变：如果 `~/.agents/projects/$PROJECT/project.toml` 已存在，`install.sh` 仍跳过 Step 5.5 bootstrap，避免覆盖已有项目状态；因此 `cartooner` / `mor` / `cartooner-web` 等既有项目不会被这次 install 入口重写。
- `wait-for-seat.sh` 现在按 `project-seat`、`project-seat-claude`、`project-seat-codex`、`project-seat-gemini` 四个候选名探测；不会误吸附其它未知前缀 session，也能兼容当前三种工具后缀。

## Verification

```text
$ bash -n scripts/install.sh
$ bash -n scripts/wait-for-seat.sh
$ pytest tests/test_install_isolation.py tests/test_install_lazy_panes.py tests/test_project_bootstrap_repo_template.py tests/test_ancestor_brief_spawn49.py -q
12 passed in 23.73s

$ pytest tests/test_launch_permissions.py tests/test_openclaw_koder_workspace.py -q
19 passed in 0.14s
```

覆盖到的关键场景：

- dry-run 只 launch `ancestor + memory`
- 六宫格 5 个 lazy pane 命令正确
- runtime bootstrap 会生成 project/local/template + pending seat secrets
- `wait-for-seat.sh` 能 attach 到 `project-seat-tool`
- `wait-for-seat.sh` 对 `exact / -claude / -codex / -gemini` 四种名字都能 attach
- `--base-url + --api-key + --model` 在无 env / 无 tty / 探测失效时仍可成功 install
- `--provider minimax --api-key ...` 自动补 minimax base_url + model
- `--provider anthropic_console --api-key ...` 跳过 detect / 无 tty 也能成功 install
- `--base-url` 单传报 `INVALID_FLAGS`
- `--provider minimax` 与 explicit custom flags 冲突时报 `INVALID_FLAGS`
- render 后 brief 不含 `~/` / `${AGENT_HOME}` 占位，全部落成真实宿主路径
- brief 不再包含 B2.6、memory send-keys、`${PROJECT_NAME}-bootstrap-report.md` 或 `${PROJECT_NAME}-feishu-binding-report.md`
- B5 的真实 UX 现在是 ancestor 自读现状后“选 openclaw agent → 拉新群 → 粘贴 chat_id → bind”
- B7 后会单向写 `${PROJECT_NAME}-phase-a-decisions.md` 给 memory；Phase-A 主链路不等待 memory 回执

## Notes

- 本次没有 commit。
- worktree 里还保留其他未提交改动；本交付只在其上增量修改，没有回滚它们。
