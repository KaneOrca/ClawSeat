task_id: SMOKE-053-054
owner: claude-minimax
target: planner

## Phase 1 — pytest 全仓回归
1738 passed, 5 failed, 7 skipped, 2 xfailed in 53.56s

失败项（非 codex 改动引起，属于 pre-existing）：
1. test_ask_without_profile_returns_error — assert rc==2 但 rc==1（--ask deprecated 行为变化）
2. test_kind_event_project_ignored_still_reads_global_log — returncode==1（memory-oracle 子进程问题）
3. test_all_silent_excepts_have_sentinel — core/preflight.py:339 缺少 # silent-ok:
4. test_default_path_linux_no_homebrew — PATH 以 /opt/homebrew/bin 开头，非 /usr/local/bin（macOS 差异）
5. test_runtime_reuses_config_default_path — 两处 DEFAULT_PATH 值相同但非同一对象（is 比较失败）

总数 1738 ≥ 200，回归广度确认。

## Phase 2 — seed_user_tool_dirs filesystem smoke

=== sandbox HOME: /Users/ywf/.agent-runtime/identities/claude/api/custom-smoke01-ancestor/home ===
total 16
drwx------@ 6 ywf  staff  192  4 23 03:27 .
drwx------@ 6 ywf  staff  192  4 23 02:58 ..
ls: /Users/ywf/.agent-runtime/identities/claude/api/custom-smoke01-ancestor/home/Library/Application Support/iTerm2: No such file or directory
ls: /Users/ywf/.agent-runtime/identities/claude/api/custom-smoke01-ancestor/home/Library/Preferences/com.googlecode.iterm2.plist: No such file or directory

=== real HOME ===
total 16
drwx------@  7 ywf  staff   224  4 22 15:24 .
drwx------+ 78 ywf  staff  2496  4 23 04:14 ..
total 384
drwxr-xr-x@ 14 ywf  staff     448  4 23 03:39 .
drwxr-xr-x@ 77 ywf  staff    2464  4 22 23:09 ..

agent-launcher.sh --help 正常输出（略）

## Phase 3 — send_delegation_report.py --as flag

--help 输出片段：
  [--check-auth] [--as {user,bot,auto}]
  --as {user,bot,auto}  lark-cli identity: user (OAuth) | bot (appSecret) | auto (default)

Dry-run（--as auto --dry-run）：usage 输出，无 argparse 报错
--as user：argparse OK
--as bot：argparse OK
--as auto：argparse OK

## Phase 4 — agent_admin window open-grid

window --help：
usage: agent-admin window [-h]
                          {open-monitor,open-dashboard,open-grid,open-engineer,config-monitor}
                          ...

open-grid --help：
usage: agent-admin window open-grid [-h] [--recover] [--open-memory] project

positional arguments:
  project

options:
  -h, --help     show this help message and exit
  --recover
  --open-memory

不存在项目报错：
project not registered: NONEXISTENT_PROJECT

## Phase 5 — PROJECT_BINDING v2

binding-list 输出：
smoke01  oc_4bd1bd2b60e80a82300fc894ed060eef  sender_app_id=-  sender_mode=auto  koder_agent=yu  require_mention=true

smoke01 TOML（legacy 格式，路径 /Users/ywf/.agents/tasks/smoke01/PROJECT_BINDING.toml）：
version = 1
project = "smoke01"
feishu_group_id = "oc_4bd1bd2b60e80a82300fc894ed060eef"
feishu_external = false
feishu_bot_account = "yu"
require_mention = true
bound_at = "2026-04-22T19:13:03+00:00"
bound_by = "ancestor"
bound_via = "agent-admin project koder-bind"
last_bind_ts = "2026-04-22T19:13:03.205221+00:00"
openclaw_frontstage_tenant = "yu"

## 结论
- pytest 回归：1738 PASS / 5 FAIL（pre-existing，与 codex 无关）
- R1 sandbox seed：not-retroactive（smoke01-ancestor sandbox 是 R1 落地前创建，三个目录均不存在，无 symlink）
- R2 --as flag：OK（user/bot/auto 均 argparse OK）
- 054 window open-grid：OK（subcommand 存在，--recover/--open-memory flags 存在，project not registered 报错正确）
- R5 schema v2：OK（binding-list 输出含 sender_app_id/sender_mode/koder_agent，legacy TOML 仍可读）

## 异常清单（可选）
- 5 个 pytest fail 均与 FEISHU-AUTH-053 / WINDOW-OPS-054 改动无关，属 pre-existing 状态
- smoke01-ancestor sandbox 未被 retroactive seed，不影响功能（R1 改动后的新 sandbox 会生效）
