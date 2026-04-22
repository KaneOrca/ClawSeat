# TODO — MULTI-IDENTITY-056 (per-project user-tool isolation)

```
task_id: MULTI-IDENTITY-056
source: planner
target: builder-codex
priority: P1 (v0.8 candidate, blocked-by 055 R7-R13 + R5-RCA hotfix)
type: 架构演进（非紧急 hotfix）
queued: 在 055 R5/R7-R13 + 053 R7 + R5-RCA hotfix 全部 commit 之后
```

## 背景

R5-RCA-EMERGENCY 暴露：v0.7 `seed_user_tool_dirs` 把所有 sandbox 的 `.lark-cli` / `.gemini` / `.codex` symlink 到 **real HOME 同一份**，隐含假设"operator 全局单身份"。这违反 ClawSeat 多项目并行的核心愿景：

- smoke01 用余文锋发飞书（sender app A）
- smoke02 用张根铭（sender app B）
- cartooner 用第三人

当前架构所有项目共享 real HOME 一份 lark-cli config，**多用户场景跑不了**。

## 目标

每个项目（smoke01 / smoke02 / cartooner / ...）有独立的 user-level tool config（lark-cli / gemini / codex 等），互不干扰；但同一项目所有 seat 共享同一份（合理：planner/builder/qa 都代表同一项目身份）。

## 设计

### 新目录布局

```
~/.agent-runtime/
├── identities/                       # 现有：tool-level OAuth/API 凭证（已隔离）
│   └── claude/api/custom-...
├── projects/                         # 新增：project-level user-tool 配置
│   ├── smoke01/
│   │   ├── .lark-cli/                # project 独立飞书 identity
│   │   ├── .gemini/
│   │   ├── .codex/
│   │   └── Library/
│   │       ├── Application Support/iTerm2/
│   │       └── Preferences/com.googlecode.iterm2.plist
│   ├── smoke02/
│   │   └── ... (独立 identity)
│   └── cartooner/
│       └── ... (独立 identity)
└── secrets/                          # 现有
```

### 新命令

`agent_admin project init-tools <project> [--from real-home|empty]`：
- 首次创建 `~/.agent-runtime/projects/<project>/`
- `--from real-home`（默认）：copy real HOME 现有 .lark-cli/.gemini/.codex 当初始 config（operator 不需重新 auth）
- `--from empty`：空目录，operator 在该 project 内 `auth login` 重新生成

`agent_admin project switch-identity <project> --tool feishu|gemini|codex --identity <user-or-app-id>`：
- 切换 project 的 tool identity（multi-account 场景：operator 维护多个 lark-cli profile，按 project 分配）

### launcher 改造

`seed_user_tool_dirs` 函数签名扩展：

```bash
seed_user_tool_dirs <runtime_home> <project_name>
```

逻辑：
- 旧：symlink `<runtime_home>/<sub>` → `$REAL_HOME/<sub>`
- 新：symlink `<runtime_home>/<sub>` → `~/.agent-runtime/projects/<project>/<sub>`
- fallback：若 `~/.agent-runtime/projects/<project>/<sub>` 不存在 → 不 seed（让 operator 跑 init-tools 显式初始化）

### PROJECT_BINDING 集成

053 R5 已加 `feishu_sender_app_id`，赋予新含义：
- 项目绑定到的 lark-cli app_id（首次 init-tools 时根据此选 identity）
- bootstrap 流程：扫 real HOME `~/.lark-cli/config.json` apps[] 列表，让 operator 选

新增字段（可选）：
- `gemini_account_email`：绑 gemini Google account
- `codex_account_email`：绑 codex OpenAI account

### v0.7 → v0.8 迁移

- 现有 v0.7 项目（smoke01/smoke02/cartooner/install）首次启动 v0.8 launcher 时：
  - 自动 `agent_admin project init-tools <project> --from real-home`
  - copy real HOME 现状到 per-project dir
  - 旧 symlink 自动重定向到新位置
- 提供回退命令 `agent_admin project use-real-home <project>`：把 project 临时退回共享 real HOME 模式（debug 用）

## 测试

- `tests/test_agent_admin_project_init_tools.py`：验证 init-tools 创建目录 + copy real HOME
- `tests/test_agent_admin_project_switch_identity.py`：switch-identity 修改 PROJECT_BINDING + relink sandbox
- `tests/test_launcher_per_project_seed.py`：launcher seed 走 per-project dir
- `tests/test_v07_to_v08_migration.py`：旧项目自动 migrate
- `tests/test_multi_identity_isolation.py`：smoke01 改 lark-cli auth 不影响 smoke02

## 约束

- **不破坏 v0.7 现有 sandbox**（migration 必须无损）
- **memory daemon 仍跨项目共享**（只 user-tool 走 per-project，memory 是机器级 singleton）
- **不强制 multi-identity**：单用户场景 `init-tools --from real-home` + 不 switch-identity = 行为等价 v0.7

## Deliverable

`.agent/ops/install-nonint/DELIVERY-MULTI-IDENTITY-056.md`：
- 改动清单（agent_admin / launcher / project_binding / 5+ tests）
- 迁移路径文档
- v0.7 → v0.8 兼容性矩阵

**先调研，待 planner approve 设计后再编码**。
