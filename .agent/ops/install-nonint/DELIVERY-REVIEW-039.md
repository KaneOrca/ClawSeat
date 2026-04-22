task_id: REVIEW-039
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 共 4 bugs / 11 risks / 9 nits — 全部需要 fix，无一可直 commit；memory-stop-hook shebang 为 fatal。

## Subagent A — install.sh review

**[install.sh:228][bug] `tmux send-keys` failures silently swallowed**
- 原文: `run tmux send-keys -t "=$PROJECT-ancestor" Enter; run sleep 0.5; run tmux send-keys ...`
- 建议: `send-keys` 不在 `run` 的 `|| die 99` 保护内，若 tmux session 不存在则静默失败。应用 `run` 包装，或在 `send-keys` 后加 `|| true` 并记录日志。

**[install.sh:233][bug] `focus_iterm_window` subshell `|| die` 只退出子 shell，不退出父进程**
- 原文: `$PYTHON_BIN - "$1" "$2" <<'PY' || die 41 ITERM_FOCUS_FAILED "..."`
- 建议: here-doc `<<'PY'` 在子 shell 中运行，`die` 只退出子 shell，父进程继续执行。修复：显式检查 `$?` 或将 here-doc 包装在函数中并检查返回值。

**[install.sh:220][nit] `tmux attach` 用 `=%s-ancestor` 前缀但 `recreate_session` 用 `$name` 不加前缀**
- 原文: `grid_payload()` 中 `tmux attach -t '='%s-ancestor''` vs `recreate_session` 中 `tmux new-session -s "$name"`
- 建议: 验证 `tmux new-session -s "$PROJECT-ancestor"` 和 `tmux attach -t =$PROJECT-ancestor` 解析到同一 session。`=` 前缀是 tmux socket 路径格式，若 session 名不含特殊字符则实际等价，但建议统一。

**[install.sh:171-177][nit] dry-run 中 `run tmux kill-session` 打印 `[dry-run]` 后返回 0**
- 原文: `run` 函数在 DRY_RUN=1 时只打印不执行，这是预期行为
- 建议: 无严重问题，但建议在 dry-run 输出中明确标注"此步骤不会创建 session"。

**[install.sh:228][nit] 3-Enter flush 使用 `Enter` 字面量**
- 原文: `tmux send-keys ... Enter`
- 建议: 使用 `C-m` 显式表示回车，并加注释说明 3-Enter flush 合约。

### v0.7 范式冲突

1. **Step 编号不匹配**: install.sh 有 Steps 1-9，但 DRAFT-INSTALL-026.md（SSOT）是 3 步流程，造成文档漂移。
2. **Provider prompt 顺序**: v0.7 要求"两行（base_url + api_key）"，脚本先问 base_url 再问 api_key，顺序反了。
3. **硬编码 session 名**: `machine-memory-claude` 等硬编码，非动态发现（但对 tmux session 而言这是正常设计）。

### Verdict

**[REWORK]** — 2 个 bug 必须修（send-keys 静默失败 + subshell die 不退出父进程），文档漂移需协调。

---

## Subagent B — apply-koder-overlay.sh review

**[apply-koder-overlay.sh:92-100][bug] `sys.path` 成员检查用 Path 字符串比较，实际冗余**
- 原文: `if text not in sys.path: sys.path.insert(0, text)` — `sys.path.insert` 本身会添加，不管是否已在其中
- 建议: 直接无条件 `sys.path.insert(0, str(path))`，去掉冗余检查。

**[apply-koder-overlay.sh:113-121][bug] 同上，第二个 Python inline 脚本**
- 建议: 同上。

**[apply-koder-overlay.sh:156][risk] 空 tenant 列表直接 `die 2` — 无 fresh-machine fallback**
- 原文: `die 2 NO_OPENCLAW_AGENTS "~/.openclaw/ 下未找到可用 OpenClaw agent"`
- 建议: v0.7 要求 fresh-machine fallback。应引导用户运行 `openclaw init` 或提供 bootstrap 路径，而非直接退出。

**[apply-koder-overlay.sh:166-169][risk] dry-run 自动选第一个 tenant 但 banner 不醒目**
- 原文: `printf '[dry-run] auto-selecting [1] %s\n' "$CHOSEN"`
- 建议: 加大 banner：`echo "======================================== [DRY-RUN MODE] ========================================"`

**[apply-koder-overlay.sh:191][risk] Ctrl-C 在确认步骤中导致半成品状态**
- 原文: `read -r -p "确认? [y/N]: " confirm || die 4 ...`
- 建议: 加 `trap` 捕获 SIGINT，在步骤 4 已完成后中断时发出"overlay 为半成品 — 需手动清理"警告。

**[apply-koder-overlay.sh:166-169][risk] 重跑非幂等 — 不警告即覆盖已有 koder**
- 建议: 在 `run_init_koder` 前检测 tenant 是否已有 koder 标记，若有且非 dry-run 则要求 `--force` 或 die。

**[apply-koder-overlay.sh:209][risk] `--on-conflict backup` 未验证备份完整性**
- 建议: `run_init_koder` 成功后验证 `~/.openclaw/` 下是否生成了备份文件，再进入 step 5。

**[apply-koder-overlay.sh:267-269][risk] step 5 失败后 step 6 不执行，但 tenant identity 已被覆盖**
- 原文: `run_init_koder; run_koder_bind; run_feishu_config` 顺序无检查点
- 建议: 任何 step 失败时发出"需要 rollback"错误消息并附手动恢复步骤。

### 测试覆盖缺口

| 缺失 | 说明 |
|------|------|
| 空 tenant 列表 | 未覆盖 `die 2 NO_OPENCLAW_AGENTS` 路径 |
| Feishu 配置 | step 6 从未被真实调用测试 |
| Ctrl-C/SIGINT | 无 trap 测试 |
| 重跑幂等性 | 重复 overlay 无测试 |
| init_koder 部分失败 | 无 rollback 行为测试 |

### v0.7 范式冲突

1. **幂等性违反**: 重跑覆盖已有 koder identity，不警告。
2. **半成品状态风险**: 任意 step 失败无回滚，造成 corrupted state。
3. **stderr/stdout 混淆**: `note` 写 stdout，`err` 写 stderr，dry-run 输出混用可能干扰日志解析。

### Verdict

**[REWORK]** — 幂等性和半成品状态风险为核心缺陷，需修。

---

## Subagent C — bootstrap_machine_tenants.py + openclaw_home.py review

**[openclaw_home.py:57][risk] `.parent` 假设 `openclaw config file` 返回文件而非目录**
- 原文: `return _expand_with_home(lines[-1], anchor).parent`
- 建议: 若 CLI 返回 `~/.openclaw/`（目录），`.parent` 会错误地返回上级目录。需验证或明确约定 CLI 输出格式为文件路径。

**[bootstrap_machine_tenants.py:50-51][risk] `write_machine(cfg)` 无并发保护**
- 原文: `cfg = load_machine()` → 修改 → `write_machine(cfg)`
- 建议: 多 seat 并发运行时 read-modify-write 会相互覆盖。用 `fcntl.flock` 文件锁或写临时文件再 `os.rename()` 原子化。

**[openclaw_home.py:54][nit] `getattr(result, "returncode", 1)` 中的 default 参数冗余**
- 原文: `result is not None and getattr(result, "returncode", 1) == 0`
- 建议: `subprocess.run` 总返回 `CompletedProcess`，`getattr` 的 default 永远不生效，删掉 default 简化代码。

**[bootstrap_machine_tenants.py:48-49][nit] 已删除 workspace 的 tenant 静默累积**
- 原文: `if not workspace.exists(): continue`
- 建议: 发出 `WARN_STALE_TENANT` 警告，与"stderr errors with ERR_" 原则对齐。

### 测试覆盖缺口

`discover_openclaw_home()` 的三级链路（env → CLI → fallback）在 `test_scan_openclaw.py` 中仅间接覆盖，无独立单元测试。

### v0.7 范式冲突

1. **stderr errors 原则**: `workspace.exists()` 返回 False 时静默跳过，无 `WARN_` 输出。
2. **动态发现约定**: `openclaw_home.py` 的 fallback 未明确约定 CLI 输出格式，`.parent` 假设有隐式风险。

### Verdict

**[REWORK]** — `.parent` 假设和并发安全为必须修项。

---

## Subagent D — memory-stop-hook.sh + install_memory_hook.py review

**[memory-stop-hook.sh:1][bug][CRITICAL] shebang 写成 `#!/usr/bin/env python3` 但脚本是 bash**
- 原文: `#!/usr/bin/env python3` — 但文件是 bash 脚本（`set -euo pipefail`、`[[ ]]`、`local` 等 bash 语法）
- 建议: 改为 `#!/usr/bin/env bash`。这是 fatal bug，系统会尝试用 Python3 解释器运行 bash 脚本，第一行 `set -euo pipefail` 在 Python 中立即报 SyntaxError。

**[memory-stop-hook.sh:143][risk] `sleep 0.5` 可能不足以等待长消息渲染完成**
- 原文: `sleep 0.5`
- 建议: 考虑增加到 `sleep 1` 或加轮询确认 tmux 已处理 `/clear`。

**[memory-stop-hook.sh:56][nit] `[DELIVER:...]` 正则单行多 marker 可能误解析**
- 原文: `re.search(r"\[DELIVER:([^\]]+)\]", combined)`
- 建议: 同一行有多个 `[DELIVER:...]` 时，`[^\]]+` 会跨 marker 匹配。改用 `re.findall` 取所有 marker，再逐个解析。

**[memory-stop-hook.sh:153-161][risk] auto-deliver fallback 只打 stderr，无 user可见提示**
- 原文: `deliver_skipped: missing task_id...` 仅写到 stderr
- 建议: 同时写日志文件或 stdout，便于事后追溯。

**[install_memory_hook.py:70-83][risk] 幂等性：不同路径的相同 hook 脚本会重复添加**
- 原文: `if not found: stop_entries.append(...)`
- 建议: 用脚本路径的内容哈希做去重 key，而非全 command 字符串匹配。

### v0.7 范式冲突

1. **非阻塞原则**: `|| true; exit 0` 已正确实现，hook 失败不阻塞 Claude Code 关闭。
2. **无静默失败**: `deliver_response` 失败时打 stderr，但 auto-deliver fallback 的 stderr 可能被忽略。

### Verdict

**[REWORK]** — shebang bug 为 fatal，必须立即修。

---

## 总评级

| 文件 | Verdict | 必须修项数 |
|------|---------|-----------|
| install.sh | **REWORK** | 2 bugs + 1 doc drift |
| apply-koder-overlay.sh | **REWORK** | 1 bug + 5 risks |
| bootstrap_machine_tenants.py + openclaw_home.py | **REWORK** | 1 risk + 1 concurrency |
| memory-stop-hook.sh + install_memory_hook.py | **REWORK** | 1 fatal bug |

**无一可直 commit。**

### Top 3 必须修项

1. **`[memory-stop-hook.sh:1]`** — shebang 写成 `python3` 但脚本是 bash，fatal，5 秒可修
2. **`[install.sh:233]`** — subshell 中 `|| die` 只退出子 shell，父进程静默继续，导致 focus 失败被掩盖
3. **`[install.sh:228]`** — `tmux send-keys` 不在 `run` 保护内，失败静默

### v0.7 范式一致性检查

| 原则 | 违反的文件 |
|------|-----------|
| 幂等性 | apply-koder-overlay.sh（重跑覆盖）、bootstrap_machine_tenants.py（无幂等检查） |
| 无半成品状态 | apply-koder-overlay.sh（step 间无 checkpoint/rollback） |
| stderr ERR_<CODE> | bootstrap_machine_tenants.py（stale workspace 静默跳过） |
| 动态发现 | openclaw_home.py（.parent 隐式假设 CLI 输出格式） |
| CLI 直接交互 | install.sh（step 编号与 SSOT doc 不匹配） |
| 非阻塞 | memory-stop-hook.sh（shebang fatal 导致 hook 无法运行） |
