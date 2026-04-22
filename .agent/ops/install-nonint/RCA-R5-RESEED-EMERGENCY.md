## 调研结论

### Q1: R5 bug 根因（文件名+行号+代码片段）

**直接根因**不是 `session_reseed_sandbox()` 本身，而是 launcher 里 `seed_user_tool_dirs()` 在 `HOME` 已经被切到 real HOME 时继续执行了“把 real HOME 目录备份后再 symlink 回 src”的逻辑。

证据：

- [`/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh:1005-1008`](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh) 的 `run_claude_runtime()` legacy OAuth 分支：
  ```bash
  export HOME="$REAL_HOME"
  seed_user_tool_dirs "$HOME"
  ```
- [`/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh:1127-1130`](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh) 的 `run_codex_runtime()` ChatGPT 分支：
  ```bash
  export HOME="$REAL_HOME"
  export CODEX_HOME="$REAL_HOME/.codex"
  seed_user_tool_dirs "$HOME"
  ```
- [`/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh:1205-1209`](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh) 的 `run_gemini_runtime()` OAuth 分支：
  ```bash
  export HOME="$REAL_HOME"
  seed_user_tool_dirs "$HOME"
  prepare_gemini_home "$HOME" "$workdir"
  ```
- [`/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh:815-838`](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh) 的 `seed_user_tool_dirs()`：
  ```bash
  local runtime_home="$1"
  if [[ "$runtime_home" == "$REAL_HOME" ]]; then
    return 0
  fi
  ...
  backup_base="$runtime_home/.sandbox-pre-seed-backup"
  ```
  这个 guard 是当前补上的防线；事故发生时的缺口就是这里没有拦住 `runtime_home == REAL_HOME`。

`agent_admin_session.py` 里的 `seed_user_tool_dirs()` 也是同一类逻辑源头，但它本身是给 sandbox runtime 用的，正常调用路径会把 `runtime_home` 指向 `.../.agent-runtime/.../home`，不是 real HOME。

相关命令路径：

- [`/Users/ywf/ClawSeat/core/scripts/agent_admin_commands.py:43-69`](/Users/ywf/ClawSeat/core/scripts/agent_admin_commands.py) `session reseed-sandbox`
- [`/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py:523-528`](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py) `reseed_sandbox_user_tool_dirs()`
- [`/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py:550-558`](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py) `start_engineer()` 内部自动 reseed

结论：

- **触发 real HOME damage 的直接路径**是 launcher 的 OAuth / ChatGPT 分支调用 `seed_user_tool_dirs "$HOME"`，而不是 `session reseed-sandbox --all` 本身。
- `session reseed-sandbox --all` 是相邻暴露面：它调用的是同一类 seed helper，但在正常 session runtime 下应指向 sandbox home。
- `backup_base` 用的是 `runtime_home/.sandbox-pre-seed-backup`，因此一旦 `runtime_home` 错指 real HOME，备份目录就会落到 `/Users/ywf/.sandbox-pre-seed-backup/`，和现场症状一致。

### Q2: 影响范围（每个 seed 路径状态表）

只读审计结果如下：

| seed 路径 | 当前状态 | 备注 |
|---|---|---|
| `.lark-cli` | `SELF-LOOP` symlink | `readlink` 指向自身：`/Users/ywf/.lark-cli -> /Users/ywf/.lark-cli` |
| `Library/Application Support/iTerm2` | normal directory | 当前是普通目录，不是 symlink；现场未见 self-loop |
| `Library/Preferences/com.googlecode.iterm2.plist` | `SELF-LOOP` symlink | `readlink` 指向自身 |
| `.config/gemini` | missing | 当前不存在 |
| `.gemini` | `SELF-LOOP` symlink | `readlink` 指向自身 |
| `.config/codex` | missing | 当前不存在 |
| `.codex` | `SELF-LOOP` symlink | `readlink` 指向自身 |

备份目录现状：

- `/Users/ywf/.sandbox-pre-seed-backup/` 存在
- 其中可见：
  - `.lark-cli.1776892959/`
  - `.gemini.1776892959/`
  - `.codex.1776892959/`
  - `Library/`

### Q3: 数据完整性

#### `.lark-cli` 备份是否完整

`/Users/ywf/.sandbox-pre-seed-backup/.lark-cli.1776892959/` 目前可见结构：

- `.lark-cli/`（嵌套子目录，里面只有 `cache/`）
- `cache/`
- `config.json`
- `locks/`
- `logs/`
- `update-state.json`

这说明：

- 备份不是“再备份一次”的产物，而是**原始 `.lark-cli` 目录整体被 move 到 backup** 后保留下来的树。
- 嵌套的 `.lark-cli/` 子目录更像是原始 lark-cli home 内部结构，不是 backup 逻辑额外制造的目录。
- 从当前可见内容看，`config.json` / `cache` / `locks` / `logs` / `update-state.json` 都在，恢复成原样的概率高。

#### `config.json` 的含义

备份里的 `config.json` 内容显示：

- `appId: cli_a96abcca2e78dbc2`
- `brand: feishu`
- `userName: 张根铭`
- `userOpenId: ou_96c83166c9c6eea2797f005d762249fb`

这说明被损坏的是**真实 operator 的 Feishu/lark-cli 客户端身份配置**，不是某个 project sandbox 的临时文件。
从文件本身无法再推导“余文锋 / 张根铭”是否是两个不同的人名；能确认的是，现场保留下来的活跃身份名是 `张根铭`。

#### 其他 seed 路径的数据完整性

- `Library/Application Support/iTerm2` 当前是正常目录，未见 self-loop；备份目录里存在多个时间戳子目录，说明至少做过多次 seed / backup 尝试，但当前 live 路径没有被替换成 symlink。
- `Library/Preferences/com.googlecode.iterm2.plist` 已损坏为 self-loop，但备份文件存在，属于可回收范围。
- `.gemini` 和 `.codex` 都已损坏为 self-loop；各自的 `.sandbox-pre-seed-backup` 副本存在。

### Q4: 3 个修复方案对比

#### A. 直接从 backup 恢复 real HOME 的 `.lark-cli`

**思路**

- 把 `/Users/ywf/.sandbox-pre-seed-backup/.lark-cli.1776892959/` 的内容回填到 `/Users/ywf/.lark-cli/`
- 处理嵌套 `.lark-cli/` 子目录时，按“目录内目录”合并，而不是把整个备份目录再套一层

**优点**

- 数据保真度最高
- 现有 `config.json` / cache / logs / history 之类可以原样回收

**风险**

- 如果 backup 里还有未列出的隐藏状态，合并时可能覆盖当前临时状态
- 若操作顺序不对，可能把 self-loop 保持到恢复路径里

**回滚**

- 恢复前先把当前 self-loop symlink 挪到临时保留位
- 如果合并后状态异常，直接把保留位再放回去，回到事故现场

#### B. 不动 backup，重新 `lark-cli auth login`

**思路**

- 让 operator 重新登录，重新生成 real HOME 的 lark-cli 状态

**优点**

- 最保守
- 不依赖备份里是否还有遗漏

**风险**

- 可能丢失 local cache / history / 旧 auth state
- 需要 operator 重新完成登录与验证

**回滚**

- 先保留 backup 和当前 self-loop，登录失败时仍可回到方案 A

#### C. 混合方案

**思路**

- 先只恢复最关键的身份/配置文件，再让 operator 对缺失项重新登录补齐
- 对 `.lark-cli` 目录做选择性合并，而不是整棵树盲恢复

**优点**

- 比 B 保留更多历史数据
- 比 A 更容易控制风险

**风险**

- 需要人为判断哪些文件该回填、哪些该重新生成
- 操作分支更多，容易漏项

**回滚**

- 所有恢复动作都必须先保留当前 self-loop 和 backup 原件，必要时退回 A 或 B

### Q5: hotfix 代码草稿

#### 1) 最该放 guard 的位置

**主 guard：`core/launchers/agent-launcher.sh` 的 `seed_user_tool_dirs()`**

原因：

- 这是唯一会在 `HOME="$REAL_HOME"` 场景下继续做 seed 的生产路径
- 事故的真正触发点就是 launcher 分支调用了这段函数
- guard 应该放在“开始遍历 seeds 之前”，避免 backup / move / symlink 的任何副作用

建议形态：

```bash
if [[ "$runtime_home" == "$REAL_HOME" ]]; then
  return 0
fi
```

#### 2) 是否还要在 Python `seed_user_tool_dirs()` / handler 里加 guard

**要，加，但作为 defense-in-depth，不是主防线。**

建议在 [`/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py:123-157`](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py) 里增加：

```python
if runtime_home.resolve() == real_home.resolve():
    return []
```

理由：

- `session reseed-sandbox` 和 `start_engineer` 最终都会复用同一个 helper
- 如果将来某个 session 的 runtime 解析错成 real HOME，Python 侧也能直接挡住

#### 3) 其他边界条件

- `CLAWSEAT_REAL_HOME` 设错时，任何比较都会失真；需要把它当作最高优先级事实源，但一旦 `runtime_home` 和 `real_home` 解析后相同，就必须跳过 seed
- `AGENT_HOME` / `Path.home()` 作为回退项，若在 sandbox shell 里被误设，会把“real”与“sandbox”对调；因此比较必须用解析后的绝对路径，不要只做字符串前缀判断
- 若 home 本身是 symlink，比较应使用 resolved path，而不是字面路径

## 建议（planner 决策时参考）

1. 先把当前 self-loop 的影响面定死：`.lark-cli`、`.gemini`、`.codex`、`com.googlecode.iterm2.plist` 都已经被同一类 seed 逻辑触达，iTerm2 目录当前未见 self-loop。
2. 恢复优先级上，`A` 是最值得先评估的方案，因为 backup 看起来完整且能保留现有身份缓存。
3. 代码层面，launcher 的 `seed_user_tool_dirs()` 应继续保留 real-home guard；Python helper 也建议同步加 resolved-path guard，避免未来新的 session 入口再打穿。
4. 在这个 RCA 结论出来之前，不建议继续扩大 R7-R13 的交付范围，先让 planner 选择恢复策略。
