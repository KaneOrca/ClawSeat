# ClawSeat Install Notes

这份文档保留安装期的路径约定和 profile contract；面向用户的首装步骤请看 [INSTALL_GUIDE.md](INSTALL_GUIDE.md)，装完之后的日常使用请看 [POST_INSTALL.md](POST_INSTALL.md)，面向维护者的运行时契约请看 [RUNTIME_ENV.md](RUNTIME_ENV.md)。

## Canonical Path Contract

OpenClaw 首装的 canonical checkout 固定为：

```sh
export CLAWSEAT_ROOT="$HOME/.clawseat"
```

首装总入口固定为：

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py"
```

## Portable Profile Paths

Profile 文件中允许两种可移植占位符：

- `{CLAWSEAT_ROOT}`: ClawSeat 仓库根目录
- `~`: 当前用户 home

展开规则：

- `{CLAWSEAT_ROOT}` 由 `core/skills/gstack-harness/scripts/_common.py` 展开
- `~` 由 Python `Path.expanduser()` 展开

## Role-First Bootstrap

新项目继续采用 role-first seat ids：

- `koder`
- `planner`
- `builder-1`
- `reviewer-1`

对于 canonical `install` profile，当前 shipped 配置是：

```toml
[dynamic_roster]
enabled = true
materialized_seats = ["koder", "planner", "builder-1", "reviewer-1"]
bootstrap_seats = ["koder"]
default_start_seats = ["koder", "planner"]
compat_legacy_seats = false
```

语义区分：

- `seats`: 完整 roster
- `materialized_seats`: bootstrap 后应已有 session/workspace scaffold 的 seats
- `bootstrap_seats`: 兼容/frontstage bootstrap intent 字段
- `default_start_seats`: frontstage 默认优先启动建议

## Local Runtime Note

本地 Claude Code / Codex 仍然支持 `/cs`，但它是 post-install convenience path，不是 OpenClaw 首装主路径。
