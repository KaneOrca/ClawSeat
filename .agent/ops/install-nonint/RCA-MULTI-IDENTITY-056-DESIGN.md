# MULTI-IDENTITY-056 设计调研

结论先行：这条线不要去改 `real_user_home()` 这类全局 SSOT。正确的 v0.8 方向是新增一层 **project-scoped user-tool layer**，让每个 project 拥有自己的工具身份与工具目录，seat runtime 只负责指向该 project layer。`tools_isolation` 是 project 级开关，`shared-real-home` 只是兼容路径。

## Q1 · 现状 audit

| 位置 | 现在的假设 | 改造成 per-project 的工作量 | 备注 |
|---|---|---:|---|
| [core/lib/real_home.py:74-114](/Users/ywf/coding/ClawSeat/core/lib/real_home.py#L74) | `real_user_home()` 是 operator 全局 real HOME 的 SSOT | large, 但建议不要改语义 | 这是整个仓库的 global anchor。multi-identity 不应该把它改成 project-aware，应该新增 project tool root helper。 |
| [core/lib/runtime_home_links.py:76-168](/Users/ywf/coding/ClawSeat/core/lib/runtime_home_links.py#L76) | sandbox HOME 只会回链到 `real_home`，且只认识 `.lark-cli` / `.openclaw` | moderate | 这是典型的 v0.7 共享 real HOME 逻辑。可以保留为 `shared-real-home` fallback，但不能再作为 v0.8 的默认路径。 |
| [core/scripts/agent_admin_resolve.py:39-80](/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_resolve.py#L39) | `build_runtime()` 以 `AGENT_HOME/real_user_home()` 作为 shared agent home，并把 seat HOME 链回去 | large | 这里是 seat runtime 进入 project layer 的主要入口。要改成读取 project tool root，并把 project layer 注入到 runtime env。 |
| [core/launchers/agent-launcher.sh:863-924](/Users/ywf/coding/ClawSeat/core/launchers/agent-launcher.sh#L863) 与 [core/launchers/agent-launcher.sh:926-1165](/Users/ywf/coding/ClawSeat/core/launchers/agent-launcher.sh#L926) | Claude / Codex / Gemini 的 home prepare 仍在从 `REAL_HOME` 回填，且 oauth 分支直接 `HOME=$REAL_HOME` | large | 这是最明显的 global single identity 假设。要拆成 project-scoped tool home seed，并保留 real-home 作为显式 fallback。 |
| [core/scripts/agent_admin_runtime.py:210-229](/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_runtime.py#L210) | `identity_name()` / `runtime_dir_for_identity()` / `secret_file_for()` 仍然以工具 + provider + engineer 为主，secret 还是 `~/.agents/secrets/<tool>/<provider>/<engineer>.env` | large | 这里已经不是单纯的路径重命名，而是数据模型升级。multi-identity 需要把 secret / identity 变成 project-scoped，至少要能落到 project layer。 |
| [core/scripts/agent_admin_switch.py:97-166](/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_switch.py#L97) | `switch-harness` / `switch-auth` 继续按当前 per-engineer secret 逻辑拼 session | large | 这条线要一起改，否则新 project layer 只会在 launch 时生效，switch 时又回到旧的 engineer-centric 路径。 |
| [core/scripts/agent_admin_parser.py:179-230](/Users/ywf/coding/ClawSeat/core/scripts/agent_admin_parser.py#L179) 与 [core/scripts/agent_admin.py:833-917](/Users/ywf/coding/ClawSeat/core/scripts/agent_admin.py#L833) | `project` 子命令只有 `bind / binding-show / binding-list / unbind / layout`，没有 `init-tools` / `switch-identity` | large | 这是 net-new 命令面，parser、handlers、帮助文案、测试都要一起补。 |
| [core/lib/project_binding.py:1-247](/Users/ywf/coding/ClawSeat/core/lib/project_binding.py#L1) | `PROJECT_BINDING.toml` 还是 v1，只有 Feishu group / bot / mention-gate 相关字段 | moderate | 适合做 schema v3 升级点。它已经是 per-project SSOT，最适合挂上 `tools_isolation` 和项目级工具身份字段。 |
| [core/skills/gstack-harness/scripts/_feishu.py:54-70](/Users/ywf/coding/ClawSeat/core/skills/gstack-harness/scripts/_feishu.py#L54) 与 [core/skills/gstack-harness/scripts/_feishu.py:441-458](/Users/ywf/coding/ClawSeat/core/skills/gstack-harness/scripts/_feishu.py#L441) | Feishu 侧仍然通过 `_real_user_home()` / `LARK_CLI_HOME` 做全局 real HOME 回退 | moderate | 这里不需要推翻 canonical real-home 逻辑，但要让 project layer 能把 `LARK_CLI_HOME` 指到 project-scoped home。 |

结论：
- `real_user_home()` 继续做 operator-global SSOT，不要硬改成 project-aware。
- per-project identity 的正确切入点是 **project tool root**，不是全局 home。
- 当前所有 seat runtime 都已经是 project-aware 的 identity，但它们共享的 user-level tool state 还没有 project layer。

## Q2 · 工具 multi-profile 支持

| 工具 | 现状判断 | 推荐 isolation 策略 |
|---|---|---|
| `lark-cli` | `--help` 明确有 `--profile`，还有 `profile` 子命令；同时还有 `--as user|bot|auto`，说明它天然支持 profile / sender persona 的分离 | 优先走 **native profile**，不要把“身份切换”完全压在文件系统隔离上。project binding 里记录 active profile，project layer 负责选 profile。 |
| `gemini` CLI | `--help` 没有显式 account/profile 管理入口，只有 `--resume / --list-sessions / --worktree / --sandbox` 等 workspace/session 能力 | 归到 **filesystem isolation**。project layer 需要一份独立的 `~/.gemini` 语义根，identity 切换靠 project-local files / re-login。 |
| `codex` CLI | `--help` 有 `--profile`，但那是 config profile，不是明确的多账号 auth 切换；auth state 仍然落在 `CODEX_HOME/auth.json` | 归到 **filesystem isolation + config profile**。project layer 提供独立 `CODEX_HOME`，`--profile` 只负责模型/配置，不负责跨 project 共享 auth。 |
| `iTerm2` | 没有稳定的账号/profile 切换 CLI；仓内使用的是 iTerm2 Python API / AppleScript / plist 语义 | 归到 **filesystem isolation**。project layer 需要显式 seed `Library/Application Support/iTerm2` 和 `Library/Preferences/com.googlecode.iterm2.plist`。 |

推荐的 per-tool 规则：
- **原生支持 multi-profile 的工具**，优先用工具自己的 profile 切换机制。
- **单 profile 或没有账号切换入口的工具**，用 project-scoped filesystem isolation。
- **project layer** 才是“当前项目用哪个 user identity”的真相，seat runtime 只做消费端，不再直接读 real HOME。

## Q3 · v0.7 → v0.8 migration

### 现状快照

- seat runtime 这层已经是 project-aware 的：`identity_name()` 把 `project_name` 放进 identity，`runtime_dir_for_identity()` 也已经以 identity 为 key。
- 真正还在共享的是 user-level tool state，尤其是 `.lark-cli` / `.gemini` / `.codex` / iTerm2 相关文件。
- 目前的回链逻辑还是 `REAL_HOME` / `AGENT_HOME` 主导，等于“所有 project 共用同一份 real HOME 身份”。

### 推荐迁移步骤

1. **建立 project tool root**
   - 统一落到 `~/.agent-runtime/projects/<project>/...`
   - 目录里放 project-scoped 的 `lark-cli / gemini / codex / iTerm2` 状态
2. **显式初始化**
   - `agent_admin project init-tools <project> --from real-home|empty|<source-project>`
   - `real-home` 只用于迁移起点，不再是 steady-state 的默认目标
3. **seat runtime 改指向 project layer**
   - launcher / resolve 不再回链到 real HOME
   - 只在 `tools_isolation=shared-real-home` 时保留旧路径
4. **验证**
   - `lark-cli auth status`
   - `codex` / `gemini` 的 account ready check
   - iTerm2 socket / plist 存在性
5. **旧 project 兼容**
   - 未迁移的 v0.7 project 先保持 `shared-real-home`
   - 一旦执行 `init-tools` 并验证通过，再切到 `per-project`

### 风险与回滚

| 步骤 | 主要风险 | 回滚策略 |
|---|---|---|
| project tool root 创建 | 把真实账号状态复制错项目，或复制到一半 | 保持 `shared-real-home` 不变，删除 project root 后重试 |
| seat runtime 改链路 | 有 helper 漏掉新 env，出现“半 real-home 半 project-home”混态 | `--dry-run` 和一致性检查先跑，失败时立刻 fallback 到 shared-real-home |
| identity 切换 | 旧 token / 旧 profile 被覆盖 | project-local copy 先于写入发生，real HOME 不做原地修改 |
| iTerm2 seed | plist / socket 互相污染 | project root 只做独立文件，禁止 symlink 回 real HOME |

建议的迁移原则：
- **非破坏性优先**。迁移失败时，旧的 real-home 路径仍可用。
- **显式 opt-in**。`per-project` 只在初始化完成后启用。
- **禁止 self-loop**。project root 和 real HOME 不能互相指向。

## Q4 · API 设计 finalized

### `agent_admin project init-tools`

推荐签名：

```bash
agent_admin project init-tools <project> \
  [--from real-home|empty] \
  [--source-project <project>] \
  [--tools lark-cli,gemini,codex,iterm2] \
  [--dry-run]
```

设计选择：
- `--from real-home|empty` 保留最常见的两种起点。
- `--source-project <project>` 需要保留，原因是“从另一个 project 复制”是和 `real-home` 不同的 operator 意图。
- `--tools` 允许只初始化一部分工具，方便分阶段迁移。
- `--dry-run` 必须有，方便先看计划再落盘。

不建议再加一个单独的 `--shared real-home`。
- 兼容语义应该由 `tools_isolation=shared-real-home` 承担。
- 命令行层面用 `--from real-home` 已经足够明确。

### `agent_admin project switch-identity`

推荐签名：

```bash
agent_admin project switch-identity <project> \
  [--lark-profile <profile>] \
  [--lark-as user|bot|auto] \
  [--gemini-account-email <email>] \
  [--codex-account-email <email>] \
  [--dry-run]
```

语义：
- `lark-cli` 走 profile 切换，`--as` 只管 sender persona。
- `gemini` / `codex` 走 project-scoped 账号标记，必要时触发 project-local 重新初始化。
- 这个命令是 project-level orchestration，不是单纯改一个 config 文件。

输出建议：
- 成功时打印 `old -> new` identity 摘要。
- 如果只改了 lark profile，但 project-local 目录已经正确，则提示 “profile updated, no re-seed needed”。
- 如果需要重新登录或复制 token，明确打印下一步命令，而不是静默继续。

## Q5 · PROJECT_BINDING schema v3

当前这条线的 binding 还是 v1，字段只有 Feishu group / bot / mention-gate。v3 的升级建议是：

```toml
version = 3

project = "install"
feishu_group_id = "oc_..."
feishu_group_name = "ClawSeat Squad"
feishu_external = false
feishu_bot_account = "koder"
require_mention = false
bound_at = "..."
bound_by = "..."

# v3 新增
gemini_account_email = "..."
codex_account_email = "..."
tools_isolation = "per-project"  # or "shared-real-home"
```

### 字段语义

| 字段 | 语义 | 默认值 / 兼容 |
|---|---|---|
| `gemini_account_email` | 这个 project 的 Gemini 账号标识 | 空字符串，表示仍沿用旧 shared-real-home 或未初始化 |
| `codex_account_email` | 这个 project 的 Codex 账号标识 | 空字符串，表示仍沿用旧 shared-real-home 或未初始化 |
| `tools_isolation` | project 的 user-tool 存储模式 | 缺省视作 `shared-real-home`，旧 project 不会立刻断掉 |

### 兼容性矩阵

| binding 状态 | 行为 |
|---|---|
| v1 / 无 `tools_isolation` | 视为 `shared-real-home` |
| `tools_isolation = "shared-real-home"` | 保持旧行为，继续回链到 real HOME |
| `tools_isolation = "per-project"` | seat runtime 必须使用 project-local tool root |
| 新字段缺省 | 允许，迁移可以分工具推进 |
| 未知 extras | 保留，不可丢弃 |

关键原则：
- 不能把 project identity 绑回 real HOME。
- `ProjectBinding.extras` 的保留语义很重要，未来若再加 Feishu sender 字段，不应该因为这次 schema bump 被擦掉。

## Q6 · memory 边界

推荐结论：**memory 继续保持 machine-level singleton，不要被 project tool layer 绑成某个 project 的代理身份。**

理由：
- `machine.toml` 已经把 memory 设计成 machine-wide singleton。
- memory 的职责是公共记忆和学习记录，不是某个 project 的用户身份代理。
- 如果把 memory 借用某个 project 的 `.lark-cli`，会把一个跨 project 服务和一个 project 的身份耦合起来，后面很难拔。

因此建议：
1. memory **默认不 seed** project-level `.lark-cli` / `.gemini` / `.codex`
2. 如果 memory 未来真的需要 Feishu 广播，应该给它单独的 **machine-level identity**
3. 不要选“代理 project identity”这种中间态

结论对照：
- **A. memory 不发 lark-cli 消息**：当前最合理，直接 skip
- **B. memory 复用某个 project identity**：不推荐，耦合过强
- **C. memory 自己一份 machine identity**：如果未来必须发 Feishu，这是唯一可持续的路径

## 实现路径建议

按优先级建议拆成这几个 chunk：

1. **先定 schema**
   - `PROJECT_BINDING` 升到 v3
   - 增加 `tools_isolation` 和项目级账号字段
   - 保持未知 extras 不丢
2. **再加 project tool root**
   - 新增 project-scoped tool root helper
   - 把 `runtime_home_links` 的 legacy 共享逻辑留作 fallback
3. **补 `init-tools`**
   - 先支持 `real-home` / `empty`
   - 再支持 `--source-project`
4. **改 launcher / resolve**
   - 让 seat runtime 优先吃 project layer
   - 只在 `shared-real-home` 时回退到旧行为
5. **补 `switch-identity`**
   - 让 project identity 的切换成为显式命令
   - lark-cli 走 profile，gemini / codex 走 project-local account metadata
6. **最后做 migration**
   - 旧 project 默认保持兼容
   - 新 project 默认走 `per-project`
   - 加 dry-run 和 rollback 保护

建议同步的测试切片：
- `tests/test_agent_admin_project_init_tools.py`
- `tests/test_agent_admin_project_switch_identity.py`
- `tests/test_launcher_per_project_seed.py`
- `tests/test_v07_to_v08_migration.py`
- `tests/test_multi_identity_isolation.py`

这批测试应该优先覆盖：
- project root 是否真的独立于 real HOME
- lark-cli profile 切换是否只影响 project layer
- gemini / codex 的账号是否不会互相串
- `shared-real-home` fallback 是否仍可用
- memory singleton 是否不会被 project seed 污染
