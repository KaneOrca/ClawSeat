# TODO — ISOLATION-046 (install.sh 切到 agent-launcher.sh 做 sandbox HOME 隔离)

```
task_id: ISOLATION-046
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: REQUIRED — 2 subagents (A=改造 install.sh, B=测试)
scope: 重写 install.sh 启 seat 的方式 + 测试
```

## Context

LIVE-043 测出 install.sh 的架构 gap：**没用 ClawSeat 已有的 sandbox HOME isolation**。

具体证据（planner 已 verify）：
- `core/launchers/agent-launcher.sh` 行 957/960/1070/1146 用 `~/.agent-runtime/identities/<tool>/<auth>/<auth_mode>-<session_name>` 作 sandbox HOME
- `core/scripts/agent_admin_runtime.py` 有 `is_sandbox_home` 判断、`LEGACY_IDENTITIES_ROOT` 常量
- **但 `scripts/install.sh` 完全不用这套**，只 `tmux new-session bash` + send-keys claude
- 后果：所有 seat 的 `HOME=/Users/ywf`，credentials 共享主 HOME，跨 seat 没真隔离

**目标**：install.sh 改用 agent-launcher.sh 启 seat，每个 seat 拿到隔离的 sandbox HOME。

## 调研要求（先 read，再动手）

1. `core/launchers/agent-launcher.sh` 完整读一遍
   - 它的 CLI flags（--headless / --session / --tool / --auth / --dir / --provider 等）
   - 它怎么决定 runtime_dir / sandbox HOME
   - 它需要哪些前置（profile / secrets / project）
2. `core/scripts/agent_admin_session.py` 的 `start_engineer()` / `stop_engineer()`
   - 现有项目怎么启 seat（参考标准用法）
3. `core/skills/clawseat-install/scripts/init_specialist.py`（若存在）
   - 看老 v0.5 安装流程怎么集成 isolation

不要臆测 agent-launcher.sh 的 CLI；先读懂再写。

## 设计

install.sh 现状（要替换的）：

```bash
recreate_session() {
  local name="$1" cwd="${2:-$REPO_ROOT}"
  tmux kill-session -t "=$name" 2>/dev/null || true
  tmux new-session -d -s "$name" -c "$cwd" bash || die ...
}

# Step 6:
recreate_session "$PROJECT-ancestor"
tmux send-keys -t "$PROJECT-ancestor" "$(claude_command "$BRIEF_PATH")" C-m
```

新设计（替换为）：

```bash
launch_seat() {
  local seat="$1" extra_env="${2:-}"
  # 调 agent-launcher.sh，它会处理 sandbox HOME / secrets / runtime_dir
  bash "$REPO_ROOT/core/launchers/agent-launcher.sh" \
    --headless \
    --session "$PROJECT-$seat" \
    --tool claude \
    --auth api \
    --provider minimax \
    --secrets-env "$PROVIDER_ENV" \
    ${extra_env:+--env "$extra_env"} \
    || die ... 
}

# Step 6:
launch_seat ancestor "CLAWSEAT_ANCESTOR_BRIEF=$BRIEF_PATH"

# Step 8:
launch_seat memory  # memory 不需要 BRIEF
```

**注意**：上面的 CLI 是猜测，**必须读 agent-launcher.sh 实际签名后调整**。

## 兼容性约束

1. **生成的 tmux session 名要保持一致**（`smoketest-ancestor` 等），iterm_panes_driver 仍能 attach
2. **claude 进程仍带 `--dangerously-skip-permissions`**（install.sh 假定 bypass 模式）
3. **provider env 仍用 install.sh 生成的 `~/.agents/tasks/<project>/ancestor-provider.env`**（agent-launcher 要能 source 它，或我们传 env vars）
4. **memory seat 的 workspace 是 `~/.agents/workspaces/<project>/memory`**（已通过 WIRE-037 落地）—— agent-launcher 启 memory 时要用这个 dir
5. **不破坏现有 install.sh 其他 Step**（preflight / scan / brief render / iterm grid / 3-Enter flush）

## 实现任务

### Subagent A — 改造 install.sh

1. 读 agent-launcher.sh 弄清 CLI 协议
2. 写 `launch_seat()` 函数封装 agent-launcher 调用
3. Step 5 改：循环调 `launch_seat <seat>`，**不再** recreate_session + send-keys
4. Step 6 删（agent-launcher 已经启了 ancestor + claude）
5. Step 8 改：`launch_seat memory`
6. `claude_command()` 函数若不再需要可删
7. `recreate_session()` 函数若不再需要可删

### Subagent B — 测试

`tests/test_install_isolation.py`（新建）：
- mock agent-launcher.sh，verify install.sh 用对的 flags 调它
- verify 每个 seat 的预期 sandbox runtime_dir
- 验证 install.sh 不再直接 tmux new-session（grep 自身代码确认）

## 验证

```bash
bash -n scripts/install.sh && echo "syntax ok"
pytest tests/test_install_isolation.py -v

# dry-run 应打印 agent-launcher.sh 调用而非 tmux new-session
bash scripts/install.sh --dry-run --project smoketest 2>&1 | grep -E "agent-launcher|tmux new-session"
# 期望: 只有 agent-launcher 调用；没 tmux new-session（除了 install-runner 本身）
```

## 约束 & 边界

- **不改 agent-launcher.sh 本身**（除非发现真 bug，需先报告 planner）
- **不动 install.sh 其他 Step**（1/2/3/4/7/9 保持原样）
- **不改 ancestor-brief.template.md / WIRE-037 的 hook install / SKILL.md**

## 已知坑

1. `agent-launcher.sh` 可能要求 profile 已存在。install.sh 还没创建 dynamic profile（那是 ancestor Phase-A 的事）。可能需要先生成一个 minimal stub profile，或给 agent-launcher 加 `--profile-stub` 路径。读了实际代码后再决定。
2. memory seat 历史用 `machine-memory-claude` 这个 singleton 名，不带 project 前缀。agent-launcher 是不是支持这种命名要确认。
3. `iterm_panes_driver.py` 的 grid_payload 现在 attach 用的是 `tmux attach -t '=<project>-<seat>'`，这套保持不变。

## Deliverable

`DELIVERY-ISOLATION-046.md`：

```
task_id: ISOLATION-046
owner: builder-codex
target: planner

## agent-launcher 调研结论
<它的 CLI 协议 / 它的 isolation 怎么做的 / 它需要哪些前置>

## install.sh 改动
<diff 摘录 + 删了 recreate_session/claude_command 等不再需要的函数>

## Verification
- bash -n / pytest 输出
- dry-run 输出（无 tmux new-session，全是 agent-launcher）
- 真跑一次（在 tmp 项目名下，验证 sandbox HOME 真的隔离了）

## Notes
- agent-launcher 不支持的某些场景如何 workaround
- 已知遗留问题（如有）
```

**不 commit**。
