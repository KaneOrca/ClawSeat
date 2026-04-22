task_id: ARK-050
owner: builder-codex
target: planner

## 结果

- ARK（火山方舟）已补齐为 v0.7 first-class `claude/api` provider。
- `install.sh` 现在能检测 `ARK_*`、菜单选择 `ark`、以及 `--provider ark --api-key ...` 直通安装，并自动补 `base_url=https://ark.cn-beijing.volces.com/api/coding` 与 `model=ark-code-latest`。
- `agent_admin session start-engineer` 现在支持从 per-engineer secret 里的 `ARK_API_KEY / ARK_BASE_URL / ARK_MODEL` 生成 launcher custom env；`switch-harness --provider ark` 也能在 per-engineer secret 缺失时，从 shared `~/.agent-runtime/secrets/claude/ark.env` 自动 seed。
- `machine-memory-claude` 现在按机器级 singleton 处理：已存在时 install 只复用，不 kill、不重启；iTerm 窗口存在时也不再重开。
- 追加 C6/C7 后，install 的 Phase-A 不再依赖 operator 手动粘贴：Step 9.5 会在 TUI ready 后自动发送基于绝对 `BRIEF_PATH` 的 kickoff prompt；`agent_admin session start-engineer` 在 ancestor 重启时会把 `CLAWSEAT_ANCESTOR_BRIEF` 重新写回 subprocess env。

## 调研结论

1. `core/scripts/agent_admin_session.py`
   - `_launcher_auth_for()` 对 Claude `auth_mode=api` 统一返回 launcher `custom`，所以 ARK 不需要新增 launcher auth 类型。
   - `_custom_env_payload()` 是 Claude API seats 把 secret file 映射成 `LAUNCHER_CUSTOM_*` 的关键入口；这里原先不认 `ARK_*`，是 ARK seat 起不来的主因。
   - `_launcher_runtime_dir()` 对 Claude API seats 走 `~/.agent-runtime/identities/claude/api/custom-<session>`，ARK 会自然复用现有 sandbox HOME 隔离。
2. `core/scripts/agent_admin_runtime.py:secret_file_for()`
   - per-engineer secret 路径规则是 `~/.agents/secrets/<tool>/<provider>/<engineer>.env`，所以 ARK 对应路径是 `~/.agents/secrets/claude/ark/<engineer>.env`。
3. `ls ~/.agents/secrets/claude/`
   - 现状只有 `minimax/<engineer>.env` 这种 per-engineer provider 目录，没有 shared `ark.env` 镜像，说明确实需要 shared→per-engineer seed bridging。
4. `core/launchers/agent-launcher.sh:run_claude_runtime`
   - custom 分支消费 `LAUNCHER_CUSTOM_API_KEY / LAUNCHER_CUSTOM_BASE_URL / LAUNCHER_CUSTOM_MODEL`，不要求 provider 名字；因此无需改 launcher，本次只需把上游 env 填对。
5. `core/skills/memory-oracle/scripts/install_memory_hook.py`
   - 已具备幂等性：相同 Stop hook 已存在时 `changed=False`，不需要额外改代码。
6. `scripts/install.sh` / `core/scripts/agent_admin_session.py`
   - Step 9.5 的 auto-kickoff 只能依赖绝对 `BRIEF_PATH`，不能依赖启动时环境变量；因此 ancestor 重启时必须由 `start_engineer()` 反算 `CLAWSEAT_ANCESTOR_BRIEF` 回填 subprocess env。
   - `OPERATOR-START-HERE.md` 保持 fallback：它仍然会落盘，供 operator 手动接管或 kickoff 自动发送失败时使用。

## 改动清单

- `scripts/install.sh`
  - `detect_provider()` 新增 `ARK_API_KEY / ARK_BASE_URL` 检测，emit `mode=ark`
  - `select_provider()` 新增 `ark`：
    - 菜单选择时自动补 `ark-code-latest`
    - `--provider ark --api-key ...` 无需 detect 也可直通
    - dry-run placeholder 支持 `ark`
  - `write_provider_env()` 新增 `ark` case，写出 `ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL / ANTHROPIC_MODEL`
  - `seat_auth_mode_for_provider_mode()` / `seat_provider_for_provider_mode()` / `seat_model_for_provider_mode()` 新增 `ark`
  - `write_bootstrap_secret_file()` / `launcher_auth_for_provider()` / `launcher_custom_env_file_for_session()` 新增 `ark`
  - 新增 `check_iterm_window_exists()`（`osascript` helper）
  - Step 8 改成 memory singleton 守护：
    - session 已存在：复用，不 launch，不 kill
    - iTerm memory window 已存在：跳过重开
    - session 缺失：保持原先 launch + open window
  - Step 9.5 新增 auto-kickoff：
    - `sleep 12` 等 TUI ready
    - 用绝对 `BRIEF_PATH` 发送 Phase-A kickoff prompt
    - prompt 发送失败时容错，不中断 install
- `core/scripts/agent_admin_config.py`
  - `CLAUDE_API_PROVIDER_CONFIGS` 新增 `ark`
  - `SUPPORTED_RUNTIME_MATRIX["claude"]["api"]` 新增 `ark`
- `core/scripts/agent_admin_session.py`
  - Claude `_custom_env_payload()` 新增 `ARK_API_KEY / ARK_BASE_URL / ARK_MODEL` 别名读取
  - `provider=ark` 时补默认 `base_url` 和 `model`
  - `start_engineer()` 在 `engineer_id == "ancestor"` 时回填 `CLAWSEAT_ANCESTOR_BRIEF`
- `core/scripts/agent_admin_switch.py`
  - `shared_secret_candidates()` 新增 `~/.agent-runtime/secrets/claude/ark.env`
  - `switch-harness --provider ark` 现在能自动 seed per-engineer secret
- 测试
  - `tests/test_install_isolation.py`
    - tmux stub 改为默认 `has-session` 对 memory 返回 rc=1，避免 singleton 分支把所有旧测试误判成“memory 已存在”
    - 额外加了 `sleep` no-op stub，避免 C6 的 12 秒等待拖慢 install 回归
  - `tests/test_ark_provider_support.py`
  - `tests/test_install_memory_singleton.py`
  - `tests/test_install_auto_kickoff.py`
  - `tests/test_session_start_ancestor_env.py`

## 兼容性说明

- minimax / xcode-best / anthropic-console / oauth / oauth_token 既有路径未改语义。
- `install.sh` 没有扩展 provider candidates tuple 结构，仍保持 `(mode, label, key, base)` 4-tuple。
- launcher 本身未修改；ARK 仍通过现有 `custom` auth 路径进入相同 sandbox HOME 隔离。
- shared secret seed 只在 per-engineer secret 缺失或为空时触发，不覆盖既有 per-engineer secret。
- memory singleton 只在 `scripts/install.sh` 调用点守门；其他 seat 仍保留原来的 kill+relaunch 行为。

## Verification

```text
$ bash -n scripts/install.sh

$ pytest tests/test_ark_provider_support.py \
    tests/test_install_auto_kickoff.py \
    tests/test_session_start_ancestor_env.py \
    tests/test_install_memory_singleton.py \
    tests/test_install_isolation.py \
    tests/test_install_lazy_panes.py \
    tests/test_agent_admin_session_isolation.py -q
45 passed, 1 warning in 6.91s

$ git diff --check
```

## Patch 历程

- 先落 C1-C5：ARK provider first-class、memory singleton、per-engineer secret seed bridge。
- 再追加 C6：install Step 9.5 自动发送 Phase-A kickoff prompt，避免 operator 忘记手动粘贴 brief。
- 再追加 C7：ancestor 重启时由 `agent_admin session start-engineer` 反算 `CLAWSEAT_ANCESTOR_BRIEF`，保证 Phase-A 重启恢复。
- 为了不让 C6 的 `sleep 12` 拉慢 install 回归，补了 `tests/test_install_isolation.py` 的 `sleep` no-op stub。

## Notes

- 本次没有 commit。
- `install_memory_hook.py` 只做了调研确认，未修改实现。
- worktree 中仍有其他未提交改动；本交付只在其上增量修改，没有回滚它们。
