# ClawSeat Runtime Environment

## 目标

这份文档是维护者和排障用的 runtime contract，解释 OpenClaw 首装链路依赖的环境变量、目录职责，以及“开发 checkout”和“OpenClaw 当前实际加载 checkout”为什么可能不同步。

## 核心环境变量

| 变量 | 作用 | OpenClaw 首装期望值 |
|------|------|---------------------|
| `CLAWSEAT_ROOT` | ClawSeat 仓库根目录 | `~/.clawseat` |
| `HOME` | 当前用户 home | 当前 macOS 用户 home |
| `AGENT_HOME` | 当前 agent 的工作 home | 通常沿用 `HOME`，部分 runtime 会单独设 |
| `AGENTS_ROOT` | ClawSeat 运行时根目录 | 默认 `~/.agents` |
| `OPENCLAW_HOME` | OpenClaw 数据根目录 | 默认 `~/.openclaw` |
| `OPENCLAW_PROJECT` | 当前项目名 | OpenClaw 首装默认 `install` |

## 目录职责

### `~/.clawseat`

- canonical ClawSeat checkout
- OpenClaw 首装唯一保证路径
- `install_openclaw_bundle.py` 和 `openclaw_first_install.py` 默认都应该从这里运行

### `~/.agents`

- `profiles/`: 动态 profile，首装重点是 `install-profile-dynamic.toml`
- `sessions/`: materialized seat 的 session records
- `workspaces/`: backend seats 的 workspace scaffold
- `tasks/`: TODO / DELIVERY / patrol / handoff receipt

### `~/.openclaw`

- `skills/`: OpenClaw 全局 skill symlink 挂载点
- `workspace-koder/`: OpenClaw frontstage koder 的本地工作区
- `workspace-koder/skills/`: koder 自己看到的 skill symlink 集合

## 两套 checkout 为什么会漂

常见现场是同时存在：

- 开发 checkout：例如 `/Users/you/coding/ClawSeat`
- 安装 checkout：`~/.clawseat`

OpenClaw 实际加载哪一套，不取决于你正在改哪套，而取决于 symlink 最终指向哪里：

- `~/.openclaw/skills/clawseat`
- `~/.openclaw/skills/clawseat-install`
- `~/.openclaw/skills/gstack-harness`
- `~/.openclaw/workspace-koder/skills/*`

如果这些 symlink 还指向旧 checkout，OpenClaw 现场就会继续跑旧代码，即使你的开发 checkout 已经修好了。

## 如何判断 OpenClaw 当前在用哪套 ClawSeat

### 1. 看 skill symlink

```bash
ls -l ~/.openclaw/skills/clawseat
ls -l ~/.openclaw/skills/clawseat-install
ls -l ~/.openclaw/workspace-koder/skills/gstack-harness
```

期望都指向 `~/.clawseat/...`

### 2. 看 koder workspace contract

```bash
cat ~/.openclaw/workspace-koder/WORKSPACE_CONTRACT.toml
```

这里至少应该包含：

- `project = "install"`
- `profile = "~/.agents/profiles/install-profile-dynamic.toml"` 的展开结果
- `backend_seats`
- `default_backend_start_seats`

### 3. 看 console seat sets

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py" \
  --profile "$HOME/.agents/profiles/install-profile-dynamic.toml" \
  --json
```

重点观察 `seat_sets`：

- `roster`
- `materialized`
- `bootstrap`
- `default_start`
- `backend`

OpenClaw frontstage 里，`backend` 不应包含 `koder`。

## 首装关键脚本的 import 约定

本轮之后，首装关键链路不再依赖隐藏的全局 `PYTHONPATH` 注入作为主机制。

期望约定：

- 优先 `from core...`
- 脚本态先通过 `core._bootstrap` 建立 repo root / core import 路径
- 不再新增 `sys.path.insert(.../core)` 后直接 `from resolve import ...` 这种旧式写法

仍然允许的例外：

- `gstack-harness/scripts/_common.py` 这类非 package 路径，必要时显式加脚本目录或通过文件加载

## 自愈入口

### 全量自愈

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py"
```

### 只修 skill bundle

```bash
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_openclaw_bundle.py"
```

### 只跑 runtime-aware preflight

```bash
python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw --auto-fix
```

### 只刷新 workspace 生成物

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py"
```

## 维护建议

- OpenClaw 首装问题优先在 `~/.clawseat` 复现和验证，不要默认在开发 checkout 上修完就算结束
- 对外文档和 skill 说明都应指向 `openclaw_first_install.py`
- 如果未来要彻底废掉旧路径约定，优先继续收敛到 `core._bootstrap` / `core.resolve`
