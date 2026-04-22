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

### B2.5 — Bootstrap machine tenants from memory scan

读 `~/.agents/memory/machine/openclaw.json` 的 `agents` 列表并灌进
`~/.clawseat/machine.toml [openclaw_tenants.*]`：

```bash
python3 core/scripts/bootstrap_machine_tenants.py ~/.agents/memory/
```

成功判据：`list_openclaw_tenants()` 返回非空（若本机装了 OpenClaw）。

失败：记录 `B2.5_BOOTSTRAP_FAILED`，继续（后续 B3.5 如果需要选 agent 会再次提醒；不阻塞）。

### B3 — Verify OpenClaw binding
若 `~/.openclaw/workspace.toml` 存在，读 `project` 字段；
否则 skip 并警告。

### B3.5 — 逐个澄清 + 拉起 engineer seat
for seat in [planner, builder, reviewer, qa, designer]:
1. 向用户交互："${seat} provider? [1] claude-code+minimax (默认) [2] codex [3] gemini [4] 自定义"
2. 写 seat profile 到 `~/.agents/engineers/${seat}/${PROJECT_NAME}/profile.toml`
3. `agent-launcher.sh --headless --engineer ${seat} --project ${PROJECT_NAME}`
4. 如果当前拉起的是 planner seat，跑：
   ```bash
   python3 core/skills/planner/scripts/install_planner_hook.py \
     --workspace ~/.agents/workspaces/${PROJECT_NAME}/planner \
     --clawseat-root ${CLAWSEAT_ROOT}
   ```
5. 等 `tmux has-session -t ${PROJECT_NAME}-${seat}` 活 15s
6. 在六宫格里可见此 pane 已接管（用户目视确认）
7. 下一个

### B5 — Verify Feishu group binding
读 `~/.agents/tasks/${PROJECT_NAME}/PROJECT_BINDING.toml`:
- 若 feishu_group_id 缺 → 向用户 prompt chat_id；若用户 skip 则记录 warn，B6 一并 skip

### B6 — Smoke dispatch
发 `OC_DELEGATION_REPORT_V1` 到 feishu（如已配），否则走 CLI-only smoke（写测试文件、grep ok）。

### B7 — 写 STATUS.md
```text
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
