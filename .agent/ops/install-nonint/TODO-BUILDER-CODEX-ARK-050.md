# TODO — ARK-050 (ARK 火山方舟 provider 完整支持)

```
task_id: ARK-050
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P1
subagent-mode: OPTIONAL (单 agent，4 处点状修复)
scope: 把 ARK (火山方舟，endpoint https://ark.cn-beijing.volces.com/api/coding) 补齐为 v0.7 first-class claude-code provider
```

## Context

用户机器已配 ARK：`~/.agent-runtime/secrets/claude/ark.env` 含 `ARK_API_KEY / ARK_BASE_URL / ARK_MODEL`。

Phase-A walk-through 推演发现 4 处缺陷，ARK seat 目前**起不来**：

| # | 位置 | 现状 | 后果 |
|---|------|------|------|
| C1 | `scripts/install.sh:149-190` detect_provider Python block | 只识别 MINIMAX/ANTHROPIC/DASHSCOPE/CLAUDE_CODE_OAUTH_TOKEN/oauth；无 ARK_* 分支 | install.sh Step 3 菜单永远看不到 ARK |
| C2 | `core/scripts/agent_admin_session.py:295-326` `_custom_env_payload` | claude 分支只读 ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY / OPENAI_API_KEY | ancestor B3.5 `switch-harness --provider ark` → start-engineer 报 "missing API key" |
| C3 | secret 路径双轨 | shared: `~/.agent-runtime/secrets/claude/ark.env` (launcher 用 ARK_* names)；per-engineer: `~/.agents/secrets/claude/<provider>/<engineer>.env` (agent_admin 用 ANTHROPIC_* names) | 两边都没对齐；agent_admin 找不到 ARK secret |
| C4 | install.sh `select_provider` custom_api 分支 | `PROVIDER_MODEL` 只给 minimax 固定 `MiniMax-M2.7-highspeed`，其他 custom_api 空 | ARK 菜单选中后没传 `ark-code-latest` → Claude Code 用默认 model → endpoint 报错 |

## 调研先做（写进 DELIVERY）

1. 读 `agent_admin_session.py` 的 `_custom_env_payload`、`_launcher_auth_for`、`_launcher_runtime_dir` 三个方法看 ARK seat 经过的完整链路
2. 读 `agent_admin_runtime.py:228` `secret_file_for()` 确认 per-engineer 路径生成规则
3. 跑 `ls ~/.agents/secrets/claude/` 看现有 provider 惯例（应该只有 `minimax/<engineer>.env` 结构）
4. 读 `core/launchers/agent-launcher.sh:970-988` `run_claude_runtime` custom 分支确认 launcher 消费 `LAUNCHER_CUSTOM_API_KEY / BASE_URL / MODEL` 的方式

## 修复

### C1 — install.sh detect_provider 识别 ARK_*

`scripts/install.sh:149` Python block 加分支（在现有 DASHSCOPE 之后、oauth 之前）：

```python
k, b = lookup("keys.ARK_API_KEY.value"), lookup("keys.ARK_BASE_URL.value")
if k:
    default_base = b or "https://ark.cn-beijing.volces.com/api/coding"
    add("ark", f"claude-code + ARK 火山方舟 ({default_base})", k, default_base)
```

**注意**：candidates list 结构当前是 4-tuple `(mode, label, key, base)`。model 在 select_provider 阶段按 mode 硬编码补（见 C4）。**不扩展 tuple 结构**（避免触动 test_install_isolation.py 等 4 个测试）。

### C2 — agent_admin _custom_env_payload 支持 ARK_* 别名

`core/scripts/agent_admin_session.py:286-326` `_custom_env_payload` claude 分支：

```python
if session.tool == "claude":
    secret_env = self._parse_env_file(session.secret_file)
    api_key = (
        secret_env.get("ANTHROPIC_AUTH_TOKEN")
        or secret_env.get("ANTHROPIC_API_KEY")
        or secret_env.get("OPENAI_API_KEY")
        or secret_env.get("ARK_API_KEY")           # NEW
    )
    if not api_key:
        raise SessionStartError(...)
    payload = {"LAUNCHER_CUSTOM_API_KEY": api_key}
    base_url = (
        secret_env.get("ANTHROPIC_BASE_URL")
        or secret_env.get("OPENAI_BASE_URL")
        or secret_env.get("OPENAI_API_BASE")
        or secret_env.get("ARK_BASE_URL")          # NEW
        or ""
    )
    # provider-specific defaults (已有 minimax / xcode-best / anthropic-console)
    if session.provider == "ark" and not base_url:
        base_url = "https://ark.cn-beijing.volces.com/api/coding"
    # ... (rest unchanged)
    if base_url:
        payload["LAUNCHER_CUSTOM_BASE_URL"] = base_url
    model = (
        secret_env.get("ANTHROPIC_MODEL")
        or secret_env.get("OPENAI_MODEL")
        or secret_env.get("ARK_MODEL")             # NEW
        or ""
    )
    if session.provider == "ark" and not model:
        model = "ark-code-latest"
    if model:
        payload["LAUNCHER_CUSTOM_MODEL"] = model
    return payload
```

### C3 — secret 路径 bridging（per-engineer secret 自动 seed）

`agent_admin switch-harness` 已经会调 `ensure_api_secret_ready` 前置。扩展一个自动 seed 机制：

**方案**：当 `switch-harness --tool claude --mode api --provider <P>` 时，如果 per-engineer secret 文件（`~/.agents/secrets/claude/<P>/<engineer>.env`）不存在，**检查是否有 shared secret**（`~/.agent-runtime/secrets/claude/<P>.env`），存在就自动 copy（或 hard-link）过去。

具体在 `core/scripts/agent_admin_switch.py` 的 `ensure_api_secret_ready` 或 `session_switch_harness` 路径里加：

```python
def _maybe_seed_from_shared(self, session) -> None:
    """如果 per-engineer secret 空，检查 launcher shared secret 并 seed。"""
    target = self.hooks.secret_file_for(session.tool, session.provider, session.engineer_id)
    if target.exists() and target.read_text(encoding="utf-8").strip():
        return
    shared = Path.home() / ".agent-runtime" / "secrets" / session.tool / f"{session.provider}.env"
    if shared.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(shared, target)
        target.chmod(0o600)
        print(f"secret_seed: copied {shared} -> {target}", file=sys.stderr)
```

在 `switch-harness` rebind 成功后、`session start-engineer` 前调一次。

**好处**：用户只需要在 `~/.agent-runtime/secrets/claude/ark.env` 放一次 ARK key（shared），ancestor B3.5 给任意 seat 切 ARK provider 时自动 seed per-engineer file，不需要为每个 seat 手动 `engineer secret-set`。

**兼容性**：minimax / xcode-best 已经 pre-populated per-engineer secret，seed 路径只在文件不存在时激活，不覆盖现有。

### C4 — install.sh select_provider custom_api 菜单带 default model

`scripts/install.sh` 菜单 candidate 选中时：

```bash
# 在 select_provider 命中 candidate 后（数字选择分支）：
case "$mode" in
  minimax)
    remember_provider_selection "$mode" "$key" "$base" "MiniMax-M2.7-highspeed" ;;
  ark)
    remember_provider_selection "$mode" "$key" "$base" "ark-code-latest" ;;
  *)
    remember_provider_selection "$mode" "$key" "$base" ;;
esac
```

对应 dry-run / FORCE_PROVIDER 分支同样加 ark case。

`write_provider_env` 的 case 也加 ark：

```bash
case "$mode" in
  minimax) ... ;;
  ark)
    export_line ANTHROPIC_BASE_URL "$base"
    export_line ANTHROPIC_AUTH_TOKEN "$key"
    export_line ANTHROPIC_MODEL "${PROVIDER_MODEL:-ark-code-latest}"
    echo 'export API_TIMEOUT_MS=3000000'
    echo 'export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1'
    echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY'
    ;;
  custom_api) ... ;;
  ...
esac
```

`launcher_auth_for_provider` / `launcher_custom_env_file_for_session` 的 case 也要为 ark 添加分支（映射到 launcher `--auth custom` + fill LAUNCHER_CUSTOM_*）。

## 约束

- **不破坏 minimax / xcode-best / anthropic-console / oauth / oauth_token 现有路径**
- **不改 launcher.sh**（launcher 已能处理 LAUNCHER_CUSTOM_*）
- **不扩展 candidates tuple 结构**（保持 4-tuple，避免触动下游测试）
- ark.env 保留 ARK_* KEY names 不变（用户已写入，不要求用户改）

## 追加 C5 — memory seat 必须是机器级 singleton daemon（新需求）

**问题**：`scripts/install.sh` 当前在 main() 尾部无条件 `launch_seat "machine-memory-claude" "$MEMORY_WORKSPACE"` + `install_memory_hook` + `open_iterm_window "$(memory_payload)"`。`launch_seat` 内部会 `tmux kill-session -t "=$session"` 再 launch——**如果用户已在另一个项目跑过 install.sh，memory 已经作为 daemon 在线伴随其他项目的 Phase-B 巡检**，再跑 install 新项目会**把老 memory kill 掉重启**。

memory 是**机器级 singleton**（不是 per-project），`~/.agents/workspaces/<project>/memory` workspace 也是共享的（MEMORY-035 的 Stop hook 装在这里）——多项目共用一个 daemon。

**修复** `scripts/install.sh`：

### C5a — launch memory 前先检查已存在

把 main() 里的 memory launch 块从：
```bash
install_memory_hook
note "Step 8: start memory session + iTerm window"
launch_seat "machine-memory-claude" "$MEMORY_WORKSPACE"
open_iterm_window "$(memory_payload)" memory_window_id
```

改成：
```bash
note "Step 8: ensure memory singleton daemon"
if tmux has-session -t '=machine-memory-claude' 2>/dev/null; then
  echo "memory seat already running (machine-memory-claude), reusing."
  # hook 仍然幂等检查（不同项目可能需要不同 workspace 的 Stop hook 聚合）
  install_memory_hook
  # iTerm window 也幂等：如果已有 machine-memory-claude window 就 focus，不重开
  MEMORY_WINDOW_EXISTS=$(check_iterm_window_exists "machine-memory-claude")
  if [[ "$MEMORY_WINDOW_EXISTS" != "1" ]]; then
    open_iterm_window "$(memory_payload)" memory_window_id
  else
    echo "memory iTerm window already open, skipping open."
  fi
else
  install_memory_hook
  launch_seat "machine-memory-claude" "$MEMORY_WORKSPACE"
  open_iterm_window "$(memory_payload)" memory_window_id
fi
```

### C5b — `launch_seat` 函数保护（防御性）

不改 `launch_seat` 通用逻辑（其他 seat 允许 kill+relaunch），但在 main() 这个调用点用 has-session 守门（上面 C5a 已覆盖）。

### C5c — `install_memory_hook.py` 幂等化

确认 [core/skills/memory-oracle/scripts/install_memory_hook.py](core/skills/memory-oracle/scripts/install_memory_hook.py) 已经幂等（检查 Stop hook 已装则不重复写入 settings.json）。如果还没幂等：加一个"detect existing hook → skip"分支。

### C5d — `check_iterm_window_exists` helper 新增

`scripts/install.sh` 新增小 helper：
```bash
check_iterm_window_exists() {
  local title="$1"
  if ! command -v osascript >/dev/null 2>&1; then
    echo "0"; return
  fi
  local exists
  exists=$(osascript -e "tell application \"iTerm\"
    repeat with w in windows
      if name of w contains \"$title\" then return \"1\"
    end repeat
    return \"0\"
  end tell" 2>/dev/null || echo "0")
  printf '%s\n' "$exists"
}
```

### C5e — `memory_payload` workspace 策略

当前 `memory_payload` 的 pane command 是 `tmux attach -t '=machine-memory-claude'`，与 session 单例一致 ✅。不改。

### 测试

`tests/test_install_memory_singleton.py` 新增：
1. mock `tmux has-session` 返回 rc=0 → install.sh 不 launch memory、不 open new iTerm window
2. mock `tmux has-session` 返回 rc=1 → install.sh launch memory + open iTerm window
3. `install_memory_hook.py` 在已有 hook 时是 no-op

## 原则

memory 是 **daemon**，不是 per-project session。任何"初始化新项目"流程都必须：
- ✅ 尊重已存在的 memory daemon（不 kill）
- ✅ 只在 daemon 缺失时才启
- ✅ 不复制 memory workspace（共享 `~/.agents/workspaces/*/memory` 聚合）
- ✅ hook 可重复装但要幂等

未来任何新增 `scripts/*.sh` / `agent_admin project bootstrap` / ancestor B2 verify-memory 路径都应该遵守这个不变式。ARK-050 顺带把 install.sh 这块锁死。

## 追加 C6 — install.sh 自动 send Phase-A kickoff prompt

**问题**：Step 9 只 `tmux send-keys Enter × 3` 唤醒 session；真正的 Phase-A 启动 prompt 写在 `OPERATOR-START-HERE.md` 文件里等 operator 手动粘贴。LIVE-047 / smoke02 实测显示 operator 经常忘记粘贴 → ancestor 永远停在 welcome 界面。

**修复** `scripts/install.sh` main() 尾部：Step 9 在 Enter 唤醒后**自动 send Phase-A kickoff prompt**：

```bash
note "Step 9: focus ancestor + auto-kickoff Phase-A"
run sleep 3
focus_iterm_window "$GRID_WINDOW_ID" "ancestor"
# 3-Enter flush 唤醒 claude TUI（已存在）
run tmux send-keys -t "$PROJECT-ancestor" Enter
run sleep 0.5
run tmux send-keys -t "$PROJECT-ancestor" Enter
run sleep 0.5
run tmux send-keys -t "$PROJECT-ancestor" Enter

# NEW: 等 claude TUI ready，然后 send Phase-A kickoff prompt
if [[ "$DRY_RUN" != "1" ]]; then
  note "Step 9.5: auto-send Phase-A kickoff prompt"
  sleep 12  # 给 claude TUI welcome + skill load 时间
  local kickoff="读 $BRIEF_PATH 开始 Phase-A。按 brief 顺序执行 B0-B7，每步向我汇报或 CLI prompt 我确认。不要 fan-out specialist seat；spawn engineer seat 要 one-at-a-time。"
  tmux send-keys -t "$PROJECT-ancestor" "$kickoff" 2>/dev/null || true
  sleep 1
  tmux send-keys -t "$PROJECT-ancestor" Enter 2>/dev/null || true
fi
```

**关键点**：
- prompt 用 **absolute BRIEF_PATH**（不依赖 `$CLAWSEAT_ANCESTOR_BRIEF` env var，因为 C7 修之前 L2 重启会丢 env）
- `sleep 12` 给 claude TUI welcome screen + skill load 时间（pyenv 冷启需要 ~10 秒）
- `tmux send-keys ... || true` 容错 session 已退的场景
- dry-run 不执行 send

**OPERATOR-START-HERE.md 保留作为 fallback**（4g）：供 operator 想 review 整个 Phase-A 提要 / auto-send 失败时重来。

## 追加 C7 — agent_admin session start-engineer 对 ancestor 补 brief env

**问题**：[agent_admin_session.py:454-455](core/scripts/agent_admin_session.py:454) L2 path 只 set `CLAWSEAT_ROOT`，不 set `CLAWSEAT_ANCESTOR_BRIEF`。任何 ancestor 重启（Phase-B 自愈 / operator 手动 `session start-engineer ancestor` / iTerm crash recovery）都丢 env var → ancestor 启动后查不到 brief 卡住。

**修复** `core/scripts/agent_admin_session.py:start_engineer()`：

```python
env = dict(os.environ)
env["CLAWSEAT_ROOT"] = str(Path(self.hooks.launcher_path).resolve().parents[2])

# NEW: ancestor seat 需要 CLAWSEAT_ANCESTOR_BRIEF env var（install.sh 首次 launch 时传，重启后要从 project path 反算）
if session.engineer_id == "ancestor":
    real_home = Path(os.environ.get("CLAWSEAT_REAL_HOME", str(Path.home())))
    brief_path = real_home / ".agents" / "tasks" / session.project / "patrol" / "handoffs" / "ancestor-bootstrap.md"
    if brief_path.is_file():
        env["CLAWSEAT_ANCESTOR_BRIEF"] = str(brief_path)
    # 如 brief 不存在（project 未跑完 install Step 4），不 set env；ancestor 启动时可能会 raise 但这是另一层问题

result = subprocess.run(cmd, check=False, ..., env=env, ...)
```

**兼容**：现有非 ancestor seat（planner/builder/... + memory）不受影响。

## C6 + C7 测试

`tests/test_install_auto_kickoff.py` + `tests/test_session_start_ancestor_env.py`：

1. install.sh dry-run **不** send kickoff（避免对 test pane 产生副作用）
2. install.sh 非 dry-run 跑到 Step 9.5 时真 send 指定 prompt（mock tmux send-keys 捕获 args）
3. agent_admin start-engineer ancestor --project foo 后，subprocess env 含 `CLAWSEAT_ANCESTOR_BRIEF=<foo bootstrap path>`
4. agent_admin start-engineer planner --project foo 后，subprocess env **不**含 ancestor brief env（避免污染）

## 测试

新增 `tests/test_ark_provider_support.py`：

1. `detect_provider` 能从 mock credentials.json（含 ARK_API_KEY + ARK_BASE_URL）emit 一个 mode=ark 的 candidate
2. install.sh dry-run `--provider ark --api-key sk-xxx` 能跳菜单 + write_provider_env 写出 ANTHROPIC_MODEL=ark-code-latest
3. agent_admin `_custom_env_payload` 对 session.provider=ark，读含 ARK_API_KEY 的 secret file，正确生成 `LAUNCHER_CUSTOM_API_KEY` + `LAUNCHER_CUSTOM_BASE_URL=https://ark.cn-beijing.volces.com/api/coding` + `LAUNCHER_CUSTOM_MODEL=ark-code-latest`
4. `switch-harness --provider ark` 成功 seed per-engineer secret file 从 shared ark.env（如果 shared 存在）
5. per-engineer secret 已存在时不 overwrite

回归：
- 跑 `test_install_isolation.py / test_install_lazy_panes.py / test_agent_admin_session_isolation.py / test_ancestor_brief_spawn49.py` 全通过

## Deliverable

`.agent/ops/install-nonint/DELIVERY-ARK-050.md`：

```
task_id: ARK-050
owner: builder-codex
target: planner

## 调研结论
<_custom_env_payload / secret_file_for / launcher custom 的链路图>

## 改动清单
- scripts/install.sh (C1 + C4)
- core/scripts/agent_admin_session.py (C2)
- core/scripts/agent_admin_switch.py (C3 seed 机制)
- tests/test_ark_provider_support.py (新增)

## Verification
- bash -n / pytest 输出
- 手 e2e：配 ark.env + bash install.sh --project arktest --provider ark --api-key sk-... → ancestor 能起来
- 手 e2e：ancestor 跑 switch-harness --provider ark → per-engineer secret 自动 seed → start-engineer 成功

## Notes
- ARK_* KEY 名保留 (shared file)；per-engineer file 由 C3 seed 自动用同名 KEY 复制
- v0.8 followup: 考虑 provider registry 配置化（避免新 provider 再堆分支）
```

**不 commit**。
