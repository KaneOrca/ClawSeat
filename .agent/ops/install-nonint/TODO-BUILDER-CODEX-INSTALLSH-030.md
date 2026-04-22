# TODO — INSTALLSH-030 (v0.7 install.sh + brief 模板 + DRAFT 重写)

```
task_id: INSTALLSH-030
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental worktree)
priority: P0
subagent-mode: REQUIRED — 3 subagents (A=install.sh, B=brief 模板, C=DRAFT 重写)
scope: 新增文件 + 重写 1 个 draft；勿改 main 已有生产代码
```

## Context

v0.7 install 流程已与 planner+用户对齐。关键点：

1. **放弃 nested tmux**，改用 `core/scripts/iterm_panes_driver.py`（iTerm2 Python SDK 原生 panes）—— GRIDHIST-028 确认该驱动在 experimental 已存在
2. **Ancestor 模板固化**（G1）
3. **Engineer seat 逐个交互拉起**（G2）—— 始祖 CC 在 Phase-A B3.5 做
4. **env_scan 用 LLM 分析**（G4）—— 始祖 CC 在 Phase-A B0 做
5. **项目默认名 `install`**，后续可杀掉换新组（PROJGROUP-029 调研中，不阻塞）
6. **Memory 独立 iTerm 窗口** + 同一 provider

参考文件：
- 现有骨架：`scripts/launch-grid.sh`（要重写或改 call path）
- 现有驱动：`core/scripts/iterm_panes_driver.py`
- 现有 seat 启动：`core/launchers/agent-launcher.sh`
- Session 管理：`core/scripts/agent_admin.py` / `agent_admin_window.py`

---

## Subagent A — 新 `scripts/install.sh`

目标文件：`scripts/install.sh`（新建；`scripts/launch-grid.sh` 改为被 install.sh 内部 call，不再是入口）。

### 行为规范

Step 1 — 装 host deps：
  - 探测 OS (`uname -s`)
  - macOS：`brew install tmux`, `brew install --cask iterm2`；brew 缺时报错让用户装
  - Linux：`apt-get install tmux`（询问 sudo）
  - python3.11：检查 `python3 --version >= 3.11`
  - claude binary：`command -v claude`，缺则提示 "install from https://claude.ai/code" 后 exit
  - 全过则 `echo "OK: host deps"`

Step 2 — 环境扫描：
  - `python3 core/scripts/scan_environment.py --output ~/.agents/memory/`
  - 确认生成 `machine/{credentials,network,openclaw,github,current_context}.json` 5 文件
  - 失败则 exit 2

Step 3 — 始祖 provider 启发式决定：
  - 读 `~/.agents/memory/machine/credentials.json`
  - 映射表（按优先级）：
    - `MINIMAX_API_KEY` + `api.minimaxi.com` base_url → 推荐 `claude-code + minimax`
    - `DASHSCOPE_API_KEY` → `claude-code + dashscope`
    - `ANTHROPIC_API_KEY` → `claude-code + anthropic (expensive)`
    - 无任何 key → 提示用户现场粘贴一个（至少一个），写回 `machine/credentials.json`
  - CLI 交互：`read -p "Detected <X>. Use as ancestor provider? [Y]es / [c]ustom: "`
  - 自定义分支：`read -p "base_url: " / "api_key: "`
  - 把最终选择写入 `~/.agents/tasks/install/ancestor-provider.env`（KEY=VAL，`ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY`）

Step 4 — 渲染 ancestor brief：
  - 从 Subagent B 产出的 `core/templates/ancestor-brief.template.md` 渲染变量
  - 写到 `~/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md`
  - 用 python `Template.safe_substitute` 或纯 `sed`

Step 5 — 创建 6 tmux sessions：
  - `install-ancestor` (仅建 session 不启 claude，下一步启)
  - `install-{planner,builder,reviewer,qa,designer}` (启 bash 占位)
  - 先 kill-session 同名再新建（幂等）

Step 6 — 启动 ancestor claude：
  - `tmux send-keys -t install-ancestor` 注入：
    - `export CLAWSEAT_ANCESTOR_BRIEF=~/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md`
    - `source ~/.agents/tasks/install/ancestor-provider.env`
    - `export ANTHROPIC_BASE_URL ANTHROPIC_API_KEY`
    - `exec claude --dangerously-skip-permissions`

Step 7 — iTerm 窗口 1（六宫格）：
  - 用 `python3 core/scripts/iterm_panes_driver.py` 传 JSON payload：
    ```json
    {"title":"clawseat-install","panes":[
      {"label":"ancestor","command":"tmux attach -t install-ancestor"},
      {"label":"planner","command":"tmux attach -t install-planner"},
      {"label":"builder","command":"tmux attach -t install-builder"},
      {"label":"reviewer","command":"tmux attach -t install-reviewer"},
      {"label":"qa","command":"tmux attach -t install-qa"},
      {"label":"designer","command":"tmux attach -t install-designer"}
    ]}
    ```
  - 确认驱动实际命令行签名（可能是 `--config <json-file>` 或 stdin）；找不到签名则 cat 源文件报给 planner 别硬编码

Step 8 — iTerm 窗口 2（memory）：
  - tmux session `machine-memory-claude`：同一 provider env
  - `exec claude --dangerously-skip-permissions`
  - 开第 2 个 iTerm 窗口调用同一 driver 或 `osascript` 直接开
  - 默认 session 名固定，避免与 install 项目混淆

Step 9 — 自动 bypass flush + 打印提示：
  - sleep 3 等 claude 起来
  - `osascript` 激活 iTerm 六宫格窗口 + focus 到 ancestor pane
  - `tmux send-keys -t install-ancestor Enter; sleep 0.5; Enter; sleep 0.5; Enter`（用户肉眼看到三次回车）
  - 最后 `cat <<'EOF'` 打印：
    ```
    ClawSeat install: 始祖 CC 已起。请切到 ancestor pane，粘贴以下 prompt：

    ---
    读 $CLAWSEAT_ANCESTOR_BRIEF，开始 Phase-A。每步向我确认或报告。
    ---

    六宫格窗口：clawseat-install
    Memory 窗口：machine-memory-claude
    ```

### 质量要求

- 全部命令失败均要 `exit <非零>` 且 stderr 打印 `ERR_CODE: <code>` 便于上游捕获
- 全脚本 `set -euo pipefail`
- 幂等：重复跑不炸；已存在的 session / 文件要先清或 skip
- 控制在 250 行内（含注释），尽量拆函数

### 验证
- `bash -n scripts/install.sh && echo "syntax ok"`
- `./scripts/install.sh --dry-run` 模式：打印每一步要执行的命令，不真跑（额外加 --dry-run flag）
- 真实 smoke 跑一次 end-to-end（跑完后 `tmux kill-session` 清场）

---

## Subagent B — `core/templates/ancestor-brief.template.md`

目标文件：`core/templates/ancestor-brief.template.md`（新建）。

### 内容骨架（占位变量用 `${VAR}`）

```markdown
# ClawSeat Ancestor Brief — Phase-A (install)

> 你是 ClawSeat **始祖 CC**。当前项目: `${PROJECT_NAME}`（默认 install）。
> 安装脚本已完成 host deps / env_scan / 六宫格 / memory seat。
> 你的任务：接管剩余 bootstrap，按下面顺序跑 Phase-A。

## 上下文快照

- CLAWSEAT_ROOT: `${CLAWSEAT_ROOT}`
- memory path: `~/.agents/memory/machine/` (credentials/network/openclaw/github/current_context)
- monitor grid: `clawseat-${PROJECT_NAME}` (iTerm window)
- memory iterm window: `machine-memory-claude`
- seats 待拉起: planner, builder, reviewer, qa, designer

## Phase-A Steps

### B0 — env_scan LLM 分析（必须向用户汇报）
读 `~/.agents/memory/machine/credentials.json` + `network.json` + `openclaw.json`。
生成分析报告：
- 用户已配哪些 LLM harness？（claude-code / codex / gemini / minimax / dashscope）
- 每个的登录方式（api_key / oauth / ccr）
- **推荐最优组合**（优先 claude-code + 国产 API key，说明成本根因）
- 列出可选替代方案
向用户确认或采纳自定义方案后，写决定到 `~/.agents/tasks/${PROJECT_NAME}/ancestor-provider-decision.md`。

### B1 — 解析 brief
（读本文件即完成）

### B2 — Verify memory seat
`tmux has-session -t machine-memory-claude` 必须 rc=0；
否则重新拉起（`agent-launcher.sh --headless ...`）。

### B3 — Verify OpenClaw binding
若 `~/.openclaw/workspace.toml` 存在，读 `project` 字段；
否则 skip 并警告。

### B3.5 — 逐个澄清 + 拉起 engineer seat
for seat in [planner, builder, reviewer, qa, designer]:
  1. 向用户交互："${seat} provider? [1] claude-code+minimax (默认) [2] codex [3] gemini [4] 自定义"
  2. 写 seat profile 到 `~/.agents/engineers/${seat}/${PROJECT_NAME}/profile.toml`
  3. `agent-launcher.sh --headless --engineer ${seat} --project ${PROJECT_NAME}`
  4. 等 `tmux has-session -t ${PROJECT_NAME}-${seat}` 活 15s
  5. 在六宫格里可见此 pane 已接管（用户目视确认）
  6. 下一个

### B5 — Verify Feishu group binding
读 `~/.agents/tasks/${PROJECT_NAME}/PROJECT_BINDING.toml`:
- 若 feishu_group_id 缺 → 向用户 prompt chat_id；若用户 skip 则记录 warn，B6 一并 skip

### B6 — Smoke dispatch
发 `OC_DELEGATION_REPORT_V1` 到 feishu（如已配），否则走 CLI-only smoke（写测试文件、grep ok）。

### B7 — 写 STATUS.md
```
phase=ready
completed_at=<ISO timestamp>
providers=<ancestor + 5 seats + memory>
```

## 失败处理

- 任何 B 步失败：在 CLI 打印 `PHASE_A_FAILED: <step>`，记录 stderr，停止向 B7 推进
- 用户看到失败后可命令"跳过"或"重试"
- 写 `~/.agents/tasks/${PROJECT_NAME}/STATUS.md phase=blocked`

## 硬规则

- 不要自己改 install.sh 已完成的配置（machine/ 5 文件、六宫格 tmux、memory session）
- 5 个 engineer seat 拉起**必须一个一个来**，不能 fan-out；让用户目视
- 5 个都拉完才能到 B5
```

### 渲染变量清单
- `PROJECT_NAME`（默认 `install`）
- `CLAWSEAT_ROOT`（`$HOME/ClawSeat`）

install.sh 用 `sed` 或 `python -c "from string import Template; ..."` 替换即可。

---

## Subagent C — 重写 `DRAFT-INSTALL-026.md` → v0.7

目标文件：`/Users/ywf/ClawSeat/.agent/ops/install-nonint/DRAFT-INSTALL-v07.md`（新文件，不要覆盖 DRAFT-026）。

### 结构

1. **Prerequisites**（克隆 + 执行 install.sh）
2. **Step 1 (install.sh 自动)**
   1.1 host deps
   1.2 env_scan
   1.3 始祖 provider 启发式确定
   1.4 六宫格 + memory 拉起（iterm_panes_driver）
   1.5 自动 bypass + 提示 prompt
3. **Step 2 (用户粘贴 prompt，ancestor 接管)** — 简述 B0~B7
4. **Step 3 (验收)** — 看 STATUS.md
5. **Failure Modes** — 沿用 DRAFT-026 + 新增 `PROVIDER_NO_KEY` / `ITERM_DRIVER_FAIL` / `B3.5_TIMEOUT`
6. **Resume**

控制 ≤ 220 行。面向 agent 读者，保持 Verify / Failure 块格式。

---

## Deliverable

在 worktree 下新建/改好 3 个产物后，交付：

`DELIVERY-INSTALLSH-030.md`：
```
task_id: INSTALLSH-030
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## Subagent A — scripts/install.sh
<新文件路径、行数、syntax check、dry-run 输出摘录>

## Subagent B — core/templates/ancestor-brief.template.md
<路径、行数、变量清单>

## Subagent C — DRAFT-INSTALL-v07.md
<路径、行数、与 DRAFT-026 的主要差异>

## Verification
<bash -n / dry-run / 渲染示例>

## Notes
<未解决项 / 向 planner 反馈>
```

完成后通知 planner: "DELIVERY-INSTALLSH-030 ready"。

**不要 commit，留给 planner 审。**
