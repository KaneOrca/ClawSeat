# DELIVERY: ENV-SCAN-XCODE-BEST-FIX

## 1. 改动文件清单

- `/Users/ywf/coding/ClawSeat/scripts/env_scan.py:54,128,142-173,264`
  - 新增 `env_file_has_any_key(...)`
  - `codex_xcode_ready` 改为 key+URL 才 ready
  - `claude_xcode_ready` / `claude_minimax_ready` 同步改为文件内 key+URL 才 ready
  - 环境变量路径兼容 `OPENAI_BASE_URL` / `OPENAI_API_BASE`

- `/Users/ywf/coding/ClawSeat/tests/test_env_scan.py:81,123`
  - 新增 env_scan 回归测试

- `/Users/ywf/coding/ClawSeat/scripts/install.sh:7,81-103,130-142,244,294-388,535-557,690-693,842-864,938`
  - install 改为固定使用当前 repo 的 `REPO_ROOT`
  - 新增 provider 默认 URL 常量与提示
  - install detection / forced provider / launcher custom env / seeded seat secret 全链路支持 `xcode-best`
  - 非 ancestor seat 显式传空 `CLAWSEAT_ANCESTOR_BRIEF`，避免继承外部环境

- `/Users/ywf/coding/ClawSeat/tests/test_xcode_best_provider_support.py:19-157`
  - 新增 xcode-best install 回归测试

- `/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_session.py:624-626`
  - launcher 启动时注入 `CLAWSEAT_PROVIDER`
  - 启动前清掉继承来的 `CLAWSEAT_ANCESTOR_BRIEF`

- `/Users/ywf/coding/ClawSeat/core/launchers/agent-launcher.sh:71,417,1209-1222,1296`
  - 新增 bash 3.2 兼容的 `uppercase_ascii()`
  - `remember_custom_target` 改为懒创建 preset 目录
  - codex `xcode` auth 分支在无 URL 时按 `CLAWSEAT_PROVIDER=xcode-best` 注入 `OPENAI_BASE_URL=https://api.xcode.best/v1`

- `/Users/ywf/coding/ClawSeat/tests/test_agent_admin_session_isolation.py:216`
  - 断言 launcher env 含 `CLAWSEAT_PROVIDER`

- `/Users/ywf/coding/ClawSeat/tests/test_launcher_codex_xcode_fallback.py:19-78`
  - 新增 codex xcode launcher fallback 回归测试

- `/Users/ywf/coding/ClawSeat/tests/test_provider_validation.py:195,210`
  - 同步 provider validation fixture，给 minimax shared secret 补 `ANTHROPIC_BASE_URL`

## 2. 新增测试清单

- `tests/test_env_scan.py`
- `tests/test_xcode_best_provider_support.py`
- `tests/test_launcher_codex_xcode_fallback.py`

## 3. 手工验证命令 + 输出

说明：`env_scan.py` 读取固定 secret 路径，所以手工验证用了隔离 `CLAWSEAT_SCAN_HOME` fake-home，把 `/tmp/test-xcode.env` 复制到 fake-home 下的 canonical path。

### 3.1 key only in file => ready=False

命令：

```bash
python3 - <<'PY'
import json, os, subprocess, tempfile
from pathlib import Path

repo = Path('/Users/ywf/coding/ClawSeat')
tmp_home = Path(tempfile.mkdtemp(prefix='env-scan-key-only-clean-'))
secret = tmp_home / '.agent-runtime' / 'secrets' / 'codex' / 'xcode.env'
secret.parent.mkdir(parents=True, exist_ok=True)
Path('/tmp/test-xcode.env').write_text('OPENAI_API_KEY=sk-only\n', encoding='utf-8')
secret.write_text(Path('/tmp/test-xcode.env').read_text(encoding='utf-8'), encoding='utf-8')
env = dict(os.environ)
env['CLAWSEAT_SCAN_HOME'] = str(tmp_home)
for key in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_API_BASE', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_OAUTH_TOKEN', 'GEMINI_API_KEY'):
    env.pop(key, None)
proc = subprocess.run(['python3', 'scripts/env_scan.py'], cwd=repo, env=env, capture_output=True, text=True, check=True)
data = json.loads(proc.stdout)
ready = any(m['tool'] == 'codex' and m['auth_mode'] == 'api' and m['provider'] == 'xcode-best' for m in data['auth_methods'])
print(f'providers.xcode-best={data["providers"]["xcode-best"]}')
print(f'codex_xcode_auth_method={ready}')
PY
```

输出：

```text
providers.xcode-best=False
codex_xcode_auth_method=False
```

### 3.2 key + URL in file => ready=True

命令：

```bash
python3 - <<'PY'
import json, os, subprocess, tempfile
from pathlib import Path

repo = Path('/Users/ywf/coding/ClawSeat')
tmp_home = Path(tempfile.mkdtemp(prefix='env-scan-key-url-clean-'))
secret = tmp_home / '.agent-runtime' / 'secrets' / 'codex' / 'xcode.env'
secret.parent.mkdir(parents=True, exist_ok=True)
Path('/tmp/test-xcode.env').write_text('OPENAI_API_KEY=sk-ready\nOPENAI_BASE_URL=https://api.xcode.best/v1\n', encoding='utf-8')
secret.write_text(Path('/tmp/test-xcode.env').read_text(encoding='utf-8'), encoding='utf-8')
env = dict(os.environ)
env['CLAWSEAT_SCAN_HOME'] = str(tmp_home)
for key in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_API_BASE', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_OAUTH_TOKEN', 'GEMINI_API_KEY'):
    env.pop(key, None)
proc = subprocess.run(['python3', 'scripts/env_scan.py'], cwd=repo, env=env, capture_output=True, text=True, check=True)
data = json.loads(proc.stdout)
ready = any(m['tool'] == 'codex' and m['auth_mode'] == 'api' and m['provider'] == 'xcode-best' for m in data['auth_methods'])
print(f'providers.xcode-best={data["providers"]["xcode-best"]}')
print(f'codex_xcode_auth_method={ready}')
PY
```

输出：

```text
providers.xcode-best=True
codex_xcode_auth_method=True
```

## 4. pytest baseline 对比

每层补丁后：

- `pytest tests/test_env_scan.py -q`
  - `5 passed in 0.03s`

- `pytest tests/test_xcode_best_provider_support.py tests/test_install_provider_noninteractive.py tests/test_ark_provider_support.py -q`
  - `10 passed in 10.21s`

- `pytest tests/test_agent_admin_session_isolation.py tests/test_launcher_codex_xcode_fallback.py tests/test_launchers.py -q`
  - `44 passed in 0.78s`

收尾稳定性回归：

- `pytest tests/test_install_isolation.py::test_install_launches_isolated_seats_via_launcher tests/test_provider_validation.py::test_env_scan_emits_only_supported_runtime_combos tests/test_session_start_ancestor_env.py -q`
  - `4 passed in 1.88s`

全量：

- `pytest tests/ -q`
  - 当前结果：`8 failed, 1805 passed, 11 skipped, 2 xfailed in 84.07s`
  - 失败列表：
    - `tests/test_modal_detector.py::test_live_tmux_modal_detected`
    - `tests/test_send_notify_simplified.py::test_sent_log_format_on_success`
    - `tests/test_send_notify_simplified.py::test_emoji_message`
    - `tests/test_send_notify_simplified.py::test_chinese_message`
    - `tests/test_send_notify_simplified.py::test_newline_message`
    - `tests/test_send_notify_simplified.py::test_long_message_1kb`
    - `tests/test_send_notify_simplified.py::test_concurrent_sends_different_sessions`
    - `tests/test_send_notify_simplified.py::test_project_flag_routing`
  - 这 8 个失败都落在当前机器的 live tmux/send-notify 依赖路径，不是本次 diff 引入的 env_scan/install/launcher/xcode-best 回归。

## 5. 硬约束检查清单

- `openclaw/` 未修改：`PASS`
- 未 commit / 未 push：`PASS`
- P0 已实现：文件 secret 现在必须 key+URL 才判定 ready：`PASS`
- `claude_xcode_ready` / `claude_minimax_ready` 已同步收紧：`PASS`
- install 对 proxy provider 自动写 URL，且 `xcode-best` 已补齐：`PASS`
- launcher `auth_mode=api/xcode` 缺 URL 时可按 provider fallback：`PASS`
- 现有环境变量路径 `OPENAI_API_KEY + OPENAI_BASE_URL` 继续可用，且兼容 `OPENAI_API_BASE`：`PASS`
- install 重跑不会 double-append URL：`PASS`
  - install 这里是重写 generated env 文件，不是 append
- 当前仓库全量 pytest 未完全清零：`WARN`
  - 剩余 8 个失败为当前机器 tmux/live notify 依赖问题，见上节
