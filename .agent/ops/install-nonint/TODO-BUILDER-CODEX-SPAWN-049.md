# TODO — SPAWN-049 (install.sh 只起 ancestor + memory；其他 5 seat 由 ancestor 按需 spawn)

```
task_id: SPAWN-049
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: REQUIRED — 2 subagents (A=install.sh + wait-for-seat 改造, B=ancestor brief + project bootstrap 接线)
scope: 把 v0.7 install.sh 从"一次性起 6 seat"改成"只起 ancestor + memory；其他 5 seat 等 ancestor 决策后逐个 spawn"
```

## Context

ISOLATION-046/047/048 已让 L1→L3 + L2→L3 收敛、Pyramid 落地、auth conflict 也修了（commit `43ec29a`）。
LIVE-047 minimax 极简跑通，但暴露 v0.7 真正的设计缺陷：

**install.sh 当前**（行 332-339）一次性 launch 6 seat：
```bash
for seat in ancestor planner builder reviewer qa designer; do
  launch_seat "$PROJECT-$seat" "$REPO_ROOT" ...
done
```

但 **ancestor brief B3.5** 里又写"逐个澄清 + 拉起 engineer seat" —— 语义打架：seat 已经在 install.sh
里被 fan-out 起来了（空 claude TUI，无人对话），ancestor 再"拉起"是无意义动作；况且 B3.5 用的是
`agent-launcher.sh --engineer ${seat}` 这个 launcher 根本没实现的 flag。

用户决策：**install.sh 只起 ancestor + memory**；六宫格保留作为 UX 占位；其他 5 pane 跑 wait-for-seat
loop，等到 ancestor 调 `agent_admin session start-engineer <seat>` 后自动 attach。

## Subagent A — install.sh + wait-for-seat 改造

### A1 调研

1. 读 `agent_admin_crud.py:213` `project_bootstrap()`：参数 `--template <name>` + `--local <toml>`
2. 读 `core/templates/ancestor-engineer.toml` + `core/templates/shared/`：现有 engineer template 结构
3. 检查 `~/.agents/templates/` 是否存在（**当前不存在**），install.sh 要负责放 template
4. 看 `iterm_panes_driver.py` 怎么解析 `panes[].command`：每 pane 跑一个 shell command；当前 ancestor 用 `tmux attach -t ...`，其他 seat 也是 attach（注定失败）

### A2 实施

#### 改 1：`scripts/install.sh` Step 5 缩到只起 ancestor

```bash
note "Step 5: launch ancestor seat via agent-launcher"
launch_seat "$PROJECT-ancestor" "$REPO_ROOT" "$BRIEF_PATH"
```

删掉 for 循环，删 planner/builder/reviewer/qa/designer 的 launch。

#### 改 2：`scripts/install.sh` 新 Step 5.5 — bootstrap project profile（不 start tmux）

```bash
bootstrap_project_profile() {
  note "Step 5.5: bootstrap project engineer profiles (no tmux start)"
  # 1. 确保 ~/.agents/templates/clawseat-default.toml 存在
  # 2. 写 ~/.agents/tasks/$PROJECT/project-local.toml（含 project_name / repo_root / provider 默认）
  # 3. 调 agent_admin project bootstrap --template clawseat-default --local <local.toml>
  #    （这会建 6 个 engineer profile + project record，不启 tmux session）
}
```

需要新建 **`templates/clawseat-default.toml`** —— 6 engineer roster template。所有 engineer 默认
`tool=claude / auth_mode=api / provider=<install.sh 选的 mode>` —— ancestor 后续可调
`agent_admin engineer rebind` 切 reviewer→codex / designer→gemini。

template 内容参考 `core/templates/ancestor-engineer.toml`（其结构是 SSOT）。如果 template 字段需要扩
展（`engineers[]` list），加上来。

#### 改 3：`scripts/install.sh` Step 7 六宫格 pane commands

```bash
grid_payload() {
  printf '{"title":"clawseat-%s","panes":[' "$PROJECT"
  printf '{"label":"ancestor","command":"tmux attach -t %s-ancestor"},' "$PROJECT"
  for seat in planner builder reviewer qa designer; do
    printf '{"label":"%s","command":"bash %s/scripts/wait-for-seat.sh %s-%s"}' \
      "$seat" "$REPO_ROOT" "$PROJECT" "$seat"
    [[ "$seat" != "designer" ]] && printf ','
  done
  printf ']}\n'
}
```

注意 JSON 转义；如果 iterm_panes_driver.py 不能处理这种 nested 转义，可能要改用 jq 生成。

#### 改 4：`scripts/install.sh` 加 `--provider <mode>` flag

```bash
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1; shift ;;
      --project) PROJECT="$2"; shift 2 ;;
      --provider) FORCE_PROVIDER="$2"; shift 2 ;;
      --help|-h) ... ;;
      *) ...
    esac
  done
}
```

`select_provider()` 开头：

```bash
if [[ -n "$FORCE_PROVIDER" ]]; then
  # 在 candidates 里找第一个 mode 匹配的
  for c in "${candidates[@]}"; do
    IFS=$'\t' read -r mode label key base <<<"$c"
    if [[ "$mode" == "$FORCE_PROVIDER" ]]; then
      ... # remember + write_provider_env + return
    fi
  done
  die 22 PROVIDER_NOT_FOUND "--provider $FORCE_PROVIDER not detected on this host"
fi
```

支持的值：`minimax / custom_api / anthropic_console / oauth_token / oauth`（与 detect_provider emit 的 mode 一致）。

#### 改 4b：`scripts/install.sh` 加 `--base-url <url>` + `--api-key <key>` 显式 custom（追加 patch）

**用例**：用户没在 env 里 export，又不想交互输入；agent 自动化场景必需。

```bash
parse_args() {
  ...
    case "$1" in
      ...
      --base-url) FORCE_BASE_URL="$2"; shift 2 ;;
      --api-key) FORCE_API_KEY="$2"; shift 2 ;;
      --model) FORCE_MODEL="$2"; shift 2 ;;
      ...
    esac
  ...
  # 互斥校验
  if [[ -n "$FORCE_BASE_URL$FORCE_API_KEY" ]]; then
    [[ -n "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]] || die 2 INVALID_FLAGS "--base-url 必须和 --api-key 成对"
    [[ -n "$FORCE_PROVIDER" && "$FORCE_PROVIDER" != "custom_api" ]] && die 2 INVALID_FLAGS "--base-url/--api-key 只能配 --provider custom_api 或不传 --provider"
  fi
}
```

`select_provider()` 顶部，**优先于 `--provider` 短路**：

```bash
if [[ -n "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]]; then
  remember_provider_selection custom_api "$FORCE_API_KEY" "$FORCE_BASE_URL" "$FORCE_MODEL"
  write_provider_env custom_api "$FORCE_API_KEY" "$FORCE_BASE_URL"
  printf 'Using: explicit custom API (base_url=%s)\n' "$FORCE_BASE_URL"
  return
fi
```

**安全提示**：`--api-key` 在 ps / shell history 里明文。docs/INSTALL.md 加一段："agent 自动化推荐 `export ANTHROPIC_BASE_URL=... ANTHROPIC_API_KEY=...; bash install.sh --provider custom_api`，避免 key 上命令行。`--base-url + --api-key` 用于 CI 等不能 export 的场景。"

测试加：
- 验证 `--base-url X --api-key Y --project foo` 完全跳过 detect_provider + select_provider 交互，写出 PROVIDER_ENV 内容含 X / Y
- 验证 `--base-url X` 单传报 INVALID_FLAGS
- 验证 `--provider minimax --base-url X` 报 INVALID_FLAGS

#### 改 4c：`--provider <mode>` 自动补齐 default base_url / model（LIVE-047 反馈）

minimax 报告：`--provider minimax` 单独用不够，机器没预置 minimax env 时 detect 不 emit candidate → die PROVIDER_NOT_FOUND。用户期望 `--provider minimax --api-key sk-cp-...` 直接可用（不需要机器预置）。

在 `select_provider` 顶部（FORCE_BASE_URL 短路之前）加：

```bash
# --provider <known mode> 的 default 值补齐（便利用法：只传 --provider + --api-key）
if [[ -n "$FORCE_PROVIDER" && -z "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]]; then
  case "$FORCE_PROVIDER" in
    minimax)
      FORCE_BASE_URL="https://api.minimaxi.com/anthropic"
      [[ -z "$FORCE_MODEL" ]] && FORCE_MODEL="MiniMax-M2.7-highspeed"
      ;;
    anthropic_console)
      # anthropic-console 走 ANTHROPIC_API_KEY，不 fall through 到 custom 短路
      remember_provider_selection anthropic_console "$FORCE_API_KEY"
      write_provider_env anthropic_console "$FORCE_API_KEY"
      return
      ;;
  esac
fi
```

测试加：
- `--provider minimax --api-key sk-cp-... --project foo` → 自动填 minimax base_url + model，无交互
- `--provider anthropic_console --api-key sk-ant-... --project foo` → 走 anthropic_console 分支

#### 改 4d：修 brief 路径在 sandbox HOME 下解析错（LIVE-047 真 bug）

minimax B0 报告："brief 写 `~/.agents/memory/machine/`，但 ancestor seat 自己搜到 `~/.agents/machine/`（少 memory 层）"。

**根因**：brief template 用 `~/` 前缀；ancestor seat 的 `$HOME` 是 sandbox HOME (`~/.agent-runtime/identities/claude/api/custom-<session>/home/`)，所以 ancestor 执行 `ls ~/.agents/memory/...` 解析到不存在的 sandbox path。

launcher 已经 export `AGENT_HOME="$REAL_HOME"`（`agent-launcher.sh` 行 1026），但 brief template 没用这个 var。

**修复**：

**1. `core/templates/ancestor-brief.template.md`**：把所有 `~/` 换成 `${AGENT_HOME}/`，或者 render 时用真实 absolute path 直接填。

可选方案 A（推荐，稳定）：render 时 substitute，brief 里直接是 `/Users/ywf/.agents/memory/...` absolute path。不依赖 ancestor shell 会不会 expand。

**2. `scripts/install.sh` `render_brief()`**：传 AGENT_HOME 到 Template。

```bash
render_brief() {
  ...
  "$PYTHON_BIN" - "$TEMPLATE_PATH" "$BRIEF_PATH" "$PROJECT" "$REPO_ROOT" "$REAL_HOME" <<'PY'
from pathlib import Path
from string import Template
import sys
template_path, out_path, project, clawseat_root, agent_home = sys.argv[1:6]
out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(Template(Path(template_path).read_text(encoding="utf-8")).safe_substitute(
    PROJECT_NAME=project, CLAWSEAT_ROOT=clawseat_root, AGENT_HOME=agent_home
), encoding="utf-8")
PY
  ...
}
```

然后 brief template 里把所有 `~/.agents/...` / `~/.openclaw/...` / `~/.clawseat/...` 改成 `${AGENT_HOME}/.agents/...` 等。

列表（brief 当前 `~/` 出现位置）：
- `memory path: ~/.agents/memory/machine/` → `${AGENT_HOME}/.agents/memory/machine/`
- `~/.agents/memory/machine/credentials.json` (B0)
- `~/.agents/tasks/${PROJECT_NAME}/ancestor-provider-decision.md` (B0)
- `~/.agents/memory/machine/openclaw.json` (B2.5)
- `~/.clawseat/machine.toml` (B2.5)
- `~/.openclaw/workspace.toml` (B3)
- `~/.agents/workspaces/${PROJECT_NAME}/planner` (B3.5)
- `~/.agents/tasks/${PROJECT_NAME}/PROJECT_BINDING.toml` (B5)

测试加：
- render_brief 测试：生成 brief 后 grep `'~/'` 应为 0；grep `'/Users/ywf/.agents/memory'`（或 substituted AGENT_HOME）应 >0
- 端到端：ancestor seat 启动后在 sandbox HOME 下 `cat <brief>` 看到的全是 absolute path，不含 `~`

#### 改 4e：`wait-for-seat.sh` 必须 prefix-match（Phase-A walk-through 发现）

**问题**：install.sh grid pane 写死 `wait-for-seat.sh cartooner-planner`（按 seat 名），但 agent_admin `session_name_for()` 返回 `cartooner-planner-claude`（带 tool 后缀）。六宫格 pane 永远等不到 session。**所有 5 个非 ancestor pane 全中招**。

**修复** `scripts/wait-for-seat.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail
SESSION="${1:?usage: wait-for-seat.sh <session-prefix>}"
printf 'pane is waiting for %s (or %s-<tool>) ...\n' "$SESSION" "$SESSION"
printf '(seat will appear here once ancestor spawns it)\n'
while true; do
  # 先匹配 exact 名（历史兼容），再匹配 prefix + tool 后缀
  for candidate in "$SESSION" "${SESSION}-claude" "${SESSION}-codex" "${SESSION}-gemini"; do
    if tmux has-session -t "=$candidate" 2>/dev/null; then
      exec tmux attach -t "=$candidate"
    fi
  done
  sleep 5
done
```

测试加：
- mock tmux session `cartooner-planner-claude` 出现后，wait-for-seat.sh `cartooner-planner` 能 exec attach
- 同理 `-codex` / `-gemini` 后缀
- 纯 `cartooner-planner`（无后缀）也能 attach（向后兼容）

#### 改 4f：B2.6 新增 — ancestor 让 memory 做 openclaw 生态调研（Phase-A walk-through 发现）

**问题**：B2.5 的 `bootstrap_machine_tenants.py` 是 dumb Python pipe（只拷 agents list 到 machine.toml）。memory seat 已经在线（独立 claude TUI），但 ancestor 没让它做 LLM 级调研 —— 浪费了 memory 的 LLM 能力。

**修复**：在 `core/templates/ancestor-brief.template.md` B2.5 之后加 B2.6：

```markdown
### B2.6 — 让 memory seat 生成 openclaw 生态报告

向 memory seat 发调研请求（通过 tmux send-keys 到 machine-memory-claude pane）：

```bash
MEMORY_PROMPT="请帮我调研 ${PROJECT_NAME} 项目在 openclaw 生态的当前状态。

读以下文件：
- ${AGENT_HOME}/.agents/memory/machine/openclaw.json
- ${AGENT_HOME}/.openclaw/openclaw.json (如存在)
- ${AGENT_HOME}/.openclaw/workspace.toml (如存在)
- ${AGENT_HOME}/.clawseat/machine.toml

生成 markdown 报告到 ${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-bootstrap-report.md，含：
1. ${PROJECT_NAME} 在 openclaw 里占哪些 tenant / agent（名字 + 职责）
2. 已绑定的 skill / plugin / extension
3. feishu group binding 当前状态（绑定 / 未绑定 / 需要补）
4. 这台机器上其他 clawseat 项目（cartooner 不是唯一项目的话）
5. 建议 Phase-A 接下来的注意事项

完成后说 'MEMORY_REPORT_READY: <path>'，不要继续做其他事。"

tmux send-keys -t '=machine-memory-claude' "$MEMORY_PROMPT" Enter

# 等 memory 完成（轮询 learnings 文件 + 'MEMORY_REPORT_READY' 信号）
REPORT_PATH="${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-bootstrap-report.md"
for i in {1..60}; do  # 最多 10 分钟
  [[ -f "$REPORT_PATH" ]] && grep -q "MEMORY_REPORT_READY" <(tmux capture-pane -t '=machine-memory-claude' -p -S -20) && break
  sleep 10
done

# ancestor 读报告后带进上下文，供 B3 / B3.5 决策使用
cat "$REPORT_PATH"
```
```

**如果 memory 超时或失败**：ancestor 降级为自己读 openclaw.json（不阻塞 Phase-A），在 STATUS.md 记 `B2.6_FALLBACK_SELF_READ`。

不动 B2.5（bootstrap_machine_tenants.py 仍然跑，是 data pipe）。B2.6 是 LLM 层的叠加。

#### 改 4g：install.sh Step 9 结束 prompt 引导加强（LIVE-047 反馈）

**问题**：minimax 报"安装结束没给发给始祖的 prompt"。Step 9 的 heredoc 输出 prompt，但：
1. 可能被前面 Step 7 / Step 8 失败 exit 40 吃掉（没到 Step 9）
2. 可能被 iTerm 打开新窗口后终端被切走，operator 看不到
3. 没引导 operator 第一句话该说什么

**修复** `scripts/install.sh` main() 尾部：

```bash
# 把引导 prompt 写成文件（确保不被终端切走吃掉）
GUIDE_FILE="$AGENT_HOME/.agents/tasks/$PROJECT/OPERATOR-START-HERE.md"
cat > "$GUIDE_FILE" <<EOF
# Operator — ClawSeat $PROJECT 启动指引

install.sh 已完成。现在做 3 件事：

1. 切到 iTerm 窗口 "clawseat-$PROJECT" 的 ancestor pane（左上角第一格）
2. 在 ancestor pane 粘贴以下 prompt（ctrl+V 或 cmd+V）：

---
读 \$CLAWSEAT_ANCESTOR_BRIEF 开始 Phase-A。

第一步：让 memory 做 openclaw 生态调研（brief B2.6）。发 prompt 给 machine-memory-claude session，等报告。然后逐步走 B3 / B3.5 / B5 / B6 / B7，每步向我确认。

用 agent_admin.py session start-engineer 逐个拉起 seat（不要 fan-out，一个一个来）。
---

3. 每走完一步向 ancestor 说"继续"或给修正（provider / chat_id 等）
EOF

# 终端输出明显分隔
printf '\n'
printf '╔════════════════════════════════════════════════════════════════╗\n'
printf '║  ClawSeat install complete                                       ║\n'
printf '║                                                                  ║\n'
printf '║  NEXT STEPS: cat %-47s ║\n' "$GUIDE_FILE"
printf '║                                                                  ║\n'
printf '║  Or read the file at: %-42s ║\n' "$GUIDE_FILE"
printf '╚════════════════════════════════════════════════════════════════╝\n'
printf '\n'
```

测试加：
- install.sh 跑完必须写 `$AGENT_HOME/.agents/tasks/$PROJECT/OPERATOR-START-HERE.md`
- 文件含 `agent_admin.py session start-engineer` 关键字
- 终端 stdout 含 "ClawSeat install complete" banner

#### 改 4h：B5 feishu binding 调研也交给 memory（Phase-A walk-through 发现）

**问题**：B5 原设计是 ancestor 自己读 `PROJECT_BINDING.toml` 判断绑没绑飞书。但 memory 有更完整视图：其他项目的 binding 例、lark-cli app 可用性、openclaw.json 里的 feishu_group_id 分布、候选 chat_id。让 memory 扫一次，ancestor 根据报告决策 + 呈现给 operator。

**修复** `core/templates/ancestor-brief.template.md` B5 段改为：

```markdown
### B5 — Feishu group binding (via memory 调研)

向 memory send-keys 调研请求：

```bash
MEMORY_PROMPT="调研 ${PROJECT_NAME} 的 feishu binding 状态。读：
- ${AGENT_HOME}/.agents/tasks/*/PROJECT_BINDING.toml (glob 所有项目)
- ${AGENT_HOME}/.agents/memory/machine/openclaw.json（看 agents.*.feishu_group_id）
- ${AGENT_HOME}/.lark-cli/config.json（如存在，列可用 app）
- ${AGENT_HOME}/.openclaw/openclaw.json（如存在，看 accounts.*.appId）

生成 ${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-feishu-binding-report.md：
1. ${PROJECT_NAME} 当前 PROJECT_BINDING.toml 状态（绑了 / 未绑 / 文件缺）
2. 本机其他项目绑定示例（mor / cartooner-web 等）
3. 可用 lark-cli app 列表（user/bot mode）
4. 推荐策略：
   - 已绑 → 仅确认
   - 未绑 + 有 lark-cli → 建议 lark-cli chats list 找 chat_id
   - 未绑 + 无 lark-cli → 建议 CLI-only mode
完成后说 'FEISHU_REPORT_READY: <path>'"

tmux send-keys -t '=machine-memory-claude' "$MEMORY_PROMPT" Enter

REPORT_PATH="${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-feishu-binding-report.md"
for i in {1..60}; do
  [[ -f "$REPORT_PATH" ]] && grep -q "FEISHU_REPORT_READY" <(tmux capture-pane -t '=machine-memory-claude' -p -S -20) && break
  sleep 10
done
cat "$REPORT_PATH"
```

ancestor 依据报告在 CLI 呈现给 operator：

- 已绑 → 自动 pass 进 B6
- 未绑 + 有 候选 chat_id → 呈现候选列表让 operator 选 / 粘贴自定义 / skip
- 未绑 + 无候选 → 提示 CLI-only 或让 operator 手动跑 lark-cli

operator 决定后写入：
```bash
python3 $CLAWSEAT_ROOT/core/scripts/agent_admin.py project bind \
  --project ${PROJECT_NAME} \
  --feishu-group <chat_id_or_empty> \
  --bound-by ancestor
```

skip 模式下 bind 仍然建 PROJECT_BINDING.toml（空 chat_id），记录 CLI-only 决策。
```

**其他 B 步同理**：Phase-A 里任何需要"现状感知"的步骤（看机器上有什么 / 有几个 / 绑没绑），都应该交给 memory 调研，而不是 ancestor 自己 os.listdir。这是 v0.7 agent-driven 的核心。

后续 v0.8 / v0.9 可以把 B0 env_scan 汇报、B3 openclaw binding 验证也挪到 memory 调研（本次 SPAWN-049 不做，只修 B2.6 + B5）。

#### 改 4i：B5 正确流程 = 选 agent → 拉群 → 粘贴 chat_id（walk-through 发现）

**问题**：4h 的 B5 让 operator "从现有群里挑 chat_id"，但真实场景是 operator **为新项目新建一个群**，把指定的 openclaw agent 拉进群，再把群 id 告诉 ancestor。

**正确流程**：

1. memory 调研报告应列**可用 openclaw agent**（而非候选 chat_id），含：
   - agent name / appId / app mode (user/bot)
   - 占用状态（其他项目已绑用哪个 agent）
   - 推荐给 cartooner 的 agent
2. ancestor 呈现 agent 列表让 operator 选
3. operator 选 agent 后，ancestor 给**拉群指引**
4. operator 拉群 + 粘贴 chat_id
5. ancestor bind + 进 B6

**修复** `core/templates/ancestor-brief.template.md` B5 段（覆盖 4h）：

```markdown
### B5 — Feishu group binding（agent-driven 新建群流程）

#### B5.1 memory 调研
memory send-keys prompt：
"调研 ${PROJECT_NAME} 的 feishu 绑定可选项。读：
- ${AGENT_HOME}/.openclaw/openclaw.json (agents[] + accounts[])
- ${AGENT_HOME}/.openclaw/extensions/openclaw-lark/ (如存在)
- ${AGENT_HOME}/.agents/tasks/*/PROJECT_BINDING.toml
- ${AGENT_HOME}/.lark-cli/config.json

生成 ${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-feishu-binding-report.md：
1. 本机可用 openclaw agent：name / appId / app mode (user/bot) / 当前绑定状态
2. 其他 clawseat 项目的 agent→group 绑定示例
3. 推荐给 ${PROJECT_NAME} 的 agent（未被占用 + 命名匹配优先）
4. ${PROJECT_NAME} 当前 PROJECT_BINDING.toml 状态
完成后说 'FEISHU_REPORT_READY: <path>'"

#### B5.2 ancestor 呈现 + operator 选 agent
读报告后 CLI 输出：
"Memory 调研结果：
本机可用 openclaw agent：
  [1] cartooner-bot  (appId=cli_xxx, bot mode, 未占用) [推荐]
  [2] cartooner-web-bot (appId=cli_yyy, bot mode, 已绑 cartooner-web)
  [3] openclaw-lark-user (user mode, 多项目共享)

选哪个给 ${PROJECT_NAME}? (回数字或 'skip' 走 CLI-only)"

#### B5.3 operator 选完 → ancestor 给拉群指引
"你选了 cartooner-bot。接下来请你在飞书：

1. 创建新群（建议群名: Cartooner-<你的标识>）
2. 把 @cartooner-bot 拉进群（管理员邀请，或 bot 加群链接）
3. 在群里 @cartooner-bot 发任意消息，确认 bot 能收到
4. 获取 chat_id，二选一：
   a. 终端跑: lark-cli chats list --as bot --app cartooner-bot | grep -i cartooner
   b. 飞书开发者平台 > 应用详情 > 事件订阅 > 群聊列表

把 chat_id (格式 oc_xxxxxxxx) 粘贴给我。或 'skip' 跳过进 CLI-only。"

#### B5.4 operator 粘贴 chat_id → ancestor bind
```bash
python3 $CLAWSEAT_ROOT/core/scripts/agent_admin.py project bind \
  --project ${PROJECT_NAME} \
  --feishu-group <chat_id> \
  --feishu-bot-account <selected_agent_name> \
  --require-mention true \
  --bound-by ancestor
```

#### B5.5 skip 分支
operator 答 skip → 仍创建 PROJECT_BINDING.toml（空 group_id，`cli_only=true`），记录 CLI-only 决策；B6 只跑本地 handoff smoke。
```

**agent_admin project bind 已支持这些 flag**（见 `agent_admin.py:842-879`）✅ 不需要改 CLI。

#### 改 4j：回滚 4f / 4i 的 "memory 调研" 设计（memory 职责必须窄）

**问题（walk-through 对齐发现）**：4f (B2.6 让 memory 调研 openclaw 生态) 和 4i (B5 让 memory 调研 feishu binding) **越界**。

memory 的 canonical 职责（`core/skills/memory-oracle/SKILL.md` + `ancestor skill` §5）：
- **只读查询**：`query_memory.py --kind <decision|finding|issue|delivery|machine>`，返回已有 learnings
- **被动积累**：memory Stop-hook（MEMORY-035）在 pane 有 activity 时 trigger，持续写 `~/.agents/memory/learnings/`
- **Phase-B 巡检伴随**：launchd 注入 `/patrol-tick` 后 ancestor 的 P7 把决策 / 交付物交给 memory 存档

**memory 不该**：
- 承接 ad-hoc "请帮我调研 X" 的 LLM prompt
- 在 Phase-A 关键路径上成为 ancestor 的子思考器
- Phase-B 和 Phase-A 共用一个 "send-keys + 等 report" 的 blocking 同步接口（会把巡检回合和启动流程耦死）

**正确设计**：

##### B2.6 撤销（supersedes 4f）
Phase-A 不新增 B2.6。B2.5 的 `bootstrap_machine_tenants.py` 已经把 openclaw.json agents 灌进 machine.toml 足够了；如果 ancestor 想要 LLM 级综合判断（比如 "cartooner 在生态里什么位置"），**ancestor 自己 Read** 三份文件（`machine/openclaw.json` + `openclaw/workspace.toml` + `clawseat/machine.toml`）做分析，不经过 memory。

brief template 只需把 B2.5 改成：

```markdown
### B2.5 — Bootstrap machine tenants + ancestor 快速概览

跑 `bootstrap_machine_tenants.py` 灌 tenants 后，ancestor 自己 Read：
- ${AGENT_HOME}/.agents/memory/machine/openclaw.json
- ${AGENT_HOME}/.openclaw/workspace.toml（如存在）
- ${AGENT_HOME}/.clawseat/machine.toml

向用户汇报一行摘要：当前 tenant 数、${PROJECT_NAME} 是否已在其中、其他项目概览。不写 learnings 文件，不调 memory。
```

##### B5 改为 ancestor 自己读（supersedes 4i）
ancestor 直接 Read：
- `${AGENT_HOME}/.agents/tasks/*/PROJECT_BINDING.toml`（用 `agent_admin.py project binding-list`）
- `${AGENT_HOME}/.agents/memory/machine/openclaw.json` 的 `agents[]` + `accounts[]`
- `${AGENT_HOME}/.lark-cli/config.json`（如存在）

列可用 openclaw agent + 占用状态 → operator 选 → 给拉群指引 → bind。**不经过 memory**。

brief template B5 段把 "tmux send-keys 给 memory" 的整段替换为 "ancestor 自己 Read 三类文件"，其他（operator 交互 / bind 命令）不变。

##### memory 在 Phase-A 的唯一位置
不是 B2.6 / B5，而是 **B7 之后**：ancestor 把 Phase-A 决策（provider 选择 / seat roster / feishu binding）写到 `~/.agents/memory/learnings/${PROJECT_NAME}-phase-a-decisions.md` 让 memory 后续 Phase-B 巡检时能看到。这是 **ancestor → memory 单向交付**，不是 memory 主动干活。

##### 对已提交的 4f / 4i patch 的处理
codex 如果在做 4f / 4i 的 implementation，**停下**。改为按 4j 描述实施（B2.6 撤销 / B5 改 ancestor 自读）。如果已写代码，回滚 `memory send-keys` 相关片段。

##### 长期方向（v0.8+）
memory 如果要扩大能力，应该是**异步 learnings 积累**（在巡检时预先生成各种常见 report），不是被 ancestor 同步调用。ancestor 查询用 `query_memory.py`，返回 memory 已预生成的 learnings。

#### 改 5：`scripts/wait-for-seat.sh` 新建

```bash
#!/usr/bin/env bash
# Lazy pane attachment: wait until the named tmux session exists, then
# replace this shell with `tmux attach`. Used by install.sh six-pane
# grid for non-ancestor seats — ancestor decides when to spawn each
# seat (via `agent_admin session start-engineer <seat>`); this script
# polls and auto-attaches when the seat goes live.
set -euo pipefail
SESSION="${1:?usage: wait-for-seat.sh <session-name>}"
printf 'pane is waiting for %s ...\n' "$SESSION"
printf '(seat will appear here once ancestor spawns it)\n'
while ! tmux has-session -t "=$SESSION" 2>/dev/null; do
  sleep 5
done
exec tmux attach -t "=$SESSION"
```

权限 0755。

### A3 测试

新建 `tests/test_install_lazy_panes.py`（或扩展现有 test_install_isolation.py）：

1. dry-run 验证 install.sh Step 5 只 launch 1 seat（ancestor），不再有 planner/builder/.../designer 的 launcher 调用
2. dry-run 验证 grid_payload JSON 含 5 个 wait-for-seat.sh command
3. 真跑 fake-root smoke：
   - 跑完 install.sh 后只有 `<project>-ancestor` + `machine-memory-claude` 两个 tmux session
   - `<project>-{planner,builder,reviewer,qa,designer}` 都不存在
4. wait-for-seat.sh 单元测试：mock tmux session 出现后能 exec tmux attach（用 stub tmux 验证 exec 调用）
5. `--provider minimax` flag 跳过 Step 3 交互（mock credentials.json 含多个 provider）

## Subagent B — ancestor brief + project bootstrap 接线

### B1 调研

读 `core/templates/ancestor-brief.template.md` 当前 B3.5 段（行 50-63）：
- 当前用 `agent-launcher.sh --headless --engineer ${seat} --project ${PROJECT_NAME}` —— **launcher 无此 flag**
- 需要改用 `agent_admin session start-engineer <seat> --project <project>`（L2，ISOLATION-048 已接 L3，sandbox HOME 统一）

### B2 实施

#### 改 1：`core/templates/ancestor-brief.template.md`

更新上下文快照段落：
```
- seats 待拉起: planner, builder, reviewer, qa, designer
  - 它们的 profile 已由 install.sh Step 5.5 建好（~/.agents/engineers/<seat>/）
  - 它们对应的 iTerm 六宫格 pane 当前在跑 wait-for-seat.sh，等你 spawn 后自动 attach
```

更新 B3.5 段落：
```
### B3.5 — 逐个澄清 + spawn engineer seat

for seat in [planner, builder, reviewer, qa, designer]:
1. 向用户交互："${seat} provider 用什么？
   - 默认: claude-code + minimax (install.sh 已选)
   - 替代: codex / gemini / 自定义"
2. 如果用户改了 default：
   `python3 core/scripts/agent_admin.py engineer rebind ${seat} --tool <X> --auth <Y> --provider <Z>`
   `python3 core/scripts/agent_admin.py engineer secret-set ${seat} --env <KEY=value>`
3. spawn seat：
   `python3 core/scripts/agent_admin.py session start-engineer ${seat} --project ${PROJECT_NAME}`
4. 如果当前拉起的是 planner seat，跑：
   `python3 core/skills/planner/scripts/install_planner_hook.py --workspace ~/.agents/workspaces/${PROJECT_NAME}/planner --clawseat-root ${CLAWSEAT_ROOT}`
5. 等 `tmux has-session -t '=${PROJECT_NAME}-${seat}'` rc=0
6. 用户目视六宫格里 ${seat} pane 已自动 attach（wait-for-seat 的 exec tmux attach 触发）
7. 下一个 seat
```

### B3 测试

- 跑 `agent_admin project bootstrap` smoke（用 install.sh 准备的 template + local.toml），验证 6 engineer 都建了
- 跑 `agent_admin session start-engineer planner --project <p>`，验证 planner tmux session 起来
- 跑 wait-for-seat.sh 一段时间，spawn planner，验证 wait-for-seat 在 5-10s 内 exec attach 到那个 session

## 验证

```bash
cd /Users/ywf/ClawSeat
bash -n scripts/install.sh && bash -n scripts/wait-for-seat.sh && echo syntax-ok
pytest tests/test_install_isolation.py tests/test_install_lazy_panes.py \
       tests/test_agent_admin_session_isolation.py -q
```

期望：全 pass。

手动 e2e：
```bash
bash scripts/install.sh --project spawn49 --provider minimax
# 期望：六宫格出现，ancestor pane 在线，其他 5 pane 显示 "pane is waiting for spawn49-<seat> ..."
# memory 独立窗口出现
# 进 ancestor pane，让它跑 B3.5：spawn planner
# 期望：planner pane 5s 内自动 attach
```

## 约束

- 不改 ISOLATION-046/047/048 已落地的 launcher / agent_admin_session
- 不破坏现有 cartooner / mor / cartooner-web 项目（agent_admin project bootstrap 是项目级，互不干扰）
- 保留 memory 独立窗口（不合到六宫格）
- ancestor brief 的 B0/B1/B2/B2.5/B3/B5/B6/B7 不动，只改 B3.5 + 上下文快照段
- 不删 install.sh 已有的 launch_seat / launcher_custom_env_file_for_session（仍被 ancestor + memory 用）

## Deliverable

`.agent/ops/install-nonint/DELIVERY-SPAWN-049.md`：

```
task_id: SPAWN-049
owner: builder-codex
target: planner

## 调研结论
### agent_admin project bootstrap 用法
### template 现状 + 新建 clawseat-default.toml 内容

## 改动清单
- scripts/install.sh (Step 5/5.5/7 + --provider flag)
- scripts/wait-for-seat.sh (新建)
- templates/clawseat-default.toml (新建)
- core/templates/ancestor-brief.template.md (B3.5 + 上下文快照)
- tests/test_install_lazy_panes.py (新建)
- (可能) iterm_panes_driver.py 如有 JSON 转义问题

## Verification
- syntax + pytest 输出
- 手 e2e：六宫格 5 pane 等待 + ancestor spawn 后自动 attach 截图

## Notes
- engineer rebind 路径若发现 bug 顺手修
- --provider flag 行为细节
```

**不 commit**。
