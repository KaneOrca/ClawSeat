task_id: HOMEFIX-045
owner: builder-codex
target: planner

## 改动清单

- `core/preflight.py`
  - 修复 `_check_iterm2_python_module()` 的 subprocess 环境继承问题
  - 子进程执行 `import iterm2` 时显式传入 `env`
  - 将 `env["HOME"]` 重设为 `real_user_home()`，避免 sandbox `HOME` 把 Python user-site 指到错误目录
- `tests/test_preflight.py`
  - 新增 `test_iterm2_python_module_uses_real_home_in_subprocess_env`
  - 用 sandbox `HOME` + monkeypatch `real_user_home()` 断言 subprocess 实际拿到真实用户 `HOME`

## Root Cause

- 预检里用 `subprocess.run([sys.executable, "-c", "import iterm2"])` 时继承了当前 agent/sandbox 的 `HOME`
- 该 `HOME` 指向 `.agent-runtime/.../home`
- Python user-site 因此偏到 sandbox 目录，导致已安装在真实用户目录下的 `iterm2` 包被误判为缺失

## Verification

- `python3 -m py_compile /Users/ywf/ClawSeat/core/preflight.py`
  - 通过
- `cd /Users/ywf/ClawSeat && pytest tests/test_preflight.py -v`
  - `5 passed`
- `cd /Users/ywf/ClawSeat && pytest tests/test_preflight_gstack_severity.py tests/test_preflight_profile_aware.py -q`
  - `14 passed`

## UserSummary

- `_check_iterm2_python_module()` 现在会用真实用户 `HOME` 跑 `import iterm2`，不会再因为 sandbox HOME 把已安装的 `iterm2` 误报成缺失。

## Notes

- 未 commit。
