task_id: ISOLATION-048
owner: builder-codex
target: planner

## A1 调研结论

### L2 vs L3 identity / runtime_dir / secret_file delta

| 项 | L2 既有 (`agent_admin_runtime.py`) | L3 既有 (`agent-launcher.sh`) | 本次 048 落地 |
| --- | --- | --- | --- |
| identity 命名 | `tool.mode.provider.[project].engineer` | 无独立 identity 字段；runtime 以 `auth-session` 命名 | **保留 L2 identity / secret_file 作为 metadata SSOT** |
| tmux session 名 | `project-engineer-tool` | 默认 `tool-auth-slug(workdir)`，但支持 `--session` 覆盖 | **保持 L2 session 名不变**，启动时显式传 `--session` |
| runtime_dir | `~/.agents/runtime/identities/<tool>/<mode>/<identity>` | `~/.agent-runtime/identities/<tool>/<auth>/<auth>-<session>`；oauth/chatgpt 走 real HOME | **实际 launch 改走 L3 runtime_dir**；对 sandboxed auth 把 `session.runtime_dir` 回写成真实 L3 路径 |
| secret 文件 | `~/.agents/secrets/<tool>/<provider>/<engineer>.env` | Claude/Gemini native auth 读 shared secret；custom auth 读一次性 `--custom-env-file` | **继续以 L2 per-seat secret 为输入 SSOT**；按 tool/auth 转成 launcher shared secret 或 one-shot custom env |

### 关键结论

1. `start_engineer()` 在 048 之前仍直接 `tmux new-session ... agentctl run-engineer ...`，完全绕过 L3。
2. 如果只把 `codex api/xcode-best` 映射到 launcher 原生 `xcode`，会丢旧 L2 路径里 `config.toml` 的 `base_url/model` 语义；launcher 原生 `xcode` 只会沿用 real `~/.codex/config.toml`。
3. 为了满足“同一 seat 经 L1 vs L2 启动落到同一 sandbox HOME”，Claude API seats 必须和 `install.sh` 一样落到 launcher `custom` 命名空间，而不是 `anthropic-console` / `minimax` / `xcode` 原生命名空间。

### 现存 `~/.agent-runtime/identities/` 快照

```text
/Users/ywf/.agent-runtime/identities
/Users/ywf/.agent-runtime/identities/claude
/Users/ywf/.agent-runtime/identities/claude/api
/Users/ywf/.agent-runtime/identities/claude/api/custom-audit-qa-1-claude
/Users/ywf/.agent-runtime/identities/claude/api/custom-audit-qa-1-claude/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-audit-qa-1-claude/xdg
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-ancestor
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-ancestor/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-builder
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-builder/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-designer
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-designer/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-planner
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-planner/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-qa
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-qa/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-reviewer
/Users/ywf/.agent-runtime/identities/claude/api/custom-isol46-reviewer/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-ancestor
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-ancestor/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-builder
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-builder/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-designer
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-designer/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-planner
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-planner/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-qa
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-qa/home
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-reviewer
/Users/ywf/.agent-runtime/identities/claude/api/custom-smoketest-reviewer/home
/Users/ywf/.agent-runtime/identities/claude/api/minimax-claude-minimax-coding
/Users/ywf/.agent-runtime/identities/claude/api/minimax-claude-minimax-coding/home
/Users/ywf/.agent-runtime/identities/claude/api/minimax-claude-minimax-coding/xdg
/Users/ywf/.agent-runtime/identities/claude/api/xcode
/Users/ywf/.agent-runtime/identities/claude/oauth
/Users/ywf/.agent-runtime/identities/claude/oauth/main
/Users/ywf/.agent-runtime/identities/claude/oauth/main/home
/Users/ywf/.agent-runtime/identities/claude/oauth/main/xdg
/Users/ywf/.agent-runtime/identities/claude/oauth_token
/Users/ywf/.agent-runtime/identities/claude/oauth_token/oauth_token-demo-ancestor-claude
/Users/ywf/.agent-runtime/identities/claude/oauth_token/oauth_token-demo-ancestor-claude/home
/Users/ywf/.agent-runtime/identities/claude/oauth_token/oauth_token-demo-ancestor-claude/xdg
/Users/ywf/.agent-runtime/identities/claude/oauth_token/oauth_token-install-ancestor-claude
/Users/ywf/.agent-runtime/identities/claude/oauth_token/oauth_token-install-ancestor-claude/home
/Users/ywf/.agent-runtime/identities/claude/oauth_token/oauth_token-install-ancestor-claude/xdg
/Users/ywf/.agent-runtime/identities/codex
/Users/ywf/.agent-runtime/identities/codex/api
/Users/ywf/.agent-runtime/identities/codex/api/api-install-reviewer-1-codex
/Users/ywf/.agent-runtime/identities/codex/api/api-install-reviewer-1-codex/codex-home
/Users/ywf/.agent-runtime/identities/codex/api/api-install-reviewer-1-codex/home
/Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex
/Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex/codex-home
/Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex/home
/Users/ywf/.agent-runtime/identities/codex/api/minimax-install-reviewer-1-codex
/Users/ywf/.agent-runtime/identities/codex/api/minimax-install-reviewer-1-codex/codex-home
/Users/ywf/.agent-runtime/identities/codex/api/minimax-install-reviewer-1-codex/home
/Users/ywf/.agent-runtime/identities/codex/api/xcode
/Users/ywf/.agent-runtime/identities/codex/api/xcode-debug-reviewer-codex
/Users/ywf/.agent-runtime/identities/codex/api/xcode-debug-reviewer-codex/codex-home
/Users/ywf/.agent-runtime/identities/codex/api/xcode-debug-reviewer-codex/home
/Users/ywf/.agent-runtime/identities/codex/api/xcode/codex
/Users/ywf/.agent-runtime/identities/codex/api/xcode/home
/Users/ywf/.agent-runtime/identities/codex/api/xcode/xdg
/Users/ywf/.agent-runtime/identities/codex/oauth
/Users/ywf/.agent-runtime/identities/codex/oauth/main
/Users/ywf/.agent-runtime/identities/codex/oauth/main/codex
/Users/ywf/.agent-runtime/identities/codex/oauth/main/home
/Users/ywf/.agent-runtime/identities/codex/oauth/main/xdg
/Users/ywf/.agent-runtime/identities/gemini
/Users/ywf/.agent-runtime/identities/gemini/api
/Users/ywf/.agent-runtime/identities/gemini/api/primary
/Users/ywf/.agent-runtime/identities/gemini/oauth
/Users/ywf/.agent-runtime/identities/gemini/oauth/main
/Users/ywf/.agent-runtime/identities/gemini/oauth/main/home
/Users/ywf/.agent-runtime/identities/gemini/oauth/main/xdg
```

### 现存 L2 项目 sessions

```text
$ tmux list-sessions
cartooner-builder-1-codex: 1 windows (attached)
cartooner-designer-1-gemini: 1 windows (attached)
cartooner-planner-claude: 1 windows (attached)
cartooner-qa-1-claude: 1 windows (attached)
claude-minimax-coding: 1 windows (attached)
codex-chatgpt-coding: 1 windows (attached)

$ ls ~/.agents/sessions/
audit
cartooner
install
```

### B1：launchd patrol plist 快照

```text
$ ls ~/Library/LaunchAgents/com.clawseat.*.plist
/Users/ywf/Library/LaunchAgents/com.clawseat.install.ancestor-patrol.plist

$ launchctl list | grep clawseat
-	1	com.clawseat.install.ancestor-patrol
```

### B1：`profile-dynamic` 现状

- `scripts/install.sh` 里已经**没有** `profile-dynamic` 生成或消费路径。
- `core/skills/clawseat-install/` 里仍有 legacy 文案/辅助脚本提到 `~/.agents/profiles/<project>-profile-dynamic.toml`，但本次 048 不再让 launcher 依赖它们。

## A2 策略决策

采用 **策略 B（L2 实际启动接 L3）**，但做了两处兼容性收口：

1. `claude api/*` 统一映射到 launcher `custom`
   理由：和 046 的 `install.sh` 一致，保证同一 session 经 L1 / L2 启动落到同一 `custom-<session>` sandbox HOME。

2. `codex api/xcode-best` 也映射到 launcher `custom`
   理由：launcher 原生 `xcode` 只会用 shared `~/.codex/config.toml` + `auth.json`，会丢 L2 原先 `write_codex_api_config()` 写入的 `base_url/model` 语义；`custom` 才能一把把 `OPENAI_API_KEY + https://api.xcode.best/v1 + gpt-5.4` 带进去。

3. `gemini api/google-api-key` 保留 launcher 原生 `primary`
   理由：现有语义就是 plain env key，无额外 per-seat config 负担。

### 风险评估

- 风险 1：sandboxed seat 首次经 048 启动后，`session.runtime_dir` 会回写成真实 L3 路径。
  - 这是有意行为：让 session metadata、tmux pane banner、bootstrap 脚本都指向真实 HOME。
  - 已确认 `session_name`、`workspace`、`identity`、`secret_file` 不变。
- 风险 2：`reconcile_session_runtime()` 仍以旧 L2 公式校验 runtime_dir。
  - 目前只在 `start_engineer()` 前做一次修正，随后立刻被 L3 runtime 回写覆盖；功能正确，但未来若要彻底统一 metadata 公式，建议单独做 P2/P3 清理。
- 风险 3：现存 launchd Phase-B plist 仍在用户机上。
  - 本次按 TODO 要求**不 unload**，只删除 launcher 内嵌 preflight；后续由用户/ops 手动清理。

## 改动清单

- `core/scripts/agent_admin_session.py`
  - `236-406`: 新增 launcher auth / custom env / runtime_dir helper
  - `413-470`: `start_engineer()` 改为 subprocess 调 `core/launchers/agent-launcher.sh`
  - Claude API / CCR 统一走 launcher `custom`
  - Codex `xcode-best` 改走 launcher `custom`，保留 xcode-best endpoint/model 语义
- `core/scripts/agent_admin.py`
  - `960-961`: 修复 live 路径接线 bug，`ensure_api_secret_ready()` 改为调用 `SwitchHandlers.ensure_secret_ready()`
  - `998-1012`: `SessionService` hooks 接入 `launcher_path` / `write_session`
- `core/launchers/agent-launcher.sh`
  - 删除 v0.5 ancestor preflight 整段
  - 删除 `--skip-ancestor-preflight`
  - 删除 `--clone-from`
  - 不动 `run_claude_runtime` / `run_codex_runtime` / `run_gemini_runtime`
- `tests/test_agent_admin_session_isolation.py`
  - 新增，覆盖 L2 不再直接 `tmux new-session`
  - 覆盖 Claude / Codex / Gemini 三工具映射
  - 覆盖 custom env 文件内容与 `reset=True` 顺序
- `tests/test_launcher_no_v05_preflight.py`
  - 新增，覆盖 launcher 源码已无 v0.5 preflight artifact / help flag / ancestor dry-run
- `tests/test_install_isolation.py`
  - 只修测试环境注入：给 fake-root install 测试补 `CLAWSEAT_REAL_HOME`
  - 原因：当前 `install.sh` 会显式 `export HOME="$REAL_HOME"`，fake-root 测试也必须把“real home”钉到 fake HOME

## Verification

### Syntax / tests

```text
$ bash -n scripts/install.sh && echo install-ok
install-ok

$ bash -n core/launchers/agent-launcher.sh && echo launcher-ok
launcher-ok

$ pytest tests/test_install_isolation.py tests/test_agent_admin_session_isolation.py tests/test_launcher_no_v05_preflight.py -q
24 passed in 4.88s

$ pytest tests/test_session_stop_closes_iterm.py tests/test_launch_permissions.py -q
13 passed in 0.06s
```

### 现有项目 e2e 手跑

#### 1. Claude API seat（`audit/qa-1`）

```text
$ python3 core/scripts/agent_admin.py session start-engineer qa-1 --project audit --reset
qa-1: no HEARTBEAT_MANIFEST.toml present
audit-qa-1-claude

$ tmux capture-pane -pt audit-qa-1-claude -S -80
Claude Code · Custom API
Session:    audit-qa-1-claude
Directory:  /Users/ywf/.agents/workspaces/audit/qa-1
Model:      MiniMax-M2.7-highspeed
Endpoint:   https://api.minimaxi.com/anthropic
HOME:       /Users/ywf/.agent-runtime/identities/claude/api/custom-audit-qa-1-claude/home
AGENT_HOME: /Users/ywf
```

结论：L2 启动已明确落到 L3 `~/.agent-runtime/identities/.../home`，且未踩任何 v0.5 ancestor preflight。

#### 2. Codex API seat（`audit/reviewer-1`）

```text
$ python3 core/scripts/agent_admin.py session start-engineer reviewer-1 --project audit --reset
reviewer-1: heartbeat provisioning currently targets Claude sessions only
audit-reviewer-1-codex
```

该 seat 很快自退，未能保留 tmux pane banner；但 session metadata 与 runtime 目录已更新为：

```text
runtime_dir = "/Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex"

$ find /Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex -maxdepth 2 -type d
/Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex
/Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex/codex-home
/Users/ywf/.agent-runtime/identities/codex/api/custom-audit-reviewer-1-codex/home
```

结论：Codex 路径确实已走 launcher `custom` runtime，不再落旧 L2 `~/.agents/runtime/...`。

## Notes

- `agentctl run-engineer` / `build_engineer_exec()` **未删除**。
  - 原因：`core/engine/instantiate_seat.py` 和 parser / effective-launch 元数据仍引用它，当前不是 dead code。
- 现存 `~/Library/LaunchAgents/com.clawseat.install.ancestor-patrol.plist` **未卸载**。
  - 这是按 TODO 明确要求保留现状，不在 048 里做破坏性清理。
- live smoke 额外发现并修了一个真实接线 bug：
  - `agent_admin.py: ensure_api_secret_ready()` 之前误调了不存在的 `SwitchHandlers.ensure_api_secret_ready`
  - 若不修，真实 `session start-engineer` 会在 launcher 之前就抛 `AttributeError`
- 未做 commit。
