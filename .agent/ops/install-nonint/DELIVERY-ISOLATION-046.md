task_id: ISOLATION-046
owner: builder-codex
target: planner

## agent-launcher 调研结论

- 实际 CLI 入口是 `core/launchers/agent-launcher.sh`，可用参数是：
  - `--tool`
  - `--auth`
  - `--dir`
  - `--session`
  - `--custom-env-file`
  - `--headless`
  - `--dry-run`
- 没有 TODO 设计草图里猜测的 `--provider` / `--secrets-env` / `--env`。
- isolation 发生在 launcher 内部：
  - Claude `oauth_token` -> `~/.agent-runtime/identities/claude/oauth_token/oauth_token-<session>/home`
  - Claude API / custom -> `~/.agent-runtime/identities/claude/api/<auth>-<session>/home`
- launcher 自己负责 `tmux new-session` 和 `claude --dangerously-skip-permissions`。
- `--custom-env-file` 是 one-shot：launcher 读完后会删除该文件，所以 install 侧必须为每次 seat launch 单独生成一份。
- ancestor brief 不需要 launcher 新增参数。只要在调用 launcher 的父进程环境里导出 `CLAWSEAT_ANCESTOR_BRIEF`，tmux session 会继承该环境。

## install.sh 改动

- 改动文件：`/Users/ywf/ClawSeat/scripts/install.sh`
- 删除了 seat startup 的老路径：
  - `recreate_session()`
  - `claude_command()`
  - `tmux new-session ... bash` + `tmux send-keys ... exec claude`
- 新增 `launch_seat()` 适配层，统一走：

```bash
env CLAWSEAT_ROOT=... [CLAWSEAT_ANCESTOR_BRIEF=...] \
  bash core/launchers/agent-launcher.sh \
    --headless \
    --tool claude \
    --auth <mapped-auth> \
    --dir <seat-workdir> \
    --session <stable-session-name> \
    [--custom-env-file <one-shot-env>]
```

- session 名保持不变：
  - `${PROJECT}-ancestor`
  - `${PROJECT}-planner`
  - `${PROJECT}-builder`
  - `${PROJECT}-reviewer`
  - `${PROJECT}-qa`
  - `${PROJECT}-designer`
  - `machine-memory-claude`
- workdir 规则：
  - 项目 seats -> repo root
  - memory -> `~/.agents/workspaces/<project>/memory`
- 为保持 install 生成的 `ancestor-provider.env` 仍是事实来源，做了 auth 映射：
  - `minimax` / `custom_api` / `anthropic_console` -> launcher `--auth custom`
  - `oauth_token` -> launcher `--auth oauth_token`
  - `oauth` -> launcher `--auth oauth`
- 上面三个 API 模式之所以统一映射到 `custom`：
  - launcher 没有 `--env` / `--secrets-env`
  - install 仍要继续使用自己写出的 `~/.agents/tasks/<project>/ancestor-provider.env`
  - 所以 install 侧把 provider env 转成每-seat 一次性的 `LAUNCHER_CUSTOM_*` env file，再交给 launcher
- 幂等性保持：
  - launch 前仍先 `tmux kill-session -t "=$session"` 清掉旧 session
  - 3-Enter flush 保留不变

## Verification

- syntax:

```text
bash -n /Users/ywf/ClawSeat/scripts/install.sh
syntax ok
```

- pytest:

```text
pytest /Users/ywf/ClawSeat/tests/test_install_isolation.py -q
3 passed in 4.93s
```

- dry-run grep（只出现 launcher，不出现 `tmux new-session`）：

```text
HOME=/tmp/clawseat-isolation-dryrun bash /Users/ywf/ClawSeat/scripts/install.sh --dry-run --project smoketest \
  | grep -E "agent-launcher|tmux new-session"

==> Step 5: launch install seats via agent-launcher
[dry-run] ... core/launchers/agent-launcher.sh --headless --tool claude --auth custom --session smoketest-ancestor ...
[dry-run] ... core/launchers/agent-launcher.sh --headless --tool claude --auth custom --session smoketest-planner ...
...
[dry-run] ... core/launchers/agent-launcher.sh --headless --tool claude --auth custom --session machine-memory-claude ...
```

- 真跑一次：
  - 通过 `tests/test_install_isolation.py` 的 fake-root non-dry-run smoke 执行真实 `install.sh`
  - stub 了 preflight / env scan / memory hook / iTerm / tmux / launcher
  - 验证了 7 个 seat 实际走 launcher，且 sandbox runtime_home 为：
    - `<tmp>/home/.agent-runtime/identities/claude/api/custom-smoketest-ancestor/home`
    - ...
    - `<tmp>/home/.agent-runtime/identities/claude/api/custom-machine-memory-claude/home`
  - 同时验证 ancestor 拿到了 `CLAWSEAT_ANCESTOR_BRIEF`，其他 seat 没拿到

## Notes

- 这次没有改 `agent-launcher.sh` 本体。
- 当前实现遵循 TODO 的 post-046 方向：install 阶段所有可见 seat session 都改由 launcher 起，不再由 install.sh 直接 `tmux new-session`。
- 这与现有 ancestor brief 里“后续再逐个拉起 seat”的表述存在语义张力；本次没有改 brief / skill 文案，只在这里显式记录，留给后续 docs clarity / planner 决策收口。
- 全部改动保持未提交。
