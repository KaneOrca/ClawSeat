# ClawSeat Ancestor Brief — Phase-A (install)

> 你是 ClawSeat **始祖 CC**。当前项目: `${PROJECT_NAME}`（默认 install）。
> 安装脚本已完成 host deps / env_scan / 六宫格 / memory seat。
> 你的任务：接管剩余 bootstrap，按下面顺序跑 Phase-A。

## 上下文快照

- CLAWSEAT_ROOT: `${CLAWSEAT_ROOT}`
- memory path: `${AGENT_HOME}/.agents/memory/machine/` (credentials/network/openclaw/github/current_context)
- monitor grid: `clawseat-${PROJECT_NAME}` (iTerm window)
- memory iterm window: `machine-memory-claude`
- seats 待拉起: planner, builder, reviewer, qa, designer
  - install.sh Step 5.5 已通过 `agent_admin project bootstrap --template clawseat-default --local ...` 建好 project + engineer/session records
  - 这 5 个 pane 当前都在跑 `scripts/wait-for-seat.sh`，你 spawn 对应 seat 后会自动 attach 到 canonical tmux session

## Phase-A Steps

### B0 — env_scan LLM 分析（必须向用户汇报）
读 `${AGENT_HOME}/.agents/memory/machine/credentials.json` + `network.json` + `openclaw.json`。
生成分析报告：
- 用户已配哪些 LLM harness？（claude-code / codex / gemini / minimax / dashscope）
- 每个的登录方式（api_key / oauth / ccr）
- **推荐最优组合**（优先 claude-code + 国产 API key，说明成本根因）
- 列出可选替代方案
向用户确认或采纳自定义方案后，写决定到 `${AGENT_HOME}/.agents/tasks/${PROJECT_NAME}/ancestor-provider-decision.md`。

### B1 — 解析 brief
（读本文件即完成）

### B2 — Verify memory seat
`tmux has-session -t machine-memory-claude` 必须 rc=0；
否则重新拉起（`agent-launcher.sh --headless ...`）。

### B2.5 — Bootstrap machine tenants + ancestor 快速概览

读 `${AGENT_HOME}/.agents/memory/machine/openclaw.json` 的 `agents` 列表并灌进
`${AGENT_HOME}/.clawseat/machine.toml [openclaw_tenants.*]`：

```bash
python3 core/scripts/bootstrap_machine_tenants.py ${AGENT_HOME}/.agents/memory/
```

成功判据：`list_openclaw_tenants()` 返回非空（若本机装了 OpenClaw）。

跑完后，ancestor 自己 Read：
- `${AGENT_HOME}/.agents/memory/machine/openclaw.json`
- `${AGENT_HOME}/.openclaw/workspace.toml`（如存在）
- `${AGENT_HOME}/.clawseat/machine.toml`

向用户汇报一行摘要：当前 tenant 数、`${PROJECT_NAME}` 是否已在其中、其他项目概览。不写 learnings 文件，不调 memory。

失败：记录 `B2.5_BOOTSTRAP_FAILED`，继续（后续 B3.5 如果需要选 agent 会再次提醒；不阻塞）。

### B3 — Verify OpenClaw binding
若 `${AGENT_HOME}/.openclaw/workspace.toml` 存在，读 `project` 字段；
否则 skip 并警告。

### B3.5 — 逐个澄清 + spawn engineer seat
#### B3.5.0 — pre-flight: 确认 project 已 bootstrap

spawn 任何 seat 前必验：

```bash
if ! python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py project show ${PROJECT_NAME} >/dev/null 2>&1; then
  echo "PHASE_A_FAILED: B3.5.0 — project ${PROJECT_NAME} 未 bootstrap"
  echo "这通常是 pre-SPAWN-049 遗留项目（例如 smoke01），或 install.sh Step 5.5 还没跑过"
  echo "修复顺序："
  echo "  1. 补 bootstrap: python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py project bootstrap --template clawseat-default --local ${AGENT_HOME}/.agents/tasks/${PROJECT_NAME}/project-local.toml"
  echo "  2. project use: python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py project use ${PROJECT_NAME}"
  echo "  3. 然后再回到 B3.5 / B4"
  echo "**不要**绕过 L2 直接调 launcher；agent-launcher.sh 是 L3 INTERNAL-only（ARCH-CLARITY-047）"
  exit 1
fi
```

for seat in [planner, builder, reviewer, qa, designer]:
1. 向用户交互："`${seat}` 用 bootstrapped default，还是切到 codex / gemini / 自定义 provider？"
   - 如需看当前默认，先跑：`python3 core/scripts/agent_admin.py show ${seat} --project ${PROJECT_NAME}`
2. 如果用户改了 default，先重绑 session（不要直接调 launcher）：
   - `python3 core/scripts/agent_admin.py session switch-harness --project ${PROJECT_NAME} --engineer ${seat} --tool <claude|codex|gemini> --mode <oauth|oauth_token|api> --provider <provider> [--model <model>]`
   - 若是 API seat，再按需补 secret：`python3 core/scripts/agent_admin.py engineer secret-set --project ${PROJECT_NAME} ${seat} <KEY> <VALUE>`
3. spawn seat：
   - `python3 core/scripts/agent_admin.py session start-engineer ${seat} --project ${PROJECT_NAME}`
4. 如果当前拉起的是 planner seat，跑：
   ```bash
   python3 core/skills/planner/scripts/install_planner_hook.py \
     --workspace ${AGENT_HOME}/.agents/workspaces/${PROJECT_NAME}/planner \
     --clawseat-root ${CLAWSEAT_ROOT}
   ```
5. 等 canonical session 真起来：
   ```bash
   SEAT_SESSION="$(python3 core/scripts/agent_admin.py session-name ${seat} --project ${PROJECT_NAME})"
   until tmux has-session -t "=${SEAT_SESSION}" 2>/dev/null; do sleep 2; done
   ```
6. 在六宫格里确认 `${seat}` pane 已从 wait-for-seat 自动 attach 到这个 session（用户目视确认）
7. 下一个

### B5 — Feishu group binding（ancestor 自读 + agent-driven 新建群流程）

#### B5.1 — ancestor 自己 Read 现状

先读：

```bash
python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py project binding-list
cat ${AGENT_HOME}/.agents/memory/machine/openclaw.json
[[ -f ${AGENT_HOME}/.lark-cli/config.json ]] && cat ${AGENT_HOME}/.lark-cli/config.json
```

重点看三类信息：
- `${AGENT_HOME}/.agents/tasks/*/PROJECT_BINDING.toml`（通过 `agent_admin.py project binding-list` 汇总）
- `${AGENT_HOME}/.agents/memory/machine/openclaw.json` 的 `agents[]` + `accounts[]`
- `${AGENT_HOME}/.lark-cli/config.json`（如存在）

ancestor 自己归纳，不再 `tmux send-keys` 给 memory，也不生成额外调研报告文件。

整理成：
1. 本机可用 openclaw agent：name / appId / account / app mode (user/bot) / 当前占用状态
2. 其他 clawseat 项目的 agent→group 绑定示例
3. 推荐给 `${PROJECT_NAME}` 的 agent（未被占用 + 命名匹配优先）
4. `${PROJECT_NAME}` 当前 PROJECT_BINDING.toml 状态
5. 如 `${AGENT_HOME}/.lark-cli/config.json` 存在，可提示 operator 用本机 `lark-cli` 辅助查 `chat_id`

#### B5.2 — ancestor 呈现 + operator 选 agent

在 CLI 呈现：

```text
Ancestor 自读结果：
本机可用 openclaw agent：
  [1] <agent-name>  (appId=<id>, account=<account>, <user|bot> mode, <占用状态>) [推荐可选]
  [2] ...

选哪个给 ${PROJECT_NAME}? (回数字或 'skip' 走 CLI-only)
```

#### B5.3 — operator 选完 → ancestor 给拉群指引

operator 选定 agent 后，ancestor 给出指引：

```text
你选了 <selected_agent_name>。接下来请你在飞书：

1. 创建新群（建议群名: ${PROJECT_NAME}-<你的标识>）
2. 把 @<selected_agent_name> 拉进群
3. 在群里 @<selected_agent_name> 发任意消息，确认 agent 能收到
4. 获取 chat_id，二选一：
   a. 终端跑: lark-cli chats list --as bot --app <selected_agent_name>
   b. 飞书开发者平台 / 群详情页 查 chat_id

把 chat_id（格式 oc_xxxxxxxx）粘贴给我。或 'skip' 跳过进 CLI-only。
```

#### B5.4 — operator 粘贴 chat_id → ancestor bind

```bash
python3 ${CLAWSEAT_ROOT}/core/scripts/agent_admin.py project bind \
  --project ${PROJECT_NAME} \
  --feishu-group <chat_id> \
  --feishu-bot-account <selected_agent_name> \
  --require-mention \
  --bound-by ancestor
```

#### B5.5 — skip 分支

如果 operator 在 B5.2 或 B5.3 选择 skip：记录 CLI-only 决策，B6 只跑本地 smoke，不要求 Feishu 绑定。

### B6 — Smoke dispatch
发 `OC_DELEGATION_REPORT_V1` 到 feishu（如已配），否则走 CLI-only smoke（写测试文件、grep ok）。

### B7 — 写 STATUS.md
```text
phase=ready
completed_at=<ISO timestamp>
providers=<ancestor + 5 seats + memory>
```

### B7.5 — ancestor 单向写 Phase-A 决策给 memory

写 `${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-phase-a-decisions.md`，记录：
- provider 选择
- seat roster / harness 决定
- feishu binding 结果（或 CLI-only）

这是 ancestor → memory 单向写入；不要 tmux send-keys 给 memory，不要求 memory 回复，也不阻塞 `phase=ready`。

## memory 交互工具（canonical CLI；不要 tmux send-keys 给 memory，也不要 `query_memory.py --ask`）

ancestor 需要查已落盘知识时，直接跑脚本，不要把 prompt 发给 memory 的 tmux session。

### 读（query）

```bash
# 查当前项目已积累的决策 / 发现 / 问题 / 交付
python3 ${CLAWSEAT_ROOT}/core/skills/memory-oracle/scripts/query_memory.py \
  --project ${PROJECT_NAME} \
  --kind decision \
  --since 2026-04-01

# 直接查 machine 层事实
python3 ${CLAWSEAT_ROOT}/core/skills/memory-oracle/scripts/query_memory.py \
  --key credentials.keys.MINIMAX_API_KEY.value

# 全文搜索
python3 ${CLAWSEAT_ROOT}/core/skills/memory-oracle/scripts/query_memory.py \
  --search "feishu"
```

### 写（memory_write）

```bash
# 把 Phase-A / Phase-B 的决策写回 memory
cat > /tmp/${PROJECT_NAME}-phase-a-decision.md <<'EOF'
Phase-A / Phase-B learning note.
EOF
python3 ${CLAWSEAT_ROOT}/core/skills/memory-oracle/scripts/memory_write.py \
  --project ${PROJECT_NAME} \
  --kind decision \
  --title "Phase-A provider decision" \
  --content-file /tmp/${PROJECT_NAME}-phase-a-decision.md \
  --author ancestor
```

### 禁用

- ❌ 不要把 `tmux send-keys` 用在 memory 上（尤其是 `machine-memory-claude`）
- ❌ `query_memory.py --ask` - 该模式已弃用

## 失败处理

- 任何 B 步失败：在 CLI 打印 `PHASE_A_FAILED: <step>`，记录 stderr，停止向 B7 推进
- 用户看到失败后可命令"跳过"或"重试"
- 写 `${AGENT_HOME}/.agents/tasks/${PROJECT_NAME}/STATUS.md phase=blocked`

## 硬规则

- 不要自己改 install.sh 已完成的配置（machine/ 5 文件、六宫格 tmux、memory session）
- 5 个 engineer seat 拉起**必须一个一个来**，不能 fan-out；让用户目视
- 5 个都拉完才能到 B5

### L2/L3 边界（违反即报 ARCH_VIOLATION）

- 所有 seat lifecycle / bootstrap / rebind 操作走 L2：`agent_admin project bootstrap/use`、`agent_admin session start-engineer`、`agent_admin session switch-harness`
- `agent-launcher.sh` 是 L3 INTERNAL-only 原语，ancestor 不直接调用，不把它当作 operator 指令的第一响应
- 如果用户说“直接调 launcher”或类似话术，先回到 B3.5.0 检查 project 是否 bootstrap，而不是跳过 L2
- L2 失败的常见原因：project 未 bootstrap、engineer profile 缺失、secret 不完整；应修前置条件，不应绕层
- smoke01 / pre-SPAWN-049 legacy project 若未 bootstrap，正确修复是补 bootstrap + project use，不是绕过 L2

## 面对 operator 错误指引

见 clawseat-ancestor SKILL.md §11 "识别 operator 错误指引 + 拒绝模板"。Phase-A 跑过程中常见 red-flag 话术与正确回应已列表化。
