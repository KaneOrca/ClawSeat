task_id: PREFLIGHT-044
owner: builder-codex
target: planner

## 改动清单

- `core/preflight.py`
  - 新增 `_check_iterm2()`、`_check_iterm2_python_module()`、`_check_claude_required()`
  - `preflight_check(project, phase="runtime")` 新增 `phase` 参数
  - `phase="bootstrap"` 时跳过 `dynamic_profile` / `session_binding_dir` / `skills`，新增 iTerm2 / iterm2 Python / required claude 检查
  - CLI 新增 `--phase {bootstrap,runtime}` 与 `--project`
  - `main()` 退出码更新为：`has_hard_blocked -> 2`，否则 `0`
- `scripts/install.sh`
  - Step 1 `ensure_host_deps()` 改为统一调用 `core/preflight.py --project <name> --phase bootstrap`
  - 删除脚本内手撸 brew/cask 安装逻辑
  - dry-run 仅打印 preflight 调用
  - preflight 非零时打印完整输出并 `die 10 PREFLIGHT_FAILED`
- `tests/test_preflight.py`
  - 新增 4 个测试，锁定 runtime/bootstrap 分流、invalid phase、以及 HARD_BLOCKED 退出码

## Verification

- `bash -n /Users/ywf/ClawSeat/scripts/install.sh`
  - 通过
- `python3 -m py_compile /Users/ywf/ClawSeat/core/preflight.py`
  - 通过
- `cd /Users/ywf/ClawSeat && pytest tests/test_preflight.py -v`
  - `4 passed`
- `cd /Users/ywf/ClawSeat && pytest tests/test_preflight_gstack_severity.py tests/test_preflight_profile_aware.py -q`
  - `14 passed`
- `python3 /Users/ywf/ClawSeat/core/preflight.py --project smoketest --phase bootstrap`
  - 本机结果：`preflight_check: PASS [smoketest]`
  - 关键项：`tmux` / `tmux_server` / `iterm2` / `iterm2_python` / `claude_required` 均为 PASS
  - 退出码：`preflight_rc=0`
- `bash /Users/ywf/ClawSeat/scripts/install.sh --dry-run --project preflight-044 | sed -n '1,12p'`
  - Step 1 现在输出：
    - `==> Step 1: preflight`
    - `[dry-run] python3 /Users/ywf/ClawSeat/core/preflight.py --project preflight-044 --phase bootstrap`
  - 不再出现 `brew install tmux` / `brew install --cask iterm2`

## Notes

- 按 TODO 要求，未改动 `install.sh` 其他 Step。
- `runtime` 模式的原有 optional CLI / gstack / profile-aware skill 检查仍保留。
- 未 commit。
