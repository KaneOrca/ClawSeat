# ClawSeat 安装指南

## 支持范围

本轮首装稳定化优先保证：

- macOS
- OpenClaw 首次安装
- canonical checkout 固定为 `~/.clawseat`

旧的任意 checkout 安装方式仍可兼容，但不再是首装主路径。

## OpenClaw 首装 Quickstart

```bash
git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat
export CLAWSEAT_ROOT="$HOME/.clawseat"

python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_openclaw_bundle.py"
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py"
```

`openclaw_first_install.py` 是 canonical 总入口。它会顺序执行：

1. 校验当前 checkout 是否就是 `~/.clawseat`
2. 修复 `~/.openclaw/skills/*` 和 `~/.openclaw/workspace-koder/skills/*` symlink
3. 运行 `python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw --auto-fix`
4. 初始化或刷新 `~/.openclaw/workspace-koder`
5. 确保 `~/.agents/profiles/install-profile-dynamic.toml` 已存在且符合当前 schema
6. bootstrap `materialized_seats`
7. 如果 `planner` 已有显式 `tool/auth_mode/provider`，自动启动 `planner`
8. 如果 `planner` 尚未配置，明确停在 configuration gate 并打印唯一下一步

## 依赖分级

### HARD_BLOCKED

这些缺失时，首装会直接失败并要求先补齐：

| 项目 | 要求 | 安装方式 |
|------|------|----------|
| Python | `>= 3.11` | `brew install python@3.12` |
| tmux | 已安装 | `brew install tmux` |
| Node.js | `>= 22` | `brew install node` |
| OpenClaw CLI | 可执行 | `npm install -g openclaw` |
| backend CLI | `claude` / `codex` / `gemini` 至少一个 | 按 seat runtime 安装 |
| CLAWSEAT_ROOT | OpenClaw 首装必须指向 `~/.clawseat` | `export CLAWSEAT_ROOT="$HOME/.clawseat"` |
| repo integrity | repo 必须包含 ClawSeat 核心文件 | 重新 clone `~/.clawseat` |

### RETRYABLE

这些问题允许自动修复，`--auto-fix` 只负责修这类项：

- tmux server 未启动
- `install-profile-dynamic.toml` 缺失或 schema 过旧
- `~/.openclaw/skills/*` 或 `workspace-koder/skills/*` symlink 漂移
- `~/.openclaw/workspace-koder` 缺文件或 contract 过旧
- `~/.agents/sessions/install` 绑定目录缺失

### WARNING

这些不会阻止首装通过，但会限制后续能力：

- `gstack` 缺失：specialist seats 可物化，但 builder/reviewer/qa/designer 能力受限
- `lark-cli` 缺失：当前未启用飞书桥接时只给 warning
- iTerm2 等可选窗口能力缺失

## Runtime-Aware Preflight

OpenClaw 首装必须用 runtime-aware 模式：

```bash
python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw --auto-fix
```

行为变化：

- 不再逐个对 `claude` / `codex` / `gemini` 全量 warning
- 改成只检查“是否至少存在一个可用 backend CLI”
- seat-specific CLI 在 seat 已配置或即将启动时再精确校验

如果你只想看状态，不自动修复：

```bash
python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw
```

## 首装成功的定义

一个成功的 OpenClaw 首装，至少要满足：

- `~/.openclaw/workspace-koder` 已生成并匹配当前模板
- `~/.agents/profiles/install-profile-dynamic.toml` 已就绪
- `materialized_seats` 的 session / workspace scaffold 已存在
- install console 可正常渲染
- 如果 `planner` 已配置，`planner` 已启动
- 如果 `planner` 未配置，安装流程必须明确停在配置 gate，而不是模糊失败

## Planner 配置 Gate

ClawSeat 仍然保持当前产品策略：backend seat 第一次启动前，必须显式配置 `tool/auth_mode/provider`。

如果 `openclaw_first_install.py` 停在 configuration gate，按它打印的命令执行即可，格式类似：

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "$HOME/.agents/profiles/install-profile-dynamic.toml" \
  --seat planner \
  --tool codex \
  --auth-mode oauth \
  --provider xcode-best \
  --confirm-start
```

## 机器漂移 / 更新后修复

更新 ClawSeat 或怀疑 OpenClaw 还挂在旧 checkout 时，优先重跑 canonical 总入口：

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py"
```

只想刷新 workspace 生成物时：

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py"
```

只想修 skill symlink 时：

```bash
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_openclaw_bundle.py"
```

## 本地 Claude Code / Codex

本地 CLI 仍然支持，但它是次级路径，不是 OpenClaw 首装主路径：

```bash
git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat
export CLAWSEAT_ROOT="$HOME/.clawseat"
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"
```

之后在本地 runtime 中使用 `/cs` 即可。

## 进一步排障

运行时目录、环境变量语义、dev checkout 与 install checkout 漂移判断，见：

- [Runtime Environment](RUNTIME_ENV.md)
- [Install Notes](INSTALL.md)

装完之后的日常使用（启动 / 停止 seat、切 provider、看日志），见：

- [Post-Install](POST_INSTALL.md)
