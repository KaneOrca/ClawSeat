# TODO — FEISHU-AUTH-053 (飞书通道 / lark-cli / PROJECT_BINDING schema 系统性修复)

```
task_id: FEISHU-AUTH-053
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0 (R1-R4) + P1 (R5-R6)
subagent-mode: REQUIRED — 2 subagents
  A = launcher sandbox home 修复 + send_delegation_report.py 改造（R1/R2）
  B = SKILL.md / brief / PROJECT_BINDING schema / B5 子步分层（R3/R4/R5/R6）
scope: 解决 smoke01 Phase-A 暴露的飞书通道 5 层系统性问题
queued: 在 ARK-050 regression fix + MEMORY-IO-051 DELIVERY 补写之后
```

## Context

smoke01 Phase-A 跑到 B6 飞书 smoke 时暴露 5 层系统性问题（planner 调研 lark-cli CLI + 源码 + sandbox 路径后确认）：

### 问题 1 · lark-cli 在 ancestor sandbox HOME 完全隔离

- ancestor 在 `~/.agent-runtime/identities/claude/api/custom-<session>/home/` sandbox HOME 里运行
- sandbox `.lark-cli/config.json` 和 real HOME `~/.lark-cli/config.json` **是两个独立文件**
- operator 在 real HOME 跑 `lark-cli auth login`，auth token 只落 real HOME keychain
- ancestor 在 sandbox 看到的是空 / 过期 / 另一个 app 的 config → 误报 "No user logged in"
- 这是 launcher sandbox HOME 的**系统性盲区**（类似 HOMEFIX-045 修 preflight HOME、SPAWN-049 4d 修 brief `$AGENT_HOME`，但 lark-cli 没覆盖）

### 问题 2 · `send_delegation_report.py` 硬编码 user-only

文件头注释（过时）：
```
# Bot-identity limitation: this script always sends as the USER identity via lark-cli OAuth.
# Bot-identity transport (Feishu app bot) is intentionally NOT supported here because:
#   1. lark-cli only exposes the user OAuth flow; bot tokens require a separate Feishu app credential.
```

**但 lark-cli 1.0.14 早已双身份**：`--as user|bot|auto` flag 所有 im 命令都支持。script 没跟上。

### 问题 3 · ancestor SKILL.md 缺 lark-cli 真实命令 reference

smoke01-ancestor 用了 **`lark-cli chats list`**（不存在的假命令），真实命令是 `lark-cli im +chat-search`。SKILL.md §5 "对外通讯" 对飞书完全没说 lark-cli 怎么用。

### 问题 4 · ancestor 缺 auth 状态诊断决策树

smoke01-ancestor 死循环在"user auth 不通"，没意识到 bot-only 是合法路径（lark-cli + `--as bot` + `im:message` scope 能独立发消息）。需要 4 种 auth 状态的决策树：

| lark-cli auth status | 正确响应 |
|---------------------|---------|
| user only（valid） | 用 user 发（现有 default） |
| bot only（valid） | 用 bot 发（`--as bot` 显式） |
| user + bot 都 valid | 按 brief / binding 配置选（默认 user，bot 作为备份） |
| 都 invalid / 缺失 | halt + 指引 operator 跑 `lark-cli auth login` |

### 问题 5 · PROJECT_BINDING schema 字段语义混淆

smoke01 bind 时 `feishu_bot_account=yu` —— 但 `yu` 是 **openclaw agent**（koder overlay 目标），**不是飞书 sender**。飞书 sender 是 `cli_a96abcca2e78dbc2`（lark-cli app）。两个概念串位。

## R1 (P0) — launcher symlink lark-cli 到 real HOME

### R1 · 改动（扩展为 multi-tool user-level seed）

`core/launchers/agent-launcher.sh` `run_claude_runtime` / `run_codex_runtime` / `run_gemini_runtime`（所有 tool）在 `runtime_dir` setup 完之后、`exec <tool>` 之前，新增一个 **generic helper `seed_user_tool_dirs()`**，seed 多个 user-level 工具目录/socket（都是 sandbox HOME 盲区）：

```bash
seed_user_tool_dirs() {
  local runtime_home="$1"
  # symlinks: source (in real HOME) → target (in sandbox HOME)
  # 只 seed 存在的源，跳过已有目标。symlink 是 bi-directional（sandbox 写就到 real HOME）
  local seeds=(
    ".lark-cli"                                   # lark-cli app + OAuth token registry (FEISHU-AUTH-053 R1 原始 scope)
    "Library/Application Support/iTerm2"          # iTerm2 Python API socket (smoke02 实测暴露)
    "Library/Preferences/com.googlecode.iterm2.plist"  # iTerm2 prefs (某些命令需要)
  )
  local src tgt
  for sub in "${seeds[@]}"; do
    src="$REAL_HOME/$sub"
    tgt="$runtime_home/$sub"
    if [[ -e "$src" && ! -e "$tgt" ]]; then
      mkdir -p "$(dirname "$tgt")"
      ln -s "$src" "$tgt"
    fi
  done
}
```

三个 `run_*_runtime` 在最后 `exec <tool>` 前都调一次 `seed_user_tool_dirs "$runtime_dir/home"`。

考虑复用已有的 `prepare_claude_home()` 作为参考（它 symlink `~/.claude.json` + `~/.claude/settings.json`）。新增这个 `seed_user_tool_dirs` 和 `prepare_claude_home` / `prepare_codex_home` / `prepare_gemini_home` 并列（都是 "seed sandbox HOME from real HOME" 类操作）。

**设计原则**：
- 只 seed 用户级 shared resources（auth / socket / preferences），不 seed 秘密 keyring
- 所有 seed 都 symlink（不复制），让 sandbox 写回 real HOME（如 ancestor 跑 `lark-cli auth login` 完成会持久化）
- 未来新增 user-level tool 都往 `seeds[]` 数组里加一行即可

**已知覆盖的 sandbox HOME 盲区列表**（写入 DELIVERY "Known blind spots" 段留给未来参考）：
1. `~/.lark-cli/` — FEISHU-AUTH-053 R1 原始场景
2. `~/Library/Application Support/iTerm2/` — smoke02 iterm_panes_driver 暴露
3. `~/Library/Preferences/com.googlecode.iterm2.plist` — iTerm2 配置
4. `~/.agents/memory/` — 已经是绝对路径使用 `$AGENT_HOME`，**不**需 symlink（SPAWN-049 4d 处理过）
5. `~/.claude/` — `prepare_claude_home()` 已处理
6. `~/.codex/` — `prepare_codex_home()` 已处理
7. `~/.gemini/` — `prepare_gemini_home()` 已处理
8. 未来可能新增：`~/.ssh/`（如 ancestor 需要 git 操作）、`~/.config/gh/`（GitHub CLI）、`~/Library/Keychains/`（危险，暂不 seed）

### R1 · 测试

`tests/test_launcher_lark_cli_seed.py`：

1. Mock runtime_dir 建好后，跑 `prepare_lark_cli_home` helper
2. 验 `$runtime_dir/home/.lark-cli` 是 symlink 指向 `$REAL_HOME/.lark-cli`
3. real HOME 不存在 `.lark-cli` 时跳过（不 fail）
4. sandbox 已有 `.lark-cli`（非 symlink）时不覆盖（保守）

## R2 (P0) — `send_delegation_report.py` 支持 bot/auto identity

### R2 · 改动

`core/skills/gstack-harness/scripts/send_delegation_report.py`:

1. **删除** user-only hardcode 注释（文件头 lines 2-10）
2. **新增 `--as` 参数**：
   ```python
   parser.add_argument(
       "--as",
       dest="identity",
       choices=["user", "bot", "auto"],
       default="auto",
       help="lark-cli identity: user (OAuth) | bot (appSecret) | auto (default)",
   )
   ```
3. **传给 lark-cli 命令**：
   ```python
   cmd = ["lark-cli", "im", "+messages-send", "--chat-id", chat_id, ...]
   if args.identity != "auto":
       cmd.extend(["--as", args.identity])
   ```
4. **auth 检查也要 `--as`-aware**：
   ```python
   # --auth-check mode 按 args.identity 查对应身份
   ```
5. **scope 提示**：user 发消息需 `im:message.send_as_user`；bot 发需 `im:message`。当 lark-cli 报 scope 缺失时，错误信息要引导 operator 加对应 scope

### R2 · 测试

`tests/test_send_delegation_report_identity.py`:

1. `--as user` → cmd 含 `--as user`
2. `--as bot` → cmd 含 `--as bot`
3. `--as auto`（default）→ cmd 不含 `--as`
4. `--auth-check --as bot` → `lark-cli auth status --as bot` 调用
5. 文件头 **不再** 含 "Bot-identity limitation" hardcode

## R3 (P0) — ancestor SKILL.md lark-cli cheat sheet

### R3 · 改动

`core/skills/clawseat-ancestor/SKILL.md` §5 "对外通讯" 末尾新增：

```markdown
### 5.x · Feishu via lark-cli（canonical 命令）

```bash
# 1. 查 auth 状态（第一步必做）
lark-cli auth status                    # default identity
lark-cli auth status --as user          # 显式查 user
lark-cli auth status --as bot           # 显式查 bot

# 2. 查群（按群名）
lark-cli im +chat-search --params '{"query":"<groupname>"}' --as user

# 3. 发消息（text）
lark-cli im +messages-send \
  --chat-id oc_xxxxxxxx \
  --data '{"msg_type":"text","content":"{\"text\":\"hello\"}"}' \
  --as user    # 或 --as bot

# 4. 批量消息 / OC_DELEGATION_REPORT 走 wrapper
python3 ${CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/send_delegation_report.py \
  --project ${PROJECT_NAME} --chat-id oc_... --as user    # 或 --as bot / --as auto
```

### 禁用（假命令 / 错用法）

- ❌ `lark-cli chats list` — 该子命令**不存在**，用 `lark-cli im +chat-search`
- ❌ 假设 lark-cli 只支持 user — 1.0.14+ 支持 bot，`--as bot` 即可

### lark-cli app / OpenClaw agent app 不混

- `~/.lark-cli/config.json` 的 `apps[].appId` = **lark-cli app**（飞书通道发送身份）
- `~/.agents/memory/machine/openclaw.json` 的 `agents[].appId` = **OpenClaw agent app**（koder / 项目 agent）
- 两者**独立**，PROJECT_BINDING 里要分字段记录（见 §5.y）
```

### R3 · 测试

`tests/test_ancestor_skill_lark_cli_cheat_sheet.py`：
- SKILL.md §5 含 `im +messages-send` + `--as user|bot`
- SKILL.md 含"禁用 `lark-cli chats list`" 或类似警告
- SKILL.md 含 "lark-cli app / OpenClaw agent app 不混" 段

## R4 (P0) — ancestor auth 状态决策树

### R4 · 改动

`core/skills/clawseat-ancestor/SKILL.md` §5 之后新增 §5.y：

```markdown
### 5.y · Feishu auth 状态决策树

Phase-A B5.2 或 Phase-B P4 飞书发送前必先跑：

```bash
AUTH_STATUS=$(lark-cli auth status 2>&1)
USER_VALID=$(echo "$AUTH_STATUS" | python3 -c "import json,sys; d=json.load(sys.stdin); print('true' if d.get('identity')=='user' and d.get('tokenStatus')=='valid' else 'false')" 2>/dev/null || echo false)
BOT_VALID=$(lark-cli auth status --as bot 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('true' if d.get('tokenStatus')=='valid' else 'false')" 2>/dev/null || echo false)
```

然后按 4 种状态响应：

| user_valid | bot_valid | 响应 |
|-----------|-----------|------|
| true | false | 默认 user 发（`send_delegation_report.py --as user`） |
| false | true | 切 bot 发（`send_delegation_report.py --as bot`） |
| true | true | 按 PROJECT_BINDING.feishu_sender_mode 选；默认 user |
| false | false | halt + 指引 operator 跑 `lark-cli auth login`（user flow）或配 bot appSecret |

**不要**：
- 死盯 user auth 不通（忽略 bot 可用性）
- 照 operator "跑 lark-cli auth login --recommend" 建议而不先确认 bot 是否已够用
```

### R4 · brief template 同步

`core/templates/ancestor-brief.template.md` B5 段指向 `SKILL.md §5.y`。

### R4 · 测试

`tests/test_ancestor_auth_decision_tree.py`：
- SKILL.md §5.y 含 4 种状态表
- brief template B5 引用 §5.y

## R5 (P1) — PROJECT_BINDING schema 拆 4 field

### R5 · schema 改动

`core/scripts/project_binding.py` `ProjectBinding` dataclass 升级：

```python
@dataclass
class ProjectBinding:
    project: str
    feishu_group_id: str = ""              # oc_xxxxxxxx (unchanged)
    feishu_sender_app_id: str = ""         # NEW: lark-cli app that sends msgs (cli_xxx)
    feishu_sender_mode: str = "auto"       # NEW: "user" | "bot" | "auto"
    openclaw_koder_agent: str = ""         # NEW: OpenClaw agent that gets koder overlay
    require_mention: bool = False          # unchanged
    bound_by: str = ""                     # unchanged
    bound_at: str = ""                     # unchanged

    # Backward compat: old `feishu_bot_account` field alias
    @classmethod
    def from_toml(cls, data: dict) -> "ProjectBinding":
        # If legacy feishu_bot_account present, migrate to either
        # sender_app_id (if starts with "cli_") or openclaw_koder_agent
        # (if matches openclaw agent name).
        legacy = data.pop("feishu_bot_account", "")
        if legacy and not (data.get("feishu_sender_app_id") or data.get("openclaw_koder_agent")):
            if legacy.startswith("cli_"):
                data["feishu_sender_app_id"] = legacy
            else:
                data["openclaw_koder_agent"] = legacy
        return cls(**data)
```

### R5 · CLI 改动

`agent_admin.py cmd_project_bind` 加 flag：

```
--feishu-sender-app-id <cli_xxx>
--feishu-sender-mode user|bot|auto
--openclaw-koder-agent <name>
```

保留旧 `--feishu-bot-account` flag（warn deprecated，自动 route 到 sender_app_id 或 koder_agent）。

### R5 · 测试

`tests/test_project_binding_schema_v2.py`：
- 新 schema dump 4 field
- 读旧 `feishu_bot_account=cli_xxx` → sender_app_id
- 读旧 `feishu_bot_account=yu`（不带 cli_ 前缀）→ openclaw_koder_agent
- `agent_admin project bind --feishu-bot-account cli_xxx` warn deprecated + 正确 route

## R6 (P1) — ancestor B5 子步分层

### R6 · brief template 改动

`core/templates/ancestor-brief.template.md` B5 段彻底重写为 5 子步：

```markdown
### B5 — Feishu channel + koder overlay bind（5 子步）

#### B5.1 · 选 openclaw agent 做 koder overlay
[ancestor 自读 openclaw.json agents[] + project binding-list 呈现菜单]
[operator 选定后跑 apply-koder-overlay.sh <project> <chat_id_if_known>]

#### B5.2 · 飞书 auth pre-flight（按 §5.y 决策树）
[lark-cli auth status → 识别 user / bot / dual / none 4 种状态]

#### B5.3 · 选 sender + 拉群 + 获取 chat_id
[按 B5.2 结果选 sender mode + app_id]
[指引 operator 飞书新建群 + 拉 sender 进群 + lark-cli im +chat-search 查 chat_id]

#### B5.4 · project bind（4 字段）
python3 agent_admin.py project bind --project <p> \
  --feishu-group <oc_xxx> \
  --feishu-sender-app-id <cli_xxx> \
  --feishu-sender-mode user|bot|auto \
  --openclaw-koder-agent <agent_name>

#### B5.5 · verify smoke dispatch
python3 send_delegation_report.py --project <p> --chat-id <oc_xxx> --as <mode>
[按 B5.2 的 sender mode 选；如失败按错误码排查 scope / 群成员 / 应用审核]
```

### R6 · 测试

`tests/test_ancestor_brief_b5_substeps.py`：
- brief 含 B5.1 / B5.2 / B5.3 / B5.4 / B5.5 五个子步
- B5.4 含 4 个 bind field
- B5.5 引用 send_delegation_report.py + `--as <mode>`

## R7 (P1) — koder 非 @ 响应的两层配置文档化

### 问题背景（memory 调研）

smoke01 apply-koder-overlay.sh 完成后，bot 仍然只响应 @ 消息。memory `query_memory.py --search requireMention` 显示：
- **Layer 1 (OpenClaw 侧)** `openclaw.json → config.channels.feishu.accounts.<agent>.groups.<group_id>.requireMention = false`：koder account 已有 `groups.*.requireMention=false` 默认，smoke01 绑的 group 也已 `False`。✓
- **Layer 2 (飞书开发者平台)** `app 后台 → 事件订阅 → 消息接收模式 = "接收群聊所有消息"`：smoke01 遗漏此步，lark-cli 不支持此配置，必须 UI 手动。✗

memory 历史 feedback: `feedback_feishu_bot_receive_mode.md` — 非 @ 不响应先查飞书开发者平台设置，**非 OpenClaw requireMention**。

### R7.1 · apply-koder-overlay.sh 完成后打印 Layer 2 提示

`scripts/apply-koder-overlay.sh` 末尾（PROJECT_BINDING 写完 / openclaw.json patch 完之后、exit 前）追加：

```bash
cat <<'POST_OVERLAY_NOTE'

✓ koder overlay applied (OpenClaw Layer 1 ready).

⚠ Feishu Layer 2 配置必需（operator 手动操作）：
  1. 打开 https://open.feishu.cn/app
  2. 选 app <FEISHU_SENDER_APP_ID>（见 PROJECT_BINDING.toml）
  3. 事件订阅 → 消息接收模式 → 选 "接收群聊所有消息"（非仅 @）
  4. 如 app 已 release，点击 "刷新 release"
  5. 完成后回 ancestor 确认 "ok"，B5 继续

注：此步 lark-cli / Open API 不可编程，必须 UI 操作。
配置不做 → bot 只响应 @，非 @ 消息到达不了 OpenClaw。
POST_OVERLAY_NOTE
```

注意 `<FEISHU_SENDER_APP_ID>` 用脚本已知变量替换（从 PROJECT_BINDING.toml `feishu_sender_app_id` 读，R5 schema 提供）。

### R7.2 · brief B5 追加 substep B5.4.5 "Feishu Layer 2 UI 配置"

`core/templates/ancestor-brief.template.md` B5 在 B5.4（bind）和 B5.5（smoke）之间加 B5.4.5：

```markdown
**B5.4.5 · 飞书 Layer 2 UI 配置（operator 手动，一次性）**

apply-koder-overlay.sh 已打印提示。如 operator 未完成 / 不确定：
- operator 必须 UI 登录 https://open.feishu.cn/app 配置 app 事件订阅消息接收模式
- 未完成时 B5.5 smoke 将只能测 @ 路径，非 @ 要等配置后重测
- 配置后无需重启 OpenClaw（事件订阅 pull 模式实时生效）

ancestor 行动：向 operator 确认 "Layer 2 已配置完成" → 记入 phase-a-decisions.md → 继续 B5.5。
未确认 → halt B5.5，不自行推进。
```

### R7.2.5 · SKILL.md §5.z "Feishu 联调 canonical troubleshooting"（smoke01 实战总结）

`core/skills/clawseat-ancestor/SKILL.md` §5 追加完整章节（这份是 operator ywf 在 smoke01 Phase-A B6 踩坑后总结，需整段原样纳入 brief / SKILL 作 canonical 资料）：

```markdown
### 5.z Feishu/lark-cli 联调 troubleshooting（canonical）

遇到 Feishu 发送失败时，**严格按此流程排查**，不要凭直觉猜：

#### 6 类常见问题速查

| 症状 | 根因 | 解决 |
|------|------|------|
| `send_delegation_report.py pre_check_auth` 不认 `--as` | script 硬编 user | 加 `--as bot` / 绕过 pre_check |
| 多 HOME 身份混乱（余文锋 vs 张根铭） | real/sandbox 是独立 lark-cli app | 先 `HOME=<path> lark-cli auth status` 确认 identity |
| Sandbox HOME 没 `.lark-cli/config.json` | seed 未生效 | 检查 R1 的 launcher symlink；sandbox 旧实例要 reseed |
| `230002` | bot/user 不在群 | 把该 identity 拉进群 |
| `missing_scope` | token 缺权限 | 飞书后台加 scope → OAuth 重授权 |
| auto 模式 user 失败不 fallback bot | 脚本逻辑缺失 | `FEISHU_SENDER_MODE=bot` 或 `--as bot` |

#### 7 步诊断流程

1. `lark-cli auth status` — 看 identity + tokenStatus
2. `lark-cli auth check --scope "im:message.send_as_user"` — 看 missing
3. `lark-cli im chats list --as user --page-all | grep oc_` + 同样 `--as bot`  — 对比两身份可见群
4. `lark-cli im +messages-send --as {user,bot} --chat-id <gid> --text test` — 两身份分别测试
5. 缺 scope：`lark-cli auth login --scope "im:message.send_as_user"` → 浏览器授权
6. 多 HOME 交叉：`HOME=/Users/ywf lark-cli auth status` / `HOME=$AGENT_HOME ...` — 确保发送和认证用同一 HOME
7. 集成脚本：`FEISHU_SENDER_MODE=bot python3 scripts/send_delegation_report.py ...`

#### 错误码

| 码 | 含义 | 解决 |
|----|------|------|
| 230002 | bot/user 不在群 | 拉进群 |
| 232010 | 操作者/群租户不一致 | 确认群属 app 租户正确 |
| missing_scope | token 缺权限 | 后台加 scope + OAuth |

#### 常见陷阱

- **real HOME lark-cli app ≠ sandbox lark-cli app**（不同 app_id，scope/群成员完全隔离）。一份 auth 不能跨 HOME 用
- **bot identity 看得到的群 ≠ user identity 看得到的群**（即使都 auth 了）；测发送前必 `chats list` 双身份对比
- `im:message` 和 `im:message.send_as_user` 是**两个独立 scope**；bot 有前者不代表能 send_as_user

### 5.y.5 始祖自检 first-time 模板

遇 Feishu 问题**先跑完 5.z 的 7 步**，再报错给 operator。直接跳到 "无法发送" 结论属 ARCH_VIOLATION（未按流程诊断）。
```

### R7.3 · SKILL.md §5 追加 "Feishu 两层配置" 说明

`core/skills/clawseat-ancestor/SKILL.md` §5（对外通讯）追加：

```markdown
### 飞书两层配置（非 @ 响应必需）

koder bot 在群里非 @ 也能回复，需要两层同时 OK：
1. **OpenClaw 侧**（`openclaw.json`）：`config.channels.feishu.accounts.<agent>.groups.<gid>.requireMention = false`
2. **飞书开发者平台**（手动 UI）：app 后台 → 事件订阅 → 消息接收模式 = "接收群聊所有消息"

apply-koder-overlay.sh 处理 L1，L2 operator 手动。brief B5.4.5 覆盖 L2 确认。

**故障症状 → 层次诊断**：
- bot 只响应 @ 消息：**L2 问题**（最常见；L1 koder 默认已正确）
- bot 完全不响应：**L1 问题**（requireMention 真值查 openclaw.json 或 memory `query_memory.py --search requireMention`）
- 部分群响应部分群不响应：**L1 group 级配置不一致**（memory 查具体 group requireMention）
```

### R7.4 · 测试

`tests/test_koder_overlay_l2_hint.py`：
- mock apply-koder-overlay.sh 执行 → 验证 stdout 含 "https://open.feishu.cn/app" + "接收群聊所有消息"

`tests/test_ancestor_brief_b5_45_l2.py`：
- brief B5 含 B5.4.5 子步
- B5.4.5 含 "Layer 2" 或 "事件订阅" 关键字
- halt 语义存在（operator 未确认 → 不推进 B5.5）

`tests/test_ancestor_skill_feishu_two_layers.py`：
- SKILL.md §5 含 "两层配置" 或 "Layer 1 / Layer 2"
- 含故障诊断对照表（"只响应 @" / "完全不响应" / "部分群"）

## 验证（所有 R1-R7 完成后）

```bash
cd /Users/ywf/ClawSeat
bash -n scripts/install.sh
bash -n core/launchers/agent-launcher.sh
pytest tests/test_launcher_lark_cli_seed.py \
       tests/test_send_delegation_report_identity.py \
       tests/test_ancestor_skill_lark_cli_cheat_sheet.py \
       tests/test_ancestor_auth_decision_tree.py \
       tests/test_project_binding_schema_v2.py \
       tests/test_ancestor_brief_b5_substeps.py \
       tests/test_koder_overlay_l2_hint.py \
       tests/test_ancestor_brief_b5_45_l2.py \
       tests/test_ancestor_skill_feishu_two_layers.py -q

# 回归
pytest tests/test_install_isolation.py tests/test_install_lazy_panes.py \
       tests/test_ancestor_brief_spawn49.py tests/test_ark_provider_support.py -q
```

## 约束

- **不改 lark-cli 本身**（homebrew 包，不在我们 repo）
- **不破坏** ARK-050 / SPAWN-049 / MEMORY-IO-051 / BRIEF-SYNC-052 已落地的路径
- **不做 auto-migrate existing PROJECT_BINDING.toml**（backward compat 读老字段即可；operator 主动 re-bind 再用新 schema）
- R1 symlink 对 real HOME 无 `.lark-cli` 的 operator（没用 lark-cli 过）是 no-op
- R2 发消息的用户话术错误提示要明确区分 user scope 缺失 vs bot scope 缺失

## Deliverable

`.agent/ops/install-nonint/DELIVERY-FEISHU-AUTH-053.md`:

```
task_id: FEISHU-AUTH-053
owner: builder-codex
target: planner

## 调研结论
### lark-cli 1.0.14 auth 模型（user / bot / auto）
### ancestor sandbox HOME vs real HOME .lark-cli 隔离
### send_delegation_report.py 过时 hardcode

## 改动清单
Subagent A (R1/R2):
- core/launchers/agent-launcher.sh (3 tool runtime 加 lark-cli home seed)
- core/skills/gstack-harness/scripts/send_delegation_report.py (删 hardcode + --as flag)

Subagent B (R3/R4/R5/R6/R7):
- core/skills/clawseat-ancestor/SKILL.md §5.x + §5.y + §5.z (R7.3 两层配置)
- core/templates/ancestor-brief.template.md B5 5 子步 + B5.4.5 (R7.2)
- core/scripts/project_binding.py schema v2 + backward compat
- core/scripts/agent_admin_crud.py cmd_project_bind 新 flags
- core/scripts/agent_admin.py cmd_project_bind new flags dispatch
- scripts/apply-koder-overlay.sh 末尾 L2 提示 (R7.1)

测试:
- tests/test_launcher_lark_cli_seed.py
- tests/test_send_delegation_report_identity.py
- tests/test_ancestor_skill_lark_cli_cheat_sheet.py
- tests/test_ancestor_auth_decision_tree.py
- tests/test_project_binding_schema_v2.py
- tests/test_ancestor_brief_b5_substeps.py
- tests/test_koder_overlay_l2_hint.py
- tests/test_ancestor_brief_b5_45_l2.py
- tests/test_ancestor_skill_feishu_two_layers.py

## Verification
<bash + pytest 输出>

## Notes
- smoke01 需要 operator 手动 re-bind (apply new schema)
- v0.8 followup：migration CLI 从 legacy PROJECT_BINDING.toml 批量升级
```

**不 commit**。
