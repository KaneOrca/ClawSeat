# DELIVERY: ENV-SCAN-ARK-FIX

## 变更摘要

### `/Users/ywf/coding/ClawSeat/scripts/env_scan.py`

- 新增 `claude_ark_file = legacy_secrets_root / "claude" / "ark.env"`
- 新增 `claude_ark_file_has_url`
- 新增 `claude_ark_ready`
  - 文件路径：要求 `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL`
  - 环境变量路径：要求 `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL` 且 URL 含 `volces.com`
- 新增 ark `auth_methods` register：
  - `tool="claude"`
  - `auth_mode="api"`
  - `provider="ark"`
- 在 `providers` summary 中新增：
  - `"ark": claude_ark_ready`

### `/Users/ywf/coding/ClawSeat/tests/test_env_scan.py`

- 在已有 `test_scan_requires_provider_url_in_secret_file(...)` 参数化用例里补 ark 对称 case
- 新增 `test_scan_accepts_claude_ark_env_base_url(...)`
- 新增 `test_scan_rejects_claude_ark_env_without_volces_domain(...)`

### `/Users/ywf/coding/ClawSeat/tests/test_provider_validation.py`

- 在 `test_env_scan_emits_only_supported_runtime_combos(...)` fixture 中补 `~/.agent-runtime/secrets/claude/ark.env`
- 期望运行时组合中加入 `("claude", "api", "ark")`

## 新增测试清单

新增自动化测试项：`3`

覆盖场景：`4`

1. file-only-key -> `providers.ark == False`
2. file key+url -> `providers.ark == True`
3. env `ANTHROPIC_AUTH_TOKEN` + volces URL -> `providers.ark == True`
4. env `ANTHROPIC_AUTH_TOKEN` + 非 volces URL -> `providers.ark == False`

相关位置：

- `/Users/ywf/coding/ClawSeat/tests/test_env_scan.py:81`
- `/Users/ywf/coding/ClawSeat/tests/test_env_scan.py:173`
- `/Users/ywf/coding/ClawSeat/tests/test_env_scan.py:186`

## 测试结果

### 1. ark 相关回归

命令：

```bash
python3.12 -m pytest tests/test_env_scan.py tests/test_provider_validation.py -q
```

结果：

```text
20 passed in 1.41s
```

### 2. 纯 env_scan 文件

命令：

```bash
python3.12 -m pytest tests/test_env_scan.py -q
```

结果：

```text
8 passed in 0.03s
```

### 3. TODO 指定的 `-k ark`

命令：

```bash
python3.12 -m pytest tests/ -q -k ark
```

结果：

```text
1 failed, 354 passed, 1479 deselected, 2 xfailed in 17.82s
```

说明：

- 唯一失败是既有 live tmux 环境测试：
  - `tests/test_modal_detector.py::test_live_tmux_modal_detected`
- 失败原因为当前机器 `tmux` 连接权限：
  - `error connecting to /private/tmp/tmux-501/default (Operation not permitted)`
- 不是本次 ark env_scan 变更引入的回归

### 4. TODO 指定的 env_scan 过滤

命令：

```bash
python3.12 -m pytest tests/test_provider_validation.py tests/ -q -k env_scan
```

结果：

```text
10 passed, 1826 deselected in 1.46s
```

## 手工验证结果

命令：

```bash
python3 - <<'PY'
import json
import os
import subprocess
import tempfile
from pathlib import Path

repo = Path('/Users/ywf/coding/ClawSeat')
keys_to_clear = (
    'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_API_BASE',
    'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
    'CLAUDE_CODE_OAUTH_TOKEN', 'GEMINI_API_KEY',
)

def run(fake_home: Path, *, env_overrides=None):
    env = dict(os.environ)
    env['CLAWSEAT_SCAN_HOME'] = str(fake_home)
    for key in keys_to_clear:
        env.pop(key, None)
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(['python3', 'scripts/env_scan.py'], cwd=repo, env=env, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    auth_method = any(
        item['tool'] == 'claude' and item['auth_mode'] == 'api' and item['provider'] == 'ark'
        for item in data['auth_methods']
    )
    return bool(data['providers']['ark']), auth_method

home1 = Path(tempfile.mkdtemp(prefix='env-scan-ark-file-key-'))
secret1 = home1 / '.agent-runtime' / 'secrets' / 'claude' / 'ark.env'
secret1.parent.mkdir(parents=True, exist_ok=True)
secret1.write_text('ANTHROPIC_AUTH_TOKEN=sk-ark-only\\n', encoding='utf-8')
print('file_only_key', *run(home1))

home2 = Path(tempfile.mkdtemp(prefix='env-scan-ark-file-url-'))
secret2 = home2 / '.agent-runtime' / 'secrets' / 'claude' / 'ark.env'
secret2.parent.mkdir(parents=True, exist_ok=True)
secret2.write_text('ANTHROPIC_AUTH_TOKEN=sk-ark-ready\\nANTHROPIC_BASE_URL=https://ark.cn-beijing.volces.com/api/coding\\n', encoding='utf-8')
print('file_key_url', *run(home2))

home3 = Path(tempfile.mkdtemp(prefix='env-scan-ark-env-url-'))
home3.mkdir(exist_ok=True)
print('env_key_url', *run(home3, env_overrides={
    'ANTHROPIC_AUTH_TOKEN': 'sk-ark-env',
    'ANTHROPIC_BASE_URL': 'https://ark.cn-beijing.volces.com/api/coding',
}))

home4 = Path(tempfile.mkdtemp(prefix='env-scan-ark-env-bad-'))
home4.mkdir(exist_ok=True)
print('env_key_non_volces', *run(home4, env_overrides={
    'ANTHROPIC_AUTH_TOKEN': 'sk-ark-env',
    'ANTHROPIC_BASE_URL': 'https://api.anthropic.com',
}))
PY
```

输出：

```text
file_only_key False False
file_key_url True True
env_key_url True True
env_key_non_volces False False
```

解释：

- `file_only_key False False`
  - 只有 `ANTHROPIC_AUTH_TOKEN` 时，`providers.ark` 不 ready，且不会注册 ark auth method
- `file_key_url True True`
  - 文件内 key+url 时，`providers.ark` ready，且 auth method 正确注册
- `env_key_url True True`
  - 纯环境变量路径在 URL 含 `volces.com` 时仍可用
- `env_key_non_volces False False`
  - 纯环境变量路径在 URL 不含 `volces.com` 时不会误判成 ark

## 全量 pytest baseline 对照

之前 baseline：

- `1812 passed / 8 failed`

本次之后：

- `1815 passed / 8 failed`

命令：

```bash
python3.12 -m pytest tests/ -q
```

尾部摘要：

```text
FAILED tests/test_send_notify_simplified.py::test_newline_message - subproces...
FAILED tests/test_send_notify_simplified.py::test_long_message_1kb - subproce...
FAILED tests/test_send_notify_simplified.py::test_concurrent_sends_different_sessions
FAILED tests/test_send_notify_simplified.py::test_project_flag_routing - subp...
8 failed, 1815 passed, 11 skipped, 2 xfailed in 91.20s (0:01:31)
```

剩余 8 个失败仍是既有 live tmux / send-notify 路径：

- `tests/test_modal_detector.py::test_live_tmux_modal_detected`
- `tests/test_send_notify_simplified.py::test_sent_log_format_on_success`
- `tests/test_send_notify_simplified.py::test_emoji_message`
- `tests/test_send_notify_simplified.py::test_chinese_message`
- `tests/test_send_notify_simplified.py::test_newline_message`
- `tests/test_send_notify_simplified.py::test_long_message_1kb`
- `tests/test_send_notify_simplified.py::test_concurrent_sends_different_sessions`
- `tests/test_send_notify_simplified.py::test_project_flag_routing`

## 已知风险

- 当前 env 路径对 ark 的 domain 判定使用 `volces.com` substring
- 这能覆盖当前 canonical URL：
  - `https://ark.cn-beijing.volces.com/api/coding`
- 如果未来 ark 出现多 region / 多 endpoint，最好改为读取 provider 定义表，而不是继续在 `env_scan.py` 写死 domain substring
- 本次按 TODO 要求，当前阶段只补 `volces.com` 一条，不扩更多 region 规则

## 约束检查

- 未改 `install.sh`：`PASS`
- 未改 `core/launchers/agent-launcher.sh`：`PASS`
- 未扩其他 provider：`PASS`
- 未 commit：`PASS`
- 未 push：`PASS`
