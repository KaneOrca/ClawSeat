task_id: SCAN-034
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: Extended `scan_environment.py` to discover OpenClaw home dynamically and emit `agents`, then added a bootstrap script that hydrates `~/.clawseat/machine.toml` tenants from `machine/openclaw.json` using the same discovery chain.

## Subagent A — scan_openclaw() 扩展
- `core/skills/memory-oracle/scripts/scan_environment.py`
  - `scan_openclaw()` 现在走 `OPENCLAW_HOME` -> `openclaw config file` -> `~/.openclaw`
  - 新增 `agents` 字段，扫描 `workspace-*` 目录和带 `WORKSPACE_CONTRACT.toml` 的直名目录，输出 `name / workspace / has_contract`
- `tests/test_scan_openclaw.py`
  - 覆盖 env override
  - 覆盖 CLI 缺失 fallback
  - 覆盖 CLI 发现 home
  - 覆盖 workspace agent 列表
  - 覆盖空目录 `agents=[]`

## Subagent B — machine_config 同步 + bootstrap
- `core/lib/machine_config.py`
  - `_openclaw_workspace_root()` 改为复用共享 helper
  - 保留 `CLAWSEAT_REAL_HOME` 测试隔离：设置该变量时禁用主机 `openclaw` CLI 影响
  - `_discover_tenants()` 现在兼容 `workspace-<name>` 和带 contract 的直名目录
- `core/lib/openclaw_home.py`
  - 新增共享 OpenClaw home 发现 helper，供 scanner 与 `machine_config` 共用
- `core/scripts/bootstrap_machine_tenants.py`
  - 从 `machine/openclaw.json.agents` 幂等追加 tenants 到 `~/.clawseat/machine.toml`
  - 已有 tenant 不覆盖
  - 不存在的 workspace 跳过
- `tests/test_bootstrap_machine_tenants.py`
  - 覆盖新增 tenant
  - 覆盖已有 tenant 不覆盖
  - 覆盖缺失 workspace skip
  - 补了一条 `OPENCLAW_HOME` auto-discovery 断言

## Verification
```text
$ python3 -m py_compile core/lib/openclaw_home.py core/lib/machine_config.py core/scripts/bootstrap_machine_tenants.py core/skills/memory-oracle/scripts/scan_environment.py tests/test_scan_openclaw.py tests/test_bootstrap_machine_tenants.py
[exit 0]

$ pytest tests/test_scan_openclaw.py tests/test_bootstrap_machine_tenants.py -v
============================= test session starts ==============================
collected 9 items

tests/test_scan_openclaw.py::test_scan_openclaw_prefers_env_override PASSED
tests/test_scan_openclaw.py::test_scan_openclaw_cli_missing_falls_back_to_home PASSED
tests/test_scan_openclaw.py::test_scan_openclaw_discovers_home_from_cli PASSED
tests/test_scan_openclaw.py::test_scan_openclaw_lists_workspace_agents PASSED
tests/test_scan_openclaw.py::test_scan_openclaw_empty_agents_list PASSED
tests/test_bootstrap_machine_tenants.py::test_bootstrap_machine_tenants_adds_new_tenants PASSED
tests/test_bootstrap_machine_tenants.py::test_bootstrap_machine_tenants_does_not_overwrite_existing PASSED
tests/test_bootstrap_machine_tenants.py::test_bootstrap_machine_tenants_skips_missing_workspace PASSED
tests/test_bootstrap_machine_tenants.py::test_load_machine_auto_discovery_uses_openclaw_home_env PASSED

============================== 9 passed in 0.04s ===============================

$ pytest tests/test_machine_config.py tests/test_memory_oracle.py::TestScanOpenclaw::test_happy_path_returns_schema -v
============================= test session starts ==============================
collected 17 items
...
============================== 17 passed in 1.00s ==============================

$ python3 core/skills/memory-oracle/scripts/scan_environment.py --only openclaw --output /tmp/scan-test/
scanning openclaw… ✓

scan complete: 1/1 scanners succeeded
index: /private/tmp/scan-test/index.json
machine/ files: ['openclaw.json']

$ python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('/tmp/scan-test/machine/openclaw.json').read_text())
print(data['home'])
print(len(data.get('agents', [])))
PY
/Users/ywf/.openclaw
13
```

## Notes
- 我把 OpenClaw home 发现链抽成了 `core/lib/openclaw_home.py`，避免 scanner 和 `machine_config` 再次各写一套。
- `bootstrap_machine_tenants.py` 使用现有 `write_machine()`，没有新增 `save_machine()` 别名。
- 未改 `memory-oracle/SKILL.md`，未改 `scripts/apply-koder-overlay.sh`。
- 当前改动全部未提交，留给 planner 审。
