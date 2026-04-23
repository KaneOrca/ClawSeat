# DELIVERY: LAUNCHER-BASH-PANE-RESEED-FIX

## 1. 改动文件清单

- `/Users/ywf/coding/ClawSeat/core/launchers/agent-launcher.sh:71,417,1211,1222,1296`
  - 保持 `#!/usr/bin/env bash`
  - 新增 `uppercase_ascii()`，替换 bash 4+ `${var^^}`
  - `remember_custom_target()` 改为懒创建 preset 目录，避免 `--help/--dry-run` 在受限 HOME 下提前写盘

- `/Users/ywf/coding/ClawSeat/tests/test_launcher_bash_compat.py:14,19,32`
  - 新增 bash 3.2 兼容回归测试

- `/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_window.py:19,411-473`
  - 新增 `SeatNotFoundInWindow`
  - 新增 pane 查找 / reseed 实现
  - `reseed_pane(project, seat_id)` 用 iTerm Python API 发送 `C-c`、`C-b d`、`bash wait-for-seat.sh <project-seat>`

- `/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_commands.py:308-312`
  - 新增 `window_reseed_pane(...)` 命令处理

- `/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_parser.py:50,467-470`
  - 新增 `window reseed-pane <seat> --project <name>` subparser

- `/Users/ywf/coding/ClawSeat/core/scripts/agent_admin.py:1205-1206,1286`
  - 新增 `cmd_window_reseed_pane(...)`
  - 将 reseed-pane 接入 `PARSER_HOOKS`

- `/Users/ywf/coding/ClawSeat/core/scripts/iterm_panes_driver.py:230-236`
  - pane 创建时 best-effort 写入 `user.seat_id`

- `/Users/ywf/coding/ClawSeat/tests/test_iterm_panes_driver.py:56,323-324`
  - fake iTerm session 增加 `async_set_variable(...)`
  - 断言 driver 会写 `user.seat_id`

- `/Users/ywf/coding/ClawSeat/tests/test_agent_admin_window_reseed.py:68-107`
  - 新增 reseed-pane parser / success / not-found / ancestor-reject 回归测试

## 2. 新增测试清单

- `tests/test_launcher_bash_compat.py`
- `tests/test_agent_admin_window_reseed.py`

## 3. 手工验证命令 + 输出

### 3.1 P0: 系统 bash 3.2

命令：

```bash
/bin/bash --version | head -1
```

输出：

```text
GNU bash, version 3.2.57(1)-release (arm64-apple-darwin24)
```

### 3.2 P0: launcher 在 bash 3.2 下 dry-run 正常

命令：

```bash
HOME=$(mktemp -d /tmp/launcher-bash32.XXXXXX) \
  /bin/bash core/launchers/agent-launcher.sh \
  --tool claude \
  --auth oauth_token \
  --session bash32-manual \
  --dir /Users/ywf/coding/ClawSeat \
  --dry-run
```

输出：

```text
Unified launcher dry-run
  tool:     claude
  auth:     oauth_token
  dir:      /Users/ywf/coding/ClawSeat
  session:  bash32-manual
  custom:   no
  headless: 0
```

### 3.3 P1: live iTerm pane reseed

- 未在本 turn 做真实 pane 手工验证
- 原因：`reseed-pane` 会向真实 iTerm pane 注入 `C-c` / `C-b d` / `bash wait-for-seat.sh ...`，会直接影响当前 seat
- 本次用单测覆盖命令序列与错误路径，见 `tests/test_agent_admin_window_reseed.py`

## 4. pytest baseline 对比

P0:

- `pytest tests/test_launcher_bash_compat.py tests/test_launchers.py tests/test_launcher_codex_xcode_fallback.py -q`
  - `29 passed in 0.86s`

P1:

- `pytest tests/test_agent_admin_window_reseed.py tests/test_window_open_grid.py tests/test_iterm_panes_driver.py tests/test_batch_start_engineer.py -q`
  - `63 passed in 0.24s`

全量：

- `pytest tests/ -q`
  - 当前结果：`8 failed, 1812 passed, 11 skipped, 2 xfailed in 84.60s`
  - 失败列表：
    - `tests/test_modal_detector.py::test_live_tmux_modal_detected`
    - `tests/test_send_notify_simplified.py::test_sent_log_format_on_success`
    - `tests/test_send_notify_simplified.py::test_emoji_message`
    - `tests/test_send_notify_simplified.py::test_chinese_message`
    - `tests/test_send_notify_simplified.py::test_newline_message`
    - `tests/test_send_notify_simplified.py::test_long_message_1kb`
    - `tests/test_send_notify_simplified.py::test_concurrent_sends_different_sessions`
    - `tests/test_send_notify_simplified.py::test_project_flag_routing`
  - 这些仍是当前机器的 live tmux/send-notify 依赖失败，不是本次 launcher bash / pane reseed diff 引入的新回归

## 5. 硬约束检查清单

- shebang 保持 `#!/usr/bin/env bash`：`PASS`
- launcher 内 bash 4+ case-conversion 语法已清理，并有 grep+`/bin/bash` 回归测试：`PASS`
- 未用 `tmux send-keys` 绕过 pane reseed：`PASS`
  - reseed 通过 iTerm Python API `async_send_text(...)` 完成
- ancestor pane 明确拒绝 reseed：`PASS`
- `SeatNotFoundInWindow` 错误路径已覆盖：`PASS`
- reseed 幂等性：`PASS`
  - 序列固定为 `C-c` → `C-b d` → `bash wait-for-seat.sh ...`，重复执行会重启同一 wait-for-seat，不依赖旧 pane 状态
- 未 commit / 未 push：`PASS`
