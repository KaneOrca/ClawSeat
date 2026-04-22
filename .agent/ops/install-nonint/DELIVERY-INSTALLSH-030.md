task_id: INSTALLSH-030
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: Added a v0.7 `scripts/install.sh`, a renderable ancestor brief template, and a new `DRAFT-INSTALL-v07.md`, all left uncommitted for planner review.

## Subagent A — scripts/install.sh

- 新增文件: [install.sh](/Users/ywf/ClawSeat/scripts/install.sh)
- 行数: `247`
- 状态:
  - `set -euo pipefail`
  - 支持 `--project <name>` 和 `--dry-run`
  - 失败统一走非零退出，并在 stderr 打 `ERR_CODE: ...`
  - host deps / machine scan / provider 选择 / brief 渲染 / tmux session 创建 / iTerm 六宫格 / memory 独立窗口 / ancestor 3-Enter flush 都已落进脚本
- 关键适配:
  - TODO 的 `core/scripts/scan_environment.py` 在仓库中不存在，改用 `core/skills/memory-oracle/scripts/scan_environment.py`
  - `core/scripts/iterm_panes_driver.py` 真实签名是 `STDIN JSON -> STDOUT JSON`
  - `scripts/launch-grid.sh` 保持不动；`install.sh` 直接走 native iTerm panes，而不是旧的 nested-tmux monitor 路径

Syntax check:

```text
bash -n scripts/install.sh && echo "syntax ok"
syntax ok
```

`--dry-run` 摘录:

```text
==> Step 1: host deps
[dry-run] brew install tmux
[dry-run] brew install --cask iterm2
OK: host deps
==> Step 2: environment scan
[dry-run] python3 /Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/scan_environment.py --output /Users/ywf/.agents/memory
==> Step 7: open six-pane iTerm grid
[dry-run] python3 /Users/ywf/ClawSeat/core/scripts/iterm_panes_driver.py <<JSON
{"title":"clawseat-install","panes":[...]}
```

## Subagent B — core/templates/ancestor-brief.template.md

- 新增文件: [ancestor-brief.template.md](/Users/ywf/ClawSeat/core/templates/ancestor-brief.template.md)
- 行数: `70`
- 内容:
  - v0.7 Phase-A brief 骨架
  - `B0/B1/B2/B3/B3.5/B5/B6/B7`
  - 失败处理
  - 硬规则
- 模板变量:
  - install-time 渲染变量: `${PROJECT_NAME}`, `${CLAWSEAT_ROOT}`
  - 运行时字面占位: `${seat}`（用于 B3.5 循环说明）

## Subagent C — DRAFT-INSTALL-v07.md

- 新增文件: [DRAFT-INSTALL-v07.md](/Users/ywf/ClawSeat/.agent/ops/install-nonint/DRAFT-INSTALL-v07.md)
- 行数: `192`
- 相比 `DRAFT-INSTALL-026.md` 的主要差异:
  - 入口从 `scripts/launch-grid.sh` 切到 v0.7 的 `scripts/install.sh`
  - Step 1 改成自动 bootstrap：host deps、machine 5 文件扫描、ancestor provider 选择、brief 渲染、iTerm 六宫格、独立 memory 窗口、3 次 Enter flush
  - Step 2 改成用户粘贴 prompt 后由 ancestor 接管，Phase-A 更新为 `B0~B7`
  - 新增 `B0` 的 env_scan LLM 分析、`B3.5` 串行逐个拉起 engineer seats
  - Failure Modes 新增 `PROVIDER_NO_KEY` / `ITERM_DRIVER_FAIL` / `B3.5_TIMEOUT`

## Verification

Line counts:

```text
247 scripts/install.sh
70 core/templates/ancestor-brief.template.md
192 .agent/ops/install-nonint/DRAFT-INSTALL-v07.md
```

Brief render example:

```text
python3 - <<'PY'
from pathlib import Path
from string import Template
p = Path('core/templates/ancestor-brief.template.md')
out = Template(p.read_text(encoding='utf-8')).safe_substitute(
    PROJECT_NAME='install',
    CLAWSEAT_ROOT='/Users/ywf/ClawSeat',
)
print(out.splitlines()[0])
print('vars:', sorted(set(__import__('re').findall(r'\$\{([^}]+)\}', p.read_text(encoding='utf-8')))))
print('rendered_lines:', len(out.splitlines()))
PY
# ClawSeat Ancestor Brief — Phase-A (install)
vars: ['CLAWSEAT_ROOT', 'PROJECT_NAME', 'seat']
rendered_lines: 70
```

## Notes

- `scripts/install.sh` 目前 **没有** 内部调用 `scripts/launch-grid.sh`。这是刻意保留的偏差：v0.7 安装路径已经切到 `iterm_panes_driver.py` 原生 pane，现有 `launch-grid.sh` 仍是旧 experimental 的 nested-tmux monitor 骨架。
- 我按 planner 补丁把 Step 3 的“无 credentials”提示收敛成两行：
  - `未检测到可用的 Claude Code 登录方式。请输入：`
  - `  base_url (回车=官方 Anthropic):`
  - `  api_key:`
- 没有执行真实 end-to-end smoke，因为它会实际安装依赖、创建 tmux sessions、启动 Claude、并打开 iTerm 窗口。
- 当前改动全部保持未提交，留给 planner 审。
