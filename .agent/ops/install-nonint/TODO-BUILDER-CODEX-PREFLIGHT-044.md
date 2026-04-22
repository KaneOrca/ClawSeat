# TODO — PREFLIGHT-044 (install.sh Step 1 改用 preflight + 补 iTerm2 检查)

```
task_id: PREFLIGHT-044
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: OK (2 subagents: A=preflight 扩展, B=install.sh 改造)
scope: 改 core/preflight.py + 改 scripts/install.sh + 测试
```

## Context

LIVE-043 在 install.sh Step 1 卡死 — 根因是 install.sh 手撸 `brew install tmux`/`brew install --cask iterm2`，**没有任何"已装就跳"的短路**。在阿里云镜像下 brew update 极慢（10-30 min），表现为"卡住"。

但**ClawSeat 仓库本来就有 `core/preflight.py`（859 行）** 实现了完整的 host 检查框架（PreflightItem / status / fix_command）。install.sh 没用它，自己重复造了残废轮子。这是架构 bug。

## 目标

让 install.sh Step 1 **不自己跑 brew install**，改为：
1. 调 `core/preflight.py --project <name> --phase bootstrap`
2. 看到 HARD_BLOCKED → 打印 fix_command + die 退出
3. 看到 PASS / WARNING / RETRYABLE → 进入 Step 2

操作员看到 `brew install tmux` 这种 fix_command 后**手动**跑一次，再重启 install.sh。这是正解的"agent-driven install"——脚本只检测，不强制安装。

---

## Subagent A — `core/preflight.py` 扩展

### A.1 — 新增 `_check_iterm2()`

macOS 下 iTerm2 是 install.sh Step 7/8 必需（iterm_panes_driver.py 用）。preflight 当前不检查。

```python
def _check_iterm2() -> PreflightItem:
    """Check iTerm2.app installed (macOS-only). Skipped on non-macOS."""
    if platform.system() != "Darwin":
        return PreflightItem(
            name="iterm2",
            status=PreflightStatus.PASS,
            message="iTerm2 not required on non-macOS",
        )
    iterm_paths = [
        Path("/Applications/iTerm.app"),
        Path.home() / "Applications" / "iTerm.app",
    ]
    for p in iterm_paths:
        if p.exists():
            return PreflightItem(
                name="iterm2",
                status=PreflightStatus.PASS,
                message=f"iTerm2 at {p}",
            )
    has_brew = shutil.which("brew") is not None
    fix = "brew install --cask iterm2" if has_brew else (
        "Install iTerm2 from https://iterm2.com/ or via brew (install Homebrew first)"
    )
    return PreflightItem(
        name="iterm2",
        status=PreflightStatus.HARD_BLOCKED,
        message="iTerm2.app not found in /Applications or ~/Applications",
        fix_command=fix,
    )
```

### A.2 — 新增 `_check_iterm2_python_module()`

iterm_panes_driver.py 调 `import iterm2`。缺这个 pip 包整个 Step 7 炸。

```python
def _check_iterm2_python_module() -> PreflightItem:
    """Check the iterm2 Python module is importable (needed by iterm_panes_driver)."""
    if platform.system() != "Darwin":
        return PreflightItem(
            name="iterm2_python",
            status=PreflightStatus.PASS,
            message="iterm2 Python module not required on non-macOS",
        )
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import iterm2"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0:
            return PreflightItem(
                name="iterm2_python",
                status=PreflightStatus.PASS,
                message="iterm2 module importable",
            )
    except (subprocess.TimeoutExpired, OSError):
        pass
    return PreflightItem(
        name="iterm2_python",
        status=PreflightStatus.HARD_BLOCKED,
        message="iterm2 Python module not installed (needed by iterm_panes_driver.py)",
        fix_command="pip3 install --user --break-system-packages iterm2",
    )
```

### A.3 — claude binary 升级为 HARD_BLOCKED（在 bootstrap 模式下）

当前 `_check_optional_cli("claude", ...)` 返回 WARNING。bootstrap 时缺 claude 是真致命（install.sh Step 6/8 启 claude）。

加一个新函数（不破坏 _check_optional_cli 现有契约）：

```python
def _check_claude_required() -> PreflightItem:
    """Check claude CLI installed — HARD_BLOCKED for install bootstrap."""
    path = shutil.which("claude")
    if path:
        return PreflightItem(
            name="claude_required",
            status=PreflightStatus.PASS,
            message=f"claude at {path}",
        )
    return PreflightItem(
        name="claude_required",
        status=PreflightStatus.HARD_BLOCKED,
        message="claude CLI not found — install Claude Code from https://claude.ai/code",
        fix_command="# Visit https://claude.ai/code to install Claude Code CLI",
    )
```

### A.4 — `--phase bootstrap` flag 给 `preflight_check()`

bootstrap 时 dynamic_profile 和 session_binding_dir 必然缺（install 流程里它们才被创建）。这两个 RETRYABLE 不该在 bootstrap 出现。

修改 `preflight_check(project: str, phase: str = "runtime") -> PreflightResult`：
- `phase="bootstrap"`：
  - 跳过 `_check_dynamic_profile`、`_check_session_binding_dir`、`_check_skills`（skills 还没装）
  - 加跑 `_check_iterm2`、`_check_iterm2_python_module`、`_check_claude_required`
- `phase="runtime"`（默认）：保持现有行为

CLI 入口（如有 main）添加 `--phase {bootstrap,runtime}` flag。

### A.5 — 测试

`tests/test_preflight.py` 加（或新建）：
- `_check_iterm2`：mock /Applications/iTerm.app 存在 / 不存在
- `_check_iterm2_python_module`：mock subprocess 返回值
- `_check_claude_required`：mock shutil.which
- `preflight_check(project, phase='bootstrap')`：跳过 dynamic_profile / session_binding / skills

---

## Subagent B — `scripts/install.sh` 改 Step 1

### B.1 — 替换 `ensure_host_deps()`

现状（第 41-74 行）整个函数手撸 brew install。**全删**，改为：

```bash
ensure_host_deps() {
  note "Step 1: preflight"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q "%s/core/preflight.py" --project "%s" --phase bootstrap\n' \
      "$PYTHON_BIN" "$REPO_ROOT" "$PROJECT"
    return 0
  fi
  # 真跑 preflight，捕获输出。HARD_BLOCKED → 打印 + die；其他 → 继续
  local pf_out pf_rc
  pf_out="$("$PYTHON_BIN" "$REPO_ROOT/core/preflight.py" --project "$PROJECT" --phase bootstrap 2>&1)"
  pf_rc=$?
  printf '%s\n' "$pf_out"
  if [[ $pf_rc -ne 0 ]]; then
    die 10 PREFLIGHT_FAILED "preflight 检测到 HARD_BLOCKED 项。按上面 fix_command 修复后重跑 install.sh。"
  fi
  echo "OK: preflight"
}
```

### B.2 — preflight.py 的退出码契约

需要 preflight.py 的 `main()` 在有 HARD_BLOCKED 时返回非零（如果还没有就加上）：
- `result.has_hard_blocked == True` → `sys.exit(2)`
- 否则 → `sys.exit(0)`

### B.3 — 验证

```bash
bash -n scripts/install.sh
python3 -m py_compile core/preflight.py

# 真跑 preflight 看你机器上的状态
python3 core/preflight.py --project smoketest --phase bootstrap
echo "preflight rc=$?"
# 期望: 你机器有 tmux/iterm2/claude/python3.11，所有 HARD_BLOCKED 项 PASS，rc=0

# 真跑 install.sh dry-run 看 Step 1 改造后输出
bash scripts/install.sh --dry-run --project smoketest 2>&1 | head -20
# 期望: Step 1 显示 [dry-run] preflight 调用，不再有 brew install
```

---

## 约束

- 不动 install.sh 其他 Step
- 不破坏 preflight 已有 runtime 行为（runtime 模式调用方式不变）
- 不改 `_check_optional_cli`（它服务于 runtime 检查）
- 测试：`pytest tests/test_preflight.py -v` 必须全绿

## Deliverable

`DELIVERY-PREFLIGHT-044.md`：

```
task_id: PREFLIGHT-044
owner: builder-codex
target: planner

## 改动清单
- core/preflight.py (新增 4 个函数 + bootstrap phase, 行数变化)
- scripts/install.sh (替换 ensure_host_deps, 简化为 preflight 调用)
- tests/test_preflight.py (新增/修改, N tests)

## Verification
- bash -n / py_compile / pytest 输出
- 你机器跑 `preflight.py --phase bootstrap`，期待全 PASS（rc=0）
- install.sh dry-run 输出

## Notes
<未解决项>
```

**不 commit**。
