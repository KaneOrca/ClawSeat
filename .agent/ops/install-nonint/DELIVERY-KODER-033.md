task_id: KODER-033
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: Added an interactive `scripts/apply-koder-overlay.sh` orchestration script plus subprocess-based pytest coverage for menu selection, bind/init wiring, and dry-run no-op behavior.

## 改动清单
- `scripts/apply-koder-overlay.sh` (新建, 274 行)
- `tests/test_apply_koder_overlay.py` (新建, 125 行)

## Verification
```text
$ bash -n scripts/apply-koder-overlay.sh && echo "syntax ok"
syntax ok

$ bash scripts/apply-koder-overlay.sh --dry-run install
==> Step 1: list OpenClaw tenants
可选的 OpenClaw agent (作为 koder 身份)：
  [1] cartooner
  [2] cartooner-web
  [3] cc
  [4] claude
  [5] codex
  [6] donk
  [7] gemini
  [8] koder
  [9] legal
  [10] mor
  [11] scout
  [12] warden
  [13] yu
[dry-run] auto-selecting [1] cartooner
将把 'cartooner' 的身份完全覆盖为 koder。此操作会改写 6 个核心文件（IDENTITY/SOUL/TOOLS/MEMORY/AGENTS/CONTRACT）。
[dry-run] destructive confirmation skipped
==> Step 4: init_koder
[dry-run] python3 /Users/ywf/ClawSeat/core/skills/clawseat-install/scripts/init_koder.py --workspace /Users/ywf/.openclaw/workspace-cartooner --project install --profile /Users/ywf/.agents/profiles/install-profile-dynamic.toml --on-conflict backup
==> Step 5: project koder-bind
[dry-run] python3 -c import\ sys\;\ from\ pathlib\ import\ Path\;\ repo\ =\ Path\(sys.argv\[1\]\)\;\ sys.path\[:0\]\ =\ \[str\(repo\)\,\ str\(repo\ /\ \"core\"\ /\ \"lib\"\)\]\;\ from\ core.scripts.agent_admin_layered\ import\ do_koder_bind\;\ do_koder_bind\(sys.argv\[2\]\,\ sys.argv\[3\]\) /Users/ywf/ClawSeat install cartooner
OK: 'cartooner' 已改造为 koder，绑定到项目 'install'

$ python3 -c "from core.lib.machine_config import list_openclaw_tenants; print(list_openclaw_tenants())"
[OpenClawTenant(name='cartooner', workspace=PosixPath('/Users/ywf/.openclaw/workspace-cartooner'), description=''), ...]

$ pytest tests/test_apply_koder_overlay.py -v
============================= test session starts ==============================
collected 3 items

tests/test_apply_koder_overlay.py::test_dry_run_lists_menu_items PASSED
tests/test_apply_koder_overlay.py::test_pick_first_invokes_init_and_bind PASSED
tests/test_apply_koder_overlay.py::test_dry_run_does_not_execute_runners PASSED

============================== 3 passed in 0.26s ===============================
```

## 已知限制
- `--dry-run` 为避免阻塞会自动选择列表中的第一个 tenant；真实执行仍要求人工选择并确认 destructive 覆盖。
- 脚本本身不改 `core/lib/machine_config.py`；tenant 枚举直接复用现有 `list_openclaw_tenants()` 返回的 registry 结果。
- 为了让 subprocess 单测可控，脚本暴露了 `INIT_KODER_RUNNER` / `KODER_BIND_RUNNER` / `CONFIGURE_KODER_FEISHU_RUNNER` 三个测试接缝；默认实际运行仍走仓库内 Python 实现。
- 当前改动全部未提交，留给 planner 审。
