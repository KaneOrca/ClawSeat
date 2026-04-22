# TODO — ISOLATION-048 (L2 接 L3 + 删除 L3 v0.5 preflight)

```
task_id: ISOLATION-048
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: REQUIRED — 2 subagents (A=L2 改造, B=L3 v0.5 清理)
scope: 让 v0.7 Pyramid 在实现上真生效，不只是 docs 承诺
```

## Context

ISOLATION-046 把 L1 (`scripts/install.sh`) 切到 L3 (`core/launchers/agent-launcher.sh`)，
ARCH-CLARITY-047 把 L1 / L2 / L3 写进 `docs/ARCHITECTURE.md §3z`。但 planner code review 发现两个仍未还的债：

### 债 1 — L2 完全绕过 L3

`core/scripts/agent_admin_session.py:216-269` 的 `start_engineer()` 仍：

```python
self._run_tmux_with_retry(
    ["new-session", "-d", "-s", session.session, "-c", session.workspace, quoted_cmd],
    ...
)
```

其中 `quoted_cmd` 来自 `build_engineer_exec()`，等于：
`agentctl_path run-engineer --project <project> <engineer_id>`

**完全没调 agent-launcher.sh**。后果：

- 同一 seat 若先经 L1 (install.sh→launcher) 起、再经 L2 (`agent_admin session start-engineer`) 起，会落到**两个不同的 sandbox HOME**：
  - L1/L3 路径：`~/.agent-runtime/identities/claude/api/<auth>-<session>/home`
  - L2 路径：`agent_admin_runtime.runtime_dir_for_identity()` 的产出（按 identity 字段，结构不同）
- credentials / 登录态不共享，operator 切换路径会被要求重新登录

### 债 2 — L3 内嵌 v0.5 ancestor preflight

`core/launchers/agent-launcher.sh:1230-1351`（约 121 行）：

- 检测 session 名匹配 `^(.+)-ancestor-(claude|codex|gemini)$` 触发
- 要求 `~/.agents/profiles/<project>-profile-dynamic.toml` v2，否则报 `migrate_profile_to_v2.py`
- 调 `python3 -m core.tui.ancestor_brief` 渲染 brief
- 装 `~/Library/LaunchAgents/com.clawseat.<project>.ancestor-patrol.plist`

v0.7 install.sh **不生成 v2 profile**；brief 已由 install.sh `render_brief()` 在 v0.7 路径下生成
(`~/.agents/tasks/<project>/patrol/handoffs/ancestor-bootstrap.md`)。

install.sh 启 ancestor 用 `<project>-ancestor`（不带 `-claude` 后缀），靠**命名巧合绕过**这段地雷。
但 P0 改完后，L2 调 launcher 时如果 session 名带 tool 后缀（例如 `<project>-<engineer>-claude`），会踩这颗雷。

## Subagent A — L2 start_engineer 接 L3

### A1 调研（先做完，再动刀）

读以下文件，整理一份对比表（可写到 DELIVERY 的"调研结论"段）：

1. `/Users/ywf/ClawSeat/core/scripts/agent_admin_runtime.py`：
   - `identity_name(session)` 的命名规则
   - `runtime_dir_for_identity(identity)` 的路径结构
   - `secret_file_for(session)` 的 secret 文件位置
   - `session_name_for(session)` 的 tmux session 名规则
2. `/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh` 956-968 / 1051-1124 / 1145-1192：
   - L3 自己的 runtime_dir 结构
   - L3 自己的 secret 文件位置（`resolve_claude_secret_file()`）
   - L3 自己的 session name 默认（`${TOOL_NAME}-${AUTH_MODE}-$(slugify $(basename $WORKDIR))`）
3. 列出当前 `~/.agent-runtime/identities/` 实际目录快照：
   ```bash
   find ~/.agent-runtime/identities -maxdepth 4 -type d 2>/dev/null | sort
   ```
4. 列出当前活跃的 L2 项目 sessions：
   ```bash
   tmux list-sessions 2>/dev/null
   ls ~/.agents/sessions/ 2>/dev/null
   ```

### A2 决策

planner 倾向**策略 B（L2 切到 L3 的命名规则）**，理由：
- L3 是更纯的 execution primitive，命名直接绑 session_name + auth_mode，可读性更好
- L1 已经按 L3 规则跑（不破坏既有 fact）
- 现存 L2 identity 数量可控（cartooner / mor / cartooner-web 等几十个 seat）

但**调研可能改变这个判断**。如果发现 L2 有 50+ 活跃 identity 且 sandbox HOME 里有不可丢的 credentials，
应改用策略 C（兼容层 + 一次性迁移脚本）。

把决策写在 DELIVERY 的"决策"段，附风险评估。

### A3 实施（基于 A2 决策）

重写 `core/scripts/agent_admin_session.py:216-269`：

- 删除 `_run_tmux_with_retry(["new-session", ...])` 直接 tmux 启动
- 改为 subprocess 调：
  ```python
  cmd = [
      "bash", launcher_path,
      "--headless",
      "--tool", session.tool,
      "--auth", launcher_auth_for(session),  # session.auth_mode → launcher 命名
      "--dir", session.workspace,
      "--session", session.session,
  ]
  if needs_custom_env(session):
      cmd += ["--custom-env-file", write_one_shot_custom_env(session)]
  env = {**os.environ, "CLAWSEAT_ROOT": clawseat_root}
  subprocess.run(cmd, env=env, check=True)
  ```
- `launcher_auth_for()`：仿 `install.sh:199-206` 的 `launcher_auth_for_provider()`
- `write_one_shot_custom_env()`：仿 `install.sh:208-248` 的 `launcher_custom_env_file_for_session()`，写到 `/tmp/agent-admin-custom-<safe_session>.XXX`，传给 launcher 后 launcher 自己 rm
- 保留 `reset=True` 行为（先 `tmux kill-session -t <session>` 再 launch）
- 保留 `_assert_session_running()` 验证启动成功
- 保留 `set-titles-string` 的 tmux 设置

`build_engineer_exec()` / `agentctl_path` 在 SessionService 里如果不再被引用可以**删掉**。
`agentctl.sh` 的 `run-engineer` 入口若除 SessionService 外没人调用也可以删（先 grep 全局确认）。

### A4 兼容性红线

- 现有项目（cartooner / mor / cartooner-web 等）的所有 seat：
  - `agent_admin session start-engineer ... <seat>` 必须能起 / 停如前
  - tmux session 名不变（保持 `session_name_for()` 的产出）
  - workspace 路径不变
- 如果迁移导致 sandbox HOME 路径变化：
  - 提供 idempotent 迁移：第一次新启时把老 HOME 的内容（特别是 `.claude.json` / `.codex/auth.json` / `.gemini`）符号链接或拷贝过去
  - 或者在 SessionService 里做兼容查询（同时支持新旧路径）
- `heartbeat` manifest / receipt 路径绑 session metadata 不动

### A5 测试

新建 `tests/test_agent_admin_session_isolation.py`，覆盖：

1. `start_engineer` 不再直接 `tmux new-session`，而是调 launcher（mock launcher 验证 flags）
2. session.tool ∈ {claude, codex, gemini} 三个分支
3. session.auth_mode ∈ {oauth_token, anthropic-console, minimax, custom, chatgpt, oauth, primary} 的 launcher_auth 映射
4. custom auth 的 `--custom-env-file` 传递（含 LAUNCHER_CUSTOM_API_KEY / BASE_URL / MODEL）
5. `reset=True` 先 `kill-session` 再 launch
6. `stop_engineer` 行为不变（仍直接 `tmux kill-session`）
7. 源码 grep 确认 `start_engineer` 函数体里不再含 `"new-session"` 字面量

回归确认：
```bash
pytest tests/test_install_isolation.py -q  # ISOLATION-046 应仍 3 passed
pytest tests/test_agent_admin_session_isolation.py -q  # 新增
```

## Subagent B — 删 L3 v0.5 preflight

### B1 调研

1. 确认 `~/.agents/profiles/*-profile-dynamic.toml` 在 v0.7 install.sh 是否被生成：
   ```bash
   grep -n "profile-dynamic" /Users/ywf/ClawSeat/scripts/install.sh
   grep -rn "profile-dynamic" /Users/ywf/ClawSeat/core/skills/clawseat-install/ 2>/dev/null
   ```
   预期：install.sh 不生成此 profile。
2. 确认 `~/.agents/tasks/<project>/patrol/handoffs/ancestor-bootstrap.md` 由 install.sh 的 `render_brief()` 生成（已知 yes，line 183-197）
3. 检查当前活跃的 launchd patrol plist：
   ```bash
   ls ~/Library/LaunchAgents/com.clawseat.*.plist 2>/dev/null
   launchctl list | grep clawseat 2>/dev/null
   ```
4. v0.7 是否还需要 Phase-B patrol？
   - 答案 planner 已定：**v0.7 用 memory Stop hook 做被动巡检**（PLANNERHOOK-041 / MEMORY-035），不再需要 launchd 定时 patrol
   - 但需确认现存 launchd plist 是否仍在运行项目（cartooner / mor），如果在，**不要 unload**，由用户后续手动清理

### B2 实施

删除 `/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh:1230-1351`（"# ── Ancestor-session preflight ──────" 整段，含 `if [[ "$SKIP_ANCESTOR_PREFLIGHT" != "1" && "$SESSION_NAME" =~ ... ]]; then ... fi`）。

注意：`--skip-ancestor-preflight` flag 解析（`SKIP_ANCESTOR_PREFLIGHT="0"` 默认 + `--skip-ancestor-preflight) SKIP_ANCESTOR_PREFLIGHT="1"; shift ;;`）也一并删除，因为不再有 preflight 可 skip。

`--clone-from` flag 同样属于 v0.5 ancestor 流程一部分（preflight 内引用 `_wizard_args` 等），调研后若确认无其他消费者，一并删除。

### B3 测试

新建 `tests/test_launcher_no_v05_preflight.py`：

1. 源码 grep 确认 launcher 不再含：
   - `profile-dynamic.toml`
   - `migrate_profile_to_v2.py`
   - `ancestor-patrol.plist.in`
   - `_preflight_project` / `_brief_path` / `_plist_template`
2. 跑 `bash agent-launcher.sh --dry-run --tool claude --auth anthropic-console --dir /tmp --session foo-ancestor-claude`，确认：
   - 退出码 0
   - 输出**不含** "profile not v2" / "ancestor-preflight"
3. 跑 `bash agent-launcher.sh --help` 确认 --skip-ancestor-preflight 选项不再出现

## 验证（A + B 完成后一起跑）

```bash
cd /Users/ywf/ClawSeat
bash -n scripts/install.sh && echo "install.sh syntax ok"
bash -n core/launchers/agent-launcher.sh && echo "launcher syntax ok"
pytest tests/test_install_isolation.py tests/test_agent_admin_session_isolation.py tests/test_launcher_no_v05_preflight.py -q
```

期望：全 pass，无回归。

手动 e2e（如能在 cartooner / mor 等已有项目跑一次最好）：
```bash
python3 core/scripts/agent_admin.py session start-engineer --project <existing> <seat>
# 期望：tmux session 起来，HOME 在 ~/.agent-runtime/identities/.../home
# 期望：seat 内 echo $HOME 显示 sandbox 路径
# 期望：未踩 v0.5 preflight
```

## 约束

- **不改 agent-launcher.sh 的 run_*_runtime / 三 tool 实际启动逻辑**（行 934-1193 不动）
- **不改 install.sh**（已 ISOLATION-046 落地）
- **不改 docs**（已 ARCH-CLARITY-047 落地）；但若 plist 安装彻底删除，相应在 INSTALL.md / ARCHITECTURE.md 加一句"Phase-B patrol 由 memory Stop hook 取代"
- **不合并** `launcher_custom_env_file_for_session` 到 launcher（那是后续 P3 优化，本次不做）
- 不破坏 cartooner / mor / cartooner-web 等已有项目的 daily-driver 流程

## Deliverable

`.agent/ops/install-nonint/DELIVERY-ISOLATION-048.md`：

```
task_id: ISOLATION-048
owner: builder-codex
target: planner

## A1 调研结论
### L2 vs L3 identity / runtime_dir / secret_file delta
<对比表>
### 现存 ~/.agent-runtime/identities/ 快照
<find 输出>
### 现存 launchd patrol plist
<launchctl list 输出>

## A2 策略决策
策略 X，理由 Y，风险 Z

## 改动清单
- core/scripts/agent_admin_session.py (start_engineer 重写, 行号)
- core/scripts/agent_admin_runtime.py (兼容层, 如有)
- core/launchers/agent-launcher.sh (删除 1230-1351 + flag)
- agentctl.sh (run-engineer 入口处理)
- tests/test_agent_admin_session_isolation.py (新建)
- tests/test_launcher_no_v05_preflight.py (新建)

## Verification
- bash -n / pytest 输出
- 现有项目 e2e 手跑结果

## Notes
- 兼容性迁移（如有）
- Phase-B plist 未来归宿
- 已知遗留 / 后续 P2/P3 hook
```

**不 commit**。

## 已知坑

1. `agent_admin_runtime` 的 secret 文件可能和 launcher 期望格式不同。launcher 期望 env file 含 `ANTHROPIC_AUTH_TOKEN=...` / `ANTHROPIC_API_KEY=...` 等；L2 现有 secret 文件是不是这种格式要 verify。如果不是，要么转格式，要么复用 install.sh 的 `--custom-env-file` 路径。
2. `agentctl.sh run-engineer` 可能除 SessionService 外还有别的 caller（如 patrol 脚本、heartbeat manifest 安装）。删之前必须 grep 全局。
3. heartbeat manifest 写入逻辑（`provision_session_heartbeat`）仍在 SessionService 后链上；改 start_engineer 不要破坏 heartbeat provisioning 顺序。
4. `_assert_session_running()` 现在验证"tmux session 存在 + 至少有一个 pane"；切到 launcher 后 launcher 内部已经 `tmux new-session`，所以同样的 assert 仍能通过。但要确认 launcher 启动是同步的（headless 模式下 `tmux new-session -d` 立即返回，session 立即可见）。
