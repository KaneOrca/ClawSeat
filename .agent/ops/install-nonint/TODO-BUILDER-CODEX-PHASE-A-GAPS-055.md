# TODO — PHASE-A-GAPS-055 (smoke02 Phase-A 暴露的 4 个根因 gap)

```
task_id: PHASE-A-GAPS-055
source: planner
reply_to: planner
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P1
subagent-mode: OPTIONAL (单 agent)
scope: smoke02 Phase-A B0/B2.5/B3.5 暴露的 4 个 gap（依赖缺失 / sandbox HOME 多工具盲点 / provider 命名歧义 / 始祖未查 memory）
queued: 可与 FEISHU-AUTH-053 并行（R1 合并，R2-R4 独立）
```

## Context

smoke02-ancestor Phase-A 报告（authoritative）：

| 阶段 | 症状 | 推断根因 |
|------|------|----------|
| B0 env_scan | LLM 分析阶段提示 `tomli` 缺失 | agent_admin.py 的 `try tomllib / except tomli` fallback 在 sandbox Python 上走 tomli 分支；sandbox 没装 tomli |
| B2.5 bootstrap | `bootstrap_machine_tenants.py` 依赖 tomli → pip install tomli 人肉解决 | 同上，install 链路未保证 tomli 可用 |
| B3.5 planner | operator 指定 `ark`，原计划 gemini + `volcengine-plan`；switch-harness 不认 `volcengine-plan` | ARK-050 只在 claude harness 把 ark 加入，非 claude harness（gemini / codex planner）的 provider 命名对齐缺失 |
| B3.5 designer | gemini seat session missing / 启动失败 | sandbox HOME 缺 gemini CLI 的配置/凭证目录（`.config/gemini/` 或 `.gemini/`），与飞书 R1 同类 |
| 全程 | 始祖没向 memory 发任何 query | brief / SKILL.md B0 / B2.5 / B3.5 未强制 "查 memory 历史经验" 步骤 |

**不重复 FEISHU-AUTH-053 R1 的工作**：R1 已规划 `seed_user_tool_dirs()` 扩展多工具 seed（`.lark-cli`、iTerm2）。本 TODO R2 在 R1 基础上**追加** gemini + 其他可预期的 CLI 工具 seed 条目。

## 修复

### R1 · tomli 依赖自愈（P1, 最简修）

`scripts/install.sh` Step 3（env_scan 前）或 `scripts/agent-launcher.sh` sandbox HOME 初始化阶段加一次：

```bash
# Ensure tomllib is available (Python 3.11+) or install tomli fallback
if ! python3 -c "import tomllib" >/dev/null 2>&1; then
  if ! python3 -c "import tomli" >/dev/null 2>&1; then
    python3 -m pip install --user --quiet tomli >/dev/null 2>&1 || true
  fi
fi
```

位置优先：`scripts/install.sh` Step 3 ancestor 启动前最稳妥（跑在 host Python）。sandbox 层的 Python 继承 site-packages 路径，通常即可 import。

**测试**：
- `tests/test_install_tomli_guard.py`：mock `python3 -c "import tomllib"` 失败 → 验证 install.sh 调用 `pip install --user tomli`
- 跑 pytest 回归 `test_install_isolation.py` / `test_install_memory_singleton.py` 确保未破坏现有路径

### R2 · sandbox HOME 多工具 seed（与 FEISHU-AUTH-053 R1 合并；本 TODO 只贡献清单）

在 R1 的 `seed_user_tool_dirs()` 数组里**追加**以下 seed 条目：

```bash
local seeds=(
  # FEISHU-AUTH-053 R1 已有
  ".lark-cli"
  "Library/Application Support/iTerm2"
  "Library/Preferences/com.googlecode.iterm2.plist"
  # PHASE-A-GAPS-055 R2 追加
  ".config/gemini"                       # gemini CLI (Google)
  ".gemini"                              # 某些版本 gemini CLI fallback 目录
  ".config/codex"                        # codex CLI（已知用到 OAuth 时）
  ".codex"                               # codex CLI fallback
)
```

**注意**：
- 这些都是 symlink（指向 `$REAL_HOME/<sub>`），不是 copy
- seed 条目幂等：`if [[ -e "$src" && ! -e "$tgt" ]]` 已守门
- 未来新增 CLI 工具只需追加数组

**测试**：在 `tests/test_launcher_seed_user_tool_dirs.py`（FEISHU-AUTH-053 R1 新增）里扩展 assertion，验证 gemini / codex 目录也被 symlink（模拟 real HOME 有这些目录）。

### R3 · ark provider 名跨 seat-type 对齐（P1）

现状（`agent_admin_switch.py:56`）：

```python
if session.tool == "claude" and session.provider == "ark":
    # ARK claude 逻辑
```

只有 `tool == "claude"` 才认 ark。planner 默认 `tool == "gemini"`（或 codex），operator 强制指定 ark 时 switch-harness 报错。

**修复方向**（codex 调研后定）：

A. 放宽 switch-harness：`if session.provider == "ark": tool = "claude"` auto-migrate（seat type 自动转 claude）
B. 严格 switch-harness：不允许 gemini/codex seat 用 ark provider，switch-harness 先报明确错误 "ark 只支持 claude harness，请先 switch-harness --tool claude"
C. operator 在 CLI 直接指定 seat-type + provider：`switch-harness planner --tool claude --provider ark`

**建议**：B（明确错误）+ 在 brief B3.5 提示下给 operator 清楚指引。但具体方案让 codex 权衡后出。

**测试**：
- `tests/test_switch_harness_ark_cross_tool.py`：gemini seat + `--provider ark` → 清晰 error 或 auto-migrate 成功

### R4 · brief / SKILL.md 强制 memory 查询（P2）

`core/templates/ancestor-brief.template.md` B0 和 B2.5 开头各加一段：

```markdown
**步骤 N.0（memory 查询，强制）**：

在执行本步之前，向 memory 发一次 query：
```bash
bash ${AGENT_HOME}/scripts/send-and-verify.sh \
  --to machine-memory-claude \
  --text "query: [B0/B2.5/B3.5 根据本步的 context]，项目 ${PROJECT_NAME}，有无历史经验或最佳实践？"
```

等 memory 回报 1-2 行摘要（或 "无相关"），记录在 phase-a-decisions.md。不 query 跳过 → ARCH_VIOLATION。
```

`core/skills/clawseat-ancestor/SKILL.md` §2 Phase-A 表格里每一步 B0 / B2.5 / B3.5 对应行加一列 "memory_query" = yes。

**测试**：
- `tests/test_ancestor_brief_memory_query_steps.py`：grep brief template 确认 B0/B2.5/B3.5 都含 "memory query / send-and-verify"
- `tests/test_ancestor_skill_memory_query_column.py`：grep SKILL.md §2 表格含 "memory_query" 列且 B0/B2.5/B3.5 值为 yes

### R5 · seed_user_tool_dirs retroactive reseed（解决 planner 复用不了 feishu auth）

**问题**（smoke01 实测 + minimax SMOKE Phase 2 确认）：

- smoke01 sandbox 是 FEISHU-AUTH-053 R1 落地前创建，各 seat sandbox HOME 没有 `.lark-cli` symlink
- 始祖 `lark-cli auth login` 写到它自己 sandbox 的独立 `.lark-cli/config.json`（不是 real HOME）
- planner / builder 各自 sandbox HOME 互相看不到，要求各自重新 auth
- `seed_user_tool_dirs` 运行时条件 `! -e "$tgt"` 对已有目录一概 skip，不 retroactive

**修复 R5.1 · seed_user_tool_dirs 语义升级**（`core/launchers/agent-launcher.sh`）：

```bash
seed_user_tool_dirs() {
  local runtime_home="$1"
  local seeds=( ... )  # 保持现状，含 R2 扩展的 gemini/codex
  local subpath src tgt backup_base="$runtime_home/.sandbox-pre-seed-backup"
  for subpath in "${seeds[@]}"; do
    src="$REAL_HOME/$subpath"; tgt="$runtime_home/$subpath"
    [[ -e "$src" ]] || continue
    if [[ -L "$tgt" ]]; then
      # 已是 symlink，幂等 skip
      continue
    elif [[ ! -e "$tgt" ]]; then
      mkdir -p "$(dirname "$tgt")"; ln -s "$src" "$tgt"
    else
      # tgt 是独立目录/文件（pre-R1 sandbox 的残留）
      # 策略：备份后替换为 symlink
      mkdir -p "$(dirname "$backup_base/$subpath")"
      mv "$tgt" "$backup_base/$subpath.$(date +%s)"
      ln -s "$src" "$tgt"
    fi
  done
}
```

**修复 R5.2 · `agent_admin session start-engineer` 启动时调用 reseed**（`core/scripts/agent_admin_session.py`）：

在 `start_engineer()` launch subprocess 之前，调用 launcher 的 `seed_user_tool_dirs` 逻辑（可以通过一个轻量 `agent-launcher.sh --reseed-sandbox-only <session>` 子命令，或直接在 python 里复现 symlink 逻辑）。保证**每次 seat 启动都检查 sandbox HOME seed 状态**，不只信 install-time。

**修复 R5.3 · 新命令 `agent_admin session reseed-sandbox [--all|<seat>]`**（operator 手动触发）：

```
agent_admin session reseed-sandbox --project smoke01 --all
  # 遍历所有 project seats 的 sandbox HOME，强制 reseed
  # 已是 symlink → skip，独立目录 → 备份 + 替换为 symlink
  # 回报变更列表
```

### R6 · 跨 seat 通讯硬规则（解决始祖忘用 send-and-verify.sh）

**问题**：始祖 Claude Code context 里没有强规则要求"所有跨 seat 文本通讯必须走 `send-and-verify.sh`"，本能倾向裸 `tmux send-keys`，导致 TUI 吞回车 / 文本与 Enter 之间没 1 秒延迟。

**修复 R6.1 · SKILL.md §9 Hard rules 扩展**（`core/skills/clawseat-ancestor/SKILL.md`）：

```markdown
### 跨 seat 文本通讯硬规则（所有 project seat）

**禁止**：裸 `tmux send-keys -t <project-seat> '...'`（任何 project seat：planner / builder / qa / reviewer / designer）

**唯一允许方式**：
bash ${CLAWSEAT_ROOT}/core/shell-scripts/send-and-verify.sh \
  --project ${PROJECT_NAME} <seat> "<message>"

原因：
- TUI（尤其 Codex / Gemini）会吞 Enter 如果文本和 Enter 之间没 sleep
- send-and-verify.sh 内置 1s delay + 3 Enter flush，保证消息被 TUI 正确接收
- 裸 send-keys 的失败没有 error feedback，始祖无法发现

**唯一例外**：memory seat（machine-memory-claude）—— 既不允许 send-keys 也不允许 send-and-verify，见 §9 memory 通讯规则。

**派发 TODO 任务**（结构化派任务）：用 `dispatch_task.py` 而不是 send-and-verify.sh，两者分工：
- send-and-verify.sh = 快速文本消息
- dispatch_task.py = 带 task_id / TASKS.md 条目 / mailbox 的正式派任务
```

**修复 R6.2 · brief B3.5 / B5 / B6 派任务示例**（`core/templates/ancestor-brief.template.md`）：

每一步涉及给 planner/builder/qa 发消息的命令行，改为 send-and-verify.sh 模板。不要出现裸 `tmux send-keys -t`。

**修复 R6.3 · ARCH_VIOLATION 触发清单扩展**（SKILL.md §11）：

现有 ARCH_VIOLATION 模板（MEMORY-IO-051 Part C）新增一条：

```
**VIOLATION: bare tmux send-keys to project seat**

检测：grep 始祖 terminal log / task output 出现 `tmux send-keys -t <project>-<seat>`
响应：reject + 提示正确命令模板（send-and-verify.sh）
```

### R7 · gemini trust prompt 自动解除（解决 smoke02-designer-gemini 卡在首次 trust 交互）

**问题**（smoke02 实测）：

- gemini CLI 访问 sandbox HOME 下新 workdir 时弹 "Do you trust the files in this folder?" 交互，**阻塞 TUI**
- 始祖 check-seat 用 send-keys `READY` + grep 判断就绪，trust prompt 吞掉回车，永远拿不到 READY → 误报 "session missing / 启动失败"
- 根因：launcher 的 `prepare_gemini_home` 只 symlink `settings.json` 等，**没预写 `trustedFolders.json`** 标记当前 workdir 为 trust

**gemini trust config schema**（real HOME 参考）：

```
~/.gemini/trustedFolders.json
{
  "/Users/ywf/coding": "TRUST_FOLDER",
  "/Users/ywf": "TRUST_FOLDER"
}
```

精确路径匹配，不递归。

**修复 R7.1 · `prepare_gemini_home` 预写 trusted workdir**（`core/launchers/agent-launcher.sh`）：

```bash
prepare_gemini_home() {
  local runtime_home="$1"
  local workdir="${2:-${WORKDIR:-}}"   # 新增 workdir 参数（run_gemini_runtime 传进来）
  local gemini_home="$runtime_home/.gemini"
  mkdir -p "$gemini_home"

  # 现有 shared_items symlink 保持不变（settings.json / installation_id / skills）
  ...existing...

  # R7.1 · 自动 trust 当前 workdir，避免首次交互阻塞
  if [[ -n "$workdir" ]]; then
    python3 - "$gemini_home/trustedFolders.json" "$REAL_HOME/.gemini/trustedFolders.json" "$workdir" <<'PY'
import json, sys, pathlib
target = pathlib.Path(sys.argv[1])
src = pathlib.Path(sys.argv[2])
workdir = sys.argv[3]
data = {}
if src.exists():
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        data = {}
data[workdir] = "TRUST_FOLDER"
target.write_text(json.dumps(data, indent=2), encoding="utf-8")
PY
  fi
}
```

调用方 `run_gemini_runtime` 传入 `$workdir`：

```bash
prepare_gemini_home "$HOME" "$workdir"
```

**修复 R7.2 · `run_gemini_runtime` oauth 分支也 seed**（避免 OAuth 路径下同样阻塞）：

oauth 分支当前是 `export HOME=$REAL_HOME` 复用 real HOME，所以 real HOME 的 `trustedFolders.json` 本就起作用。但如果 operator 没预先 trust workdir，仍卡。同样用 python helper 追加 workdir 到 real HOME 的 trustedFolders.json（备份原文件）。

**修复 R7.3 · 始祖 check-seat 脚本容错 trust prompt**（`scripts/wait-for-seat.sh` 或 check 逻辑）：

- 如果 send-keys READY 60s 后仍没回报：capture-pane 检测 "Do you trust the files" / "Trust folder" 关键字
- 命中 → 打印明确错误："gemini trust prompt detected at <seat>, operator attach pane and press 1"
- 未命中 → 回退到原 "session missing" 错误

R7.3 的价值是**给始祖 / operator 更诊断性的错误**，避免"启动失败"误导。

### R8 · wait-for-seat.sh persistent re-attach（核心根因：即使需要 onboard 也要在 iTerm 窗口持续可见）

**问题**（smoke02 实锤）：

- iTerm pane#6 designer 显示 `[exited] ... ywf@ywfdeMac-Studio ~ %`（zsh 提示符）
- `smoke02-designer-gemini` tmux session 仍然 ALIVE（卡 trust prompt）
- operator 从 iTerm 看不到任何 gemini 状态 → 误判 "没启动"

事件重建：
1. wait-for-seat.sh 过去某时刻 `exec tmux attach -t smoke02-designer-gemini`
2. operator 某次误操作（Ctrl+B D / Ctrl+C / 关闭 tab / detach）
3. `exec tmux attach` 是**一次性**的 → attach 返回后 bash 进程终结
4. pane 标记 `[exited]` 回 zsh
5. tmux session 仍在后台运行，但 iTerm pane 不再 reconnect

**这是用户强调的核心诉求**：即使 seat 需要 onboard（trust prompt / Claude welcome），iTerm pane 也必须**持续可见**到 seat 内部状态，operator 一眼能看到 prompt 就能响应。

**修复 R8.1 · wait-for-seat.sh loop re-attach**（`scripts/wait-for-seat.sh`）：

```bash
#!/usr/bin/env bash
set -uo pipefail   # 注意：不加 -e（tmux attach 退出不视为错误）

usage() {
  printf 'Usage: %s <project-seat> | <project> <seat>\n' "$0" >&2
  exit 2
}

if [[ $# -eq 1 ]]; then
  BASE_SESSION="$1"
elif [[ $# -eq 2 ]]; then
  BASE_SESSION="$1-$2"
else
  usage
fi

POLL_SECONDS="${WAIT_FOR_SEAT_POLL_SECONDS:-5}"
RECONNECT_PAUSE="${WAIT_FOR_SEAT_RECONNECT_PAUSE:-2}"

resolve_session() {
  local base="$1" candidate=""
  for candidate in "$base" "$base-claude" "$base-codex" "$base-gemini"; do
    if tmux has-session -t "=$candidate" 2>/dev/null; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

print_waiting() {
  printf '\033[2J\033[H'   # clear
  printf '┌─────────────────────────────────────────────────────────\n'
  printf '│ pane waiting for: %s\n' "$BASE_SESSION"
  printf '│ (seat will appear once ancestor spawns it)\n'
  printf '│ poll every %ss\n' "$POLL_SECONDS"
  printf '└─────────────────────────────────────────────────────────\n'
}

print_reconnecting() {
  printf '\n\033[33m┌─────────────────────────────────────────────────\n'
  printf '│ DETACHED from %s — reconnecting in %ss ...\n' "$1" "$RECONNECT_PAUSE"
  printf '│ (tmux session still alive; press Ctrl+C to abort wait)\n'
  printf '└─────────────────────────────────────────────────\033[0m\n'
}

while true; do
  if TARGET_SESSION="$(resolve_session "$BASE_SESSION")"; then
    # 不用 exec，允许 attach 返回后继续 loop
    tmux attach -t "=$TARGET_SESSION" || true
    print_reconnecting "$TARGET_SESSION"
    sleep "$RECONNECT_PAUSE"
  else
    print_waiting
    sleep "$POLL_SECONDS"
  fi
done
```

**行为差异**：
- attach 成功后 gemini trust prompt / claude welcome 在 pane 直接可见 → operator 一眼看到
- operator detach（Ctrl+B D）→ pane 显示黄色 "DETACHED" banner + 2s 后自动 reconnect
- tmux session 死亡 → 自动降级到 "waiting" 显示，直到 ancestor 再起 session
- operator 想彻底退出 → Ctrl+C 停止 loop

**修复 R8.2 · tmux session 防误 detach（可选加固）**：

install.sh Step 7 创建 seat tmux session 时追加 `tmux set-option -t <session> detach-on-destroy off`（operator 关闭最后 client 时不杀 session）。也可在 `agent_admin session start-engineer` 里同步设置。

### R9 · pane status line 可见性增强（operator 一眼知道 pane 状态）

**问题**：即使 R8 持续 re-attach，operator 仍然可能不清楚 "这个 pane 目前是 waiting / attached / disconnected 状态"。

**修复 R9.1 · tmux seat session 全局 status line**（install.sh Step 5.5 或 agent_admin session start-engineer）：

```bash
# 每个 seat session 启动时：
tmux set-option -t <session> status on
tmux set-option -t <session> status-left '[#{session_name}] '
tmux set-option -t <session> status-right '#{?client_attached,ATTACHED,WAITING} | %H:%M'
tmux set-option -t <session> status-style 'fg=white,bg=blue,bold'
```

这样每个 pane 底部都有清晰的 session 名 + attach 状态。

**修复 R9.2 · trust prompt / onboarding 显著 marker**：

iTerm 有 badge 功能（小字覆盖），或 tmux session 名里加 ⚠ unicode marker：
- 可选：ancestor check-seat 如果检测到 seat 卡 trust / onboard，通过 `tmux rename-session` 临时加前缀 `[⚠NEEDS_ONBOARD]`（operator 看到名字就知道）
- 解除后 ancestor 恢复原名

R9 为可选 polish，R8 是主修复。

### R10 · `start_engineer` onboarding-aware retry（smoke02 实战暴露）

**问题**（capture-pane + session lifecycle 实锤）：

始祖跑 `agent_admin session start-engineer smoke02-designer` 的 retry 逻辑 **对需要 operator 交互 onboard 的 TUI 破坏性**：

- `_assert_session_running` 只判 `tmux has-session` + `list-panes` rc，不识别 "operator 正在 onboarding"
- TMUX_COMMAND_RETRIES = 2，retry delay = 1s
- 某次 `_assert_session_running` 判失败 → **无条件 `kill-session`** → operator auth / trust 被腰斩
- 循环：kill → relaunch → operator 重来 → 再 kill → 最终 retries 耗尽 → session 销毁

实证：smoke02-designer-gemini 在 planner 第一次 capture-pane 时 ALIVE（trust prompt 可见），operator 正在交互；15 分钟后 `tmux has-session -t smoke02-designer-gemini` 返 rc=1，session 已不存在。期间 operator 汇报 "正在完成认证，结果又断开了"。

**修复 R10.1 · `_assert_session_running` onboarding 容错**（`core/scripts/agent_admin_session.py`）：

```python
def _is_session_onboarding(self, session_name: str) -> bool:
    """Detect operator-interactive onboard state (trust prompt / OAuth URL / welcome).
    Returns True if pane content matches known onboarding markers.
    Used by _assert_session_running to avoid killing operator mid-interaction.
    """
    result = self._run_tmux_with_retry(
        ["capture-pane", "-t", f"={session_name}", "-p", "-S", "-50"],
        reason=f"onboarding detect for {session_name}",
        check=False,
    )
    if result.returncode != 0:
        return False
    content = result.stdout or ""
    markers = [
        "Do you trust the files in this folder",   # gemini
        "Trust folder",                             # gemini
        "Welcome to Claude Code",                   # claude first-run
        "authenticate with your",                   # claude OAuth
        "https://accounts.google.com",              # gemini OAuth redirect
        "Paste the code",                           # OAuth device flow
        "Enter your API key",                       # manual key entry
    ]
    return any(m in content for m in markers)

def _assert_session_running(self, session, *, operation):
    if not self.hooks.tmux_has_session(session.session):
        raise SessionStartError(
            f"{operation} failed for '{session.session}': session missing after startup; state={self._session_window_state(session.session)}"
        )
    # R10.1 · 如 session 存在且 operator 正在 onboard，不视为失败
    if self._is_session_onboarding(session.session):
        print(
            f"_assert_session_running: session={session.session} ONBOARDING_DETECTED "
            f"(trust prompt / OAuth / welcome) — treating as alive, operator interaction required",
            file=sys.stderr,
        )
        return
    output = self._run_tmux_with_retry(
        ["list-panes", "-t", session.session, "-F", "#{pane_id}|#{pane_current_command}"],
        reason=f"{operation} verify panes for {session.session}",
        check=False,
    )
    if output.returncode != 0 or not output.stdout.strip():
        raise SessionStartError(...)
```

**修复 R10.2 · `start_engineer` except 块 onboarding-aware cleanup**：

```python
except SessionStartError as exc:
    last_error = exc
    # R10.2 · 不要盲目 kill session：先检查是否 operator onboarding
    if self.hooks.tmux_has_session(session.session):
        if self._is_session_onboarding(session.session):
            print(
                f"start_engineer: session={session.session} appears to be onboarding "
                f"(operator interaction in progress); abort retry, trust session.",
                file=sys.stderr,
            )
            # 退出 retry loop，不 kill，不 raise — 让 operator 完成 onboarding
            return
        self._run_tmux_with_retry(
            ["kill-session", "-t", session.session],
            reason=f"cleanup partial session {session.session}",
            check=False,
        )
    if attempt < TMUX_COMMAND_RETRIES:
        time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
        continue
    ...
```

**修复 R10.3 · 幂等 check idempotent path 同样保护**：

start_engineer 开头的 `if self.hooks.tmux_has_session(session.session): self._assert_session_running(...)` 也会走到 R10.1 的 onboarding 分支，保证幂等。

**修复 R10.4 · brief / SKILL.md 警示始祖不要循环验证 seat**（`core/templates/ancestor-brief.template.md` B3.5）：

```markdown
**重要**：对每个 seat 只调用 **一次** `agent_admin session start-engineer`。启动后通过 `agent_admin session list` / `tmux has-session` 查状态，不要反复 `start-engineer` 触发 retry（会 kill operator 正在交互的 onboarding session）。

seat 启动后处于 onboarding 时：
- `agent_admin session list` 会显示 session=ALIVE
- 告知 operator "请在 iTerm pane 完成 onboarding（trust folder / OAuth / API key）"
- **不要** 再次 `start-engineer`；operator 完成后自然 ready
```

### R10 测试

- `tests/test_start_engineer_onboarding_detect.py`：
  - mock `capture-pane` 返 "Do you trust the files" → `_is_session_onboarding` 返 True
  - mock `capture-pane` 返 normal prompt → 返 False
- `tests/test_start_engineer_no_kill_during_onboard.py`：
  - mock onboarding 返 True → start_engineer 不 kill session
  - mock onboarding 返 False + not running → 走原 kill+retry 路径
- `tests/test_ancestor_brief_no_retry_loop.py`：
  - grep brief 含 "不要反复 start-engineer" 警示
  - grep brief 含 "通过 session list 查状态"

### R11 · Project isolation + 始祖诊断护栏（smoke02 窗口混淆 + smoke01 symlink 错位 事故根治）

**两个独立事件汇总到一个 R**：

**事件 A · 项目身份混淆**：smoke02 始祖在 clawseat-smoke01 iTerm 窗口里对 designer pane 发命令（"designer" pane 名吃掉了 `smoke01-` 前缀，始祖凭直觉选）

**事件 B · 飞书 auth 诊断盲区**：smoke01 始祖反复把 real HOME `/Users/ywf`（余文锋）说成 "sandbox 张根铭"，手动把 planner HOME symlink 到 **ancestor sandbox HOME**（错的源头），反而让 planner 继承张根铭 app 而不是余文锋

**根因共通**：始祖 context 没有 **运行时身份断言机制**；遇到歧义靠直觉。

**修复 R11.1 · brief 硬规则 "project scope 断言"**（`core/templates/ancestor-brief.template.md`）：

每次进入 B3.5 / B5 / B6 / B7 操作 seat 前，强制跑：

```bash
# project scope assertion（每个 Phase 步骤开始时）
[ "$(echo $PROJECT_NAME)" ] || { echo "ARCH_VIOLATION: PROJECT_NAME unset"; exit 1; }
echo "scope: project=$PROJECT_NAME ancestor_session=$(tmux display-message -p '#{session_name}')"
```

输出必须匹配 `ancestor_session=${PROJECT_NAME}-ancestor`；不匹配 → halt 并报告 operator "始祖身份错位"。

**修复 R11.2 · iTerm 窗口操作 canonical 化**（brief + SKILL.md）：

- 禁止始祖用 osascript / `iterm_panes_driver.py` 手拼窗口操作（ARCH_VIOLATION）
- 唯一入口：`agent_admin window open-grid --project $PROJECT_NAME`（054 已交付）
- 未来 "window focus" / "window pane-send" 也必须走 `agent_admin window <subcommand> --project <name>`

**修复 R11.3 · 始祖 lark-cli 诊断前置核验**（SKILL.md §5.z troubleshooting 前言）：

任何飞书 / lark-cli auth 诊断**开始前**，始祖必须跑：

```bash
python3 -c "from core.lib.real_home import real_user_home; print('real_user_home:', real_user_home())"
echo "shell HOME: $HOME"
```

- 两值对照，明确 real HOME vs sandbox HOME
- 未跑即下诊断结论 = ARCH_VIOLATION
- 特别：始祖**不允许**根据路径前缀直觉判断 HOME 身份，必须信 `real_user_home()` 返回值

**修复 R11.4 · 禁止始祖手动 symlink 调试 auth**（SKILL.md §9 ARCH_VIOLATION 列表）：

- 手动 `ln -s <sandbox>/.lark-cli` → ARCH_VIOLATION
- 手动 `HOME=<sandbox> lark-cli auth login` → ARCH_VIOLATION（会往 sandbox 写独立 auth，污染跨项目）
- pre-existing sandbox 复用失败的**唯一**修复入口：
  ```
  python3 core/scripts/agent_admin.py session reseed-sandbox --project <name> --all
  ```

**修复 R11.5 · `send-and-verify.sh` / 所有跨 seat 命令强制 `--project` scope**（brief + SKILL.md）：

现有 `send-and-verify.sh --project` guardrail 已 C6 落地，但 brief 里还有裸 send-keys 示例。R11.5 把所有通讯例子都补 `--project $PROJECT_NAME` 前缀。

**修复 R11.6（长期，可 defer）· sandbox 独立 `TMUX_TMPDIR`**：

launcher 为每个 seat 设 `TMUX_TMPDIR=<sandbox_home>/.tmux/`，tmux server 按 project 隔离：
- `tmux ls` 在 sandbox 里只看得到自己的 session
- 消灭 "跨项目看到其他 session" 的架构漏洞
- 例外：`machine-memory-claude` 单独 expose（singleton 跨项目可见）

R11.6 是架构重构，不卡 R7-R10 + R11.1-5。标记 v0.8 候选，除非 operator 强制要求。

### R11 测试

- `tests/test_ancestor_brief_project_scope_assertion.py`：grep brief 含 `echo "scope: project=$PROJECT_NAME"` pattern
- `tests/test_ancestor_skill_window_ops_canonical.py`：SKILL.md 明确禁止 osascript / iterm_panes_driver 手拼
- `tests/test_ancestor_skill_larkcli_diagnostic_gate.py`：§5.z 开头含 `real_user_home()` 前置核验
- `tests/test_ancestor_skill_no_manual_symlink.py`：§9 ARCH_VIOLATION 列表含 "手动 symlink .lark-cli"

**测试**：

- `tests/test_launcher_gemini_trust_seed.py`：
  - 新建 sandbox，调用 `prepare_gemini_home runtime_home /tmp/test-workdir`
  - 验证 `$runtime_home/.gemini/trustedFolders.json` 存在且含 `/tmp/test-workdir: TRUST_FOLDER`
  - 验证 real HOME 已有其他 trust entries 被保留
- `tests/test_wait_for_seat_trust_detection.py`：
  - mock tmux capture-pane 返回 "Do you trust" 字样 → wait-for-seat 打印明确错误而非超时
  - mock 返回 READY → 正常 attach

### R12 · brief Common Operations cookbook（smoke01 重启 planner 事故）

**问题**（实测）：始祖 restart 后被 operator 要求"重启 planner"，它**没找到 brief 里的对应命令**（B3.5 spawn 流程已结束 phase，始祖不会回查），开始：
- 试 v0.5 旧 API `agent_admin start-identity claude.oauth.anthropic.smoke01.planner`
- 试 v0.8 未实现的 `clawseat init`
- `sudo ln -sf /usr/bin/python3 /usr/local/bin/python3.11`（改宿主环境，严重越界）
- 始终未 grep brief / SKILL 找 canonical 命令

**根因**：brief 是按 Phase（B0-B7 流程）组织的，**没有 "任意时点都可查的常用操作" 索引**。

**修复 R12.1 · brief 末尾追加 "Common Operations Cookbook"**（`core/templates/ancestor-brief.template.md`）：

```markdown
## Common Operations Cookbook（任何时点查阅，覆盖 Phase 之外）

### Seat 生命周期

| 场景 | 命令 |
|------|------|
| 首次 spawn / 重启已死 seat | `python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py session start-engineer <seat> --project ${PROJECT_NAME}` |
| 切换 seat harness（claude→codex 等）| `python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py session switch-harness --project ${PROJECT_NAME} --engineer <seat> --tool <claude\|codex\|gemini> --mode <oauth\|oauth_token\|api> --provider <provider>` |
| 强制 reset 重启（kill+relaunch）| 同上 + `--reset` flag |
| 查所有 seat 状态 | `python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py session list --project ${PROJECT_NAME}` |
| 检查单个 tmux session 是否存活 | `tmux has-session -t '${PROJECT_NAME}-<seat>'` |

### Sandbox HOME / lark-cli

| 场景 | 命令 |
|------|------|
| sandbox 复用 lark-cli auth 失败 | `python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py session reseed-sandbox --project ${PROJECT_NAME} --all` |
| 飞书诊断前置核验 real HOME | `python3 -c "from core.lib.real_home import real_user_home; print(real_user_home())"` |

### Window / iTerm

| 场景 | 命令 |
|------|------|
| 重开 / 恢复 iTerm 6 宫格 | `python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py window open-grid --project ${PROJECT_NAME} --recover` |
| 同时开 memory 独立窗口 | 加 `--open-memory` flag |

### Brief drift

| 场景 | 命令 |
|------|------|
| 检查自己是否过时 | `bash ${CLAWSEAT_ROOT}/scripts/ancestor-brief-mtime-check.sh` |

### 通讯

| 场景 | 命令 |
|------|------|
| 给其他 seat 发消息 | `bash ${CLAWSEAT_ROOT}/core/shell-scripts/send-and-verify.sh --project ${PROJECT_NAME} <seat> "<text>"` |
| 派结构化 TODO 任务 | `python3 ${CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/dispatch_task.py ...` |

### 飞书

| 场景 | 命令 |
|------|------|
| 飞书联调 troubleshooting | 见 SKILL.md §5.z 7 步流程 |
| 发送任务报告 | `FEISHU_SENDER_MODE=bot python3 ${CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/send_delegation_report.py ...` |
```

### R13 · 始祖 meta-rule "执行前先查 canonical"（smoke01 凭直觉拼 CLI 事故）

**修复 R13.1 · SKILL.md §9 ARCH_VIOLATION 列表追加**：

```markdown
| "我猜命令名是 ..." / 凭训练数据拼 CLI | 必须先 grep brief Cookbook 或 SKILL.md 找 canonical | grep "<场景关键字>" $CLAWSEAT_ANCESTOR_BRIEF SKILL.md |
| "我先 sudo / pip install / brew install ..." | **禁止**改宿主环境（除 brief 明确指引）| 报 operator："需要装 X，请你来做" |
| 试旧版 API（start-identity / clawseat init / clawseat-cli ...）| 这些是 v0.5/v0.6/v0.8 名字；canonical 是 agent_admin.py | 见 Common Operations Cookbook |
```

**修复 R13.2 · brief 开头加 meta-rule**：

```markdown
## Meta-rule（最高优先级）

执行任何 shell 命令前**必须先**：
1. grep `$CLAWSEAT_ANCESTOR_BRIEF` 找场景关键字（"重启" / "切换" / "lark-cli" 等）
2. 命中 Cookbook → 用 canonical 命令
3. 未命中 → grep `${CLAWSEAT_ROOT}/core/skills/clawseat-ancestor/SKILL.md`
4. 仍未命中 → 报 operator："Cookbook 没覆盖此场景，请提供命令"

**禁止**：
- 凭训练数据 / 直觉拼装 CLI 命令
- sudo / pip install / brew install 改宿主环境（除非 brief 明确指引）
- 试错式跑命令（一个 fail 就换名字再试）
```

### R12 + R13 测试

- `tests/test_ancestor_brief_cookbook_section.py`：grep brief 末尾含 "Common Operations Cookbook"，覆盖 5 个场景类别（seat lifecycle / sandbox / window / drift / 通讯）
- `tests/test_ancestor_brief_meta_rule.py`：grep brief 开头含 "Meta-rule" + "执行前先 grep" + "禁止 sudo / pip install"
- `tests/test_ancestor_skill_arch_violation_cli_guess.py`：SKILL.md §9 含 "凭训练数据拼 CLI" / "v0.5 旧 API" 等 violation 类别

### R5+R6+R7+R8+R9+R10+R11+R12+R13 测试

- `tests/test_launcher_seed_reseed_existing.py`：mock pre-existing sandbox `.lark-cli` 独立目录 → 验证 R5.1 备份 + 创建 symlink
- `tests/test_agent_admin_session_reseed.py`：`reseed-sandbox --all` 对多 seat 幂等，已是 symlink 跳过
- `tests/test_ancestor_skill_comm_discipline.py`：grep SKILL.md §9 含 "跨 seat 文本通讯硬规则" + 明确 `send-and-verify.sh` 模板
- `tests/test_ancestor_brief_no_bare_send_keys.py`：grep brief 模板**不**含 `tmux send-keys -t ${PROJECT_NAME}-` pattern（或只出现在 memory 禁止说明里）

## 约束

- 不动 bootstrap_machine_tenants.py / agent_admin.py 的 tomllib fallback 代码（已规范）
- 不改 agent-launcher.sh 的 sandbox HOME 隔离逻辑，只扩展 seed 清单和时机
- R4 不强制 memory 必须回应（allow silence）；只强制 ancestor 发 query
- R3 的方案（A/B/C）由 codex 调研后定，不预设
- **R5.1 备份前要确认 sandbox 的独立目录是否含 operator 未保存工作**（大概率只是 lark-cli 残留，低风险）；备份到 `.sandbox-pre-seed-backup` 保留 30 天留证
- R6 send-and-verify.sh 的 command line 模板用 `${CLAWSEAT_ROOT}` 而不是 hard-coded path（sandbox 里 CLAWSEAT_ROOT 是 real HOME 的 ClawSeat 路径）

## Deliverable

`.agent/ops/install-nonint/DELIVERY-PHASE-A-GAPS-055.md`:

```
## 改动清单
- scripts/install.sh (R1 tomli guard + R8.2 detach-on-destroy + R9.1 status line)
- scripts/wait-for-seat.sh (R8.1 loop re-attach)
- core/launchers/agent-launcher.sh (R2 seed 清单扩展 + R5.1 reseed 语义升级)
- core/scripts/agent_admin_session.py (R5.2 start-engineer 调用 reseed + R10.1/R10.2/R10.3 onboarding-aware)
- core/scripts/agent_admin_parser.py (R5.3 reseed-sandbox subcommand)
- core/scripts/agent_admin.py (R5.3 dispatch handler)
- core/scripts/agent_admin_commands.py (R5.3 handler impl)
- core/scripts/agent_admin_switch.py (R3 ark cross-tool)
- core/templates/ancestor-brief.template.md (R4 memory query 强制 + R6.2 send-and-verify 模板 + R10.4 禁止循环 start-engineer)
- core/skills/clawseat-ancestor/SKILL.md (R4 §2 memory_query 列 + R6.1 §9 跨 seat 通讯硬规则 + R6.3 §11 VIOLATION 模板)
- tests/test_install_tomli_guard.py
- tests/test_launcher_seed_user_tool_dirs.py (R2 扩展)
- tests/test_launcher_seed_reseed_existing.py (R5.1)
- tests/test_agent_admin_session_reseed.py (R5.3)
- tests/test_switch_harness_ark_cross_tool.py
- tests/test_ancestor_brief_memory_query_steps.py
- tests/test_ancestor_skill_memory_query_column.py
- tests/test_ancestor_skill_comm_discipline.py (R6.1)
- tests/test_ancestor_brief_no_bare_send_keys.py (R6.2)
- tests/test_launcher_gemini_trust_seed.py (R7.1)
- tests/test_wait_for_seat_trust_detection.py (R7.3)
- tests/test_wait_for_seat_persistent_reattach.py (R8.1 · detach 后 loop 行为)
- tests/test_install_seat_session_detach_on_destroy.py (R8.2)
- tests/test_seat_session_status_line.py (R9.1)
- tests/test_start_engineer_onboarding_detect.py (R10.1)
- tests/test_start_engineer_no_kill_during_onboard.py (R10.2)
- tests/test_ancestor_brief_no_retry_loop.py (R10.4)
- tests/test_ancestor_brief_project_scope_assertion.py (R11.1)
- tests/test_ancestor_skill_window_ops_canonical.py (R11.2)
- tests/test_ancestor_skill_larkcli_diagnostic_gate.py (R11.3)
- tests/test_ancestor_skill_no_manual_symlink.py (R11.4)
- tests/test_ancestor_brief_cookbook_section.py (R12.1)
- tests/test_ancestor_brief_meta_rule.py (R13.2)
- tests/test_ancestor_skill_arch_violation_cli_guess.py (R13.1)

## Verification
<pytest 输出 + R3 调研结论 + R5 smoke（smoke01 sandbox 真实 reseed 试跑）>
```

**不 commit**。
