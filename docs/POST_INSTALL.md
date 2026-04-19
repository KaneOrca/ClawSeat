# 装完之后怎么用

这份文档只覆盖 canonical OpenClaw 首装（`~/.clawseat` + `~/.openclaw`）装完之后的日常使用。首装本身见 [INSTALL_GUIDE.md](INSTALL_GUIDE.md)。

---

## 日常启动顺序

OpenClaw 前台会自动挂载 `~/.openclaw/workspace-koder`——你一进 OpenClaw 就是 koder。后端 seats (planner / builder-1 / reviewer-1) 只在被派任务时才需要起。

典型日常：

```bash
# 1. 进入 OpenClaw（koder 已就绪，无需额外命令）
openclaw

# 2. koder 会按需派活，planner 若未启动则 koder 会提示你：
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "$HOME/.agents/profiles/install-profile-dynamic.toml" \
  --seat planner --confirm-start

# 3. 看当前 seat 状态
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py" \
  --profile "$HOME/.agents/profiles/install-profile-dynamic.toml"
```

> 说明：`start_seat.py` 对非 frontstage seat 会先打印 launch summary，你要再跑一次带 `--confirm-start` 才真正启动。这是防误启。

---

## 看 seat 在做什么

每个 materialized seat 的 session 都挂在 tmux 下，名字是 `<project>-<seat>`：

```bash
# 列出 install 项目的所有 seat session
tmux list-sessions | grep '^install-'

# 贴到某个 seat 里看
tmux attach -t install-planner   # Ctrl-b d 脱附

# 只读最近输出，不 attach
tmux capture-pane -pt install-planner -S -200
```

---

## 停止 / 重启 seat

```bash
# 停一个 seat（会保留 workspace 和 TODO/DELIVERY 历史）
tmux kill-session -t install-planner

# 再拉起来（runtime 保留上次配置）
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "$HOME/.agents/profiles/install-profile-dynamic.toml" \
  --seat planner --confirm-start
```

热恢复：停 seat 后 workspace 仍在 `~/.agents/workspaces/install/planner/`、session record 仍在 `~/.agents/sessions/install/planner.json`，重启只是重挂 runtime。

---

## 切 provider / 换 backend tool

配置写在 `install-profile-dynamic.toml` 的 `[seat_overrides.<seat>]`，默认留空表示未配置（会卡 configuration gate）。

```bash
# 例子：把 planner 从 codex 切到 claude，auth 仍 oauth
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "$HOME/.agents/profiles/install-profile-dynamic.toml" \
  --seat planner \
  --tool claude \
  --auth-mode oauth \
  --provider anthropic \
  --confirm-start
```

`start_seat.py` 会覆盖 profile 中该 seat 的 tool/auth_mode/provider 并持久化，下次无参启动就延续新配置。

常见 provider 值：
- `tool=claude` — provider 通常是 `anthropic` 或 `zhipu-claude`（参考你的密钥来源）
- `tool=codex` — provider 通常是 `openai` 或 `xcode-best`
- `tool=gemini` — provider 通常是 `google`

---

## 如果卡在 configuration gate

首装最后会打出：

```
planner_config_required:
  planner 尚未完成显式 tool/auth/provider 配置，所以首装停在 configuration gate。
next_step:
  python3 ".../start_seat.py" --profile ... --seat planner --tool <...> --auth-mode <...> --provider <...> --confirm-start
```

照 `next_step` 那行填上你的 tool/auth/provider 跑一遍就过了。gate 只针对 **首次** 必须显式确认 backend runtime，之后不会再问。

---

## 看日志 / 定位卡住

每个 seat 的核心日志就在 tmux session 里，再加两个集中位置：

| 文件 | 内容 |
|------|------|
| `~/.agents/sessions/<project>/<seat>.json` | session 记录（workspace、runtime、状态时间戳） |
| `~/.agents/tasks/<project>/<seat>/TODO.md` | 当前任务 inbox |
| `~/.agents/tasks/<project>/<seat>/DELIVERY.md` | 完成回执 |
| `~/.agents/workspaces/<project>/<seat>/` | seat 的工作区（skills / runtime home） |
| `~/.openclaw/workspace-koder/WORKSPACE_CONTRACT.toml` | koder 自己的合约（project / profile / backend_seats） |

快速确认"一切都有在动"：

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py" \
  --profile "$HOME/.agents/profiles/install-profile-dynamic.toml" --json
```

关注输出里的 `seat_sets`、`heartbeat`、`patrol` 三块。

---

## 修复 / 自愈

按影响面从小到大：

```bash
# 1. 只刷 workspace 生成物（IDENTITY/SOUL/AGENTS/TOOLS/MEMORY/CONTRACT）
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py"

# 2. 只修 skill symlink 漂移（~/.openclaw/skills 指向错了）
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_openclaw_bundle.py"

# 3. 只跑诊断 preflight（不自动修）
python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw

# 4. 带自动修
python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw --auto-fix

# 5. 全量重跑首装（幂等，安全）
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py"
```

`openclaw_first_install.py` 是幂等的：workspace 已存在时走 refresh 分支，symlink 对的时候只打印 `already_installed`。

---

## 升级 ClawSeat 代码后

```bash
cd ~/.clawseat && git pull
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py"
```

升级后一律建议过一遍 canonical 总入口。symlink 指向的就是 `~/.clawseat`，代码 pull 下来之后所有 seat 自然用新版。

---

## 参考

- [INSTALL_GUIDE.md](INSTALL_GUIDE.md) — 首装 quickstart 和依赖分级
- [RUNTIME_ENV.md](RUNTIME_ENV.md) — env 变量、目录职责、checkout 漂移判断
- [INSTALL.md](INSTALL.md) — path contract、profile placeholders、role-first 约定
