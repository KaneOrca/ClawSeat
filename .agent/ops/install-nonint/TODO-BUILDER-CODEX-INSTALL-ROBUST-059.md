# TODO — INSTALL-ROBUST-059 (install.sh 健壮性：session 生命周期 + 幂等 + provider 非交互)

```
task_id: INSTALL-ROBUST-059
source: planner
target: builder-codex
priority: P1 (minimax 实测阻塞；可与 058 合并调研)
type: 调研 + 修复（合并交付）
blocked-by: 无（可并行于 056）
```

## 背景

minimax 第二次跑 `scripts/install.sh`（~/.clawseat 内）暴露三个 install 健壮性问题。minimax 的根因分析有误（"`=` 前缀问题"），需 codex 重新定位并修复。

## 问题清单

### Q1 · Session 在 `configure_tmux_session_display` 被调用前已销毁

**minimax 报错**：
```
no such session: =install-ancestor
command failed: tmux set-option -t =install-ancestor detach-on-destroy off
ERR_CODE: COMMAND_FAILED
```

**minimax 误判**：归因为 "`=` 前缀" 语法问题。

**实际根因**（planner 初查）：
- `=` 是 tmux 正确的精确匹配前缀语法，无问题
- [core/launchers/agent-launcher.sh:1338](core/launchers/agent-launcher.sh) `tmux new-session -d -s "$SESSION_NAME" ... "bash $0 ... --exec-agent"` 创建 session
- 默认 `detach-on-destroy=on`，当 session 内唯一窗口的进程退出（如 claude CLI 立即挂掉、identity 脏、某配置不对）→ session 立即销毁
- launcher 返回 0（它只看 `tmux new-session` 的 exit code，不查进程是否存活）
- install.sh [scripts/install.sh:812](scripts/install.sh) 再调 `configure_tmux_session_display` → `set-option -t "=install-ancestor"` → session 已消失 → 报错
- 死锁：`detach-on-destroy off` 必须在 session 销毁**前**设置，但现在在销毁**后**才调

**调研 + 修复**：
- (a) 把 `detach-on-destroy off` **链到 new-session 的复合命令**里（tmux `\;` 语法），或
- (b) 在 launcher 内部 `tmux new-session -d -s` 后**立刻** `set-option`，再 exec agent 进程
- (c) 新增 `launch_seat` 成功后的 session 存活探测（`tmux has-session` + pane 健康），失败时 die 带诊断
- 决定推荐方案 + 测试：`tests/test_install_seat_session_survives_create.py`

### Q2 · Step 1/preflight 未检测 `phase=ready` 导致重复安装

**minimax 现象**：第一次 install 在 05:35 写 `phase=ready`，06:05 重跑同脚本，install.sh 继续走到 Step 7+ 而非提前退出。第二次重建时因状态脏触发 Q1 的 session 销毁。

**调研**：
- [scripts/install.sh](scripts/install.sh) grep `phase=ready` / `STATUS.md`：目前**无检测**
- STATUS.md 路径：`~/.agents/tasks/install/STATUS.md`
- 设计选项：
  - (A) Step 1 检测 `phase=ready` → 打印 "already installed, use --force to rebuild" + exit 0
  - (B) `--force` / `--reinstall` flag 显式覆盖
  - (C) 检测 identity dir 已存在时走 "incremental" 路径（只补缺失步骤）
- 推荐方案 + `tests/test_install_phase_ready_early_exit.py`

### Q3 · Provider 选择非交互模式

**minimax 现象**：
```
[1] claude-code + minimax (ANTHROPIC_AUTH_TOKEN -> minimaxi)   (recommended)
[2] claude-code + oauth_token
[3] claude-code + ARK 火山方舟
[c] enter custom base_url + api_key manually
```
需要 `echo "1" |` pipe，对 CI / 自动化 / sandbox 不友好。

**调研**：
- 增加 `--provider <n>` flag 或 `CLAWSEAT_INSTALL_PROVIDER=1` env var
- 检查 install.sh 当前是否已有类似 flag（grep `--provider` / `PROVIDER`）
- 考虑和 058（sandbox HOME detection）联动：sandbox 模式下默认选择 [1] minimax
- 测试：`tests/test_install_provider_noninteractive.py`

## 建议合并范围

**与 058 合并**（两者都是 install.sh 健壮性 + sandbox 兼容性）：
- 058 Q1-Q5：iTerm Step 7 best-effort + auto-kickoff 依赖 + ancestor 自驱 GUI + sandbox HOME 检测
- 059 Q1-Q3：session 生命周期 + 幂等 + provider 非交互

两个 RCA 统一命名 `RCA-INSTALL-ROBUST-058-059.md`（或保持两份互引），**推荐方案章节列统一的工作量 + 实施顺序**。

## 约束

- **先调研 RCA**，批准后再实施
- Q1 可能需要改 launcher（涉及 053/055 已 ship 的代码 —— 谨慎回归）
- Q2/Q3 属 install.sh 范围，改动小
- 鼓励 subagent 并发（3 个 Q 独立调研）
- 不破坏 v0.7 现有 ancestor brief / start-engineer 流程

## 输出

`.agent/ops/install-nonint/RCA-INSTALL-ROBUST-058-059.md`（或分文件）：
- Q1-Q3 根因 + 推荐修复
- 与 058 联动决策
- 工作量评估（trivial / moderate / large）
- 是否独立交付 / 合并 056 / 延迟 v0.8

## Deliverable

调研阶段：`RCA-INSTALL-ROBUST-058-059.md`
实施阶段（批准后）：`DELIVERY-INSTALL-ROBUST-059.md` + pytest

**不 commit**（planner 统一）。完成后 tmux notify planner。
