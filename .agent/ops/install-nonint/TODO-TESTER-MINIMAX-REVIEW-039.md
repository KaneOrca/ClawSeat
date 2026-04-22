# TODO — REVIEW-039 (codex 4 份代码的独立 review)

```
task_id: REVIEW-039
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: REQUIRED — 4 parallel subagents (A/B/C/D)
do-not-modify: read-only code review
```

## Context

Codex 在最近几批任务里交付了 4 份未 commit 的代码。用户希望在整合进 v0.7 flow 前，由 minimax（独立第二视角）做一轮 review。目标：发现 bug、安全问题、约束违反、边界 case 漏测、或与 planner 定下的 v0.7 范式矛盾。

**v0.7 核心范式回顾**（审时参考）：
- operator ↔ ancestor = **CLI 直接交互**
- 飞书 = **write-only 广播** + **可选 koder 反向通道**
- OpenClaw 路径 = **动态发现**（不硬编码 `~/.openclaw/`）
- 幂等 / `set -euo pipefail` / stderr 错误打 `ERR_<CODE>` 便于上层捕获
- 脚本失败**不能**阻塞 Claude Code 关闭流程（hook 尤其）
- 不能引入 dead-pipe / 静默失败而无日志

---

## Subagent A — `scripts/install.sh`（247 行）

目标文件：[scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh)

重点检查：

1. **幂等性**：重复跑会不会炸？tmux session 已存在怎么处理？文件已存在怎么处理？
2. **错误处理**：每一步失败是否有清晰 `ERR_<CODE>` 到 stderr？还是静默吞了？
3. **硬编码路径**：有没有残留 `~/.openclaw/` / `~/.agents/` 之类硬编码该改成从 env/config 读的？（`$HOME` 是合法的；硬编码 `/Users/ywf/` 绝对路径才是 bug）
4. **iTerm driver 调用契约**：`iterm_panes_driver.py` 是 stdin JSON，调用方式是否正确？
5. **provider 选择分支**：无 credentials 分支的 prompt 是否简洁（两行：base_url + api_key）？
6. **dry-run 模式**：是否每一步都走 dry-run 打印而不真跑？
7. **3-Enter flush 时序**：sleep 时间够不够 claude 进程 settle？
8. **与 DRAFT-INSTALL-v07.md 和 docs/INSTALL.md 的一致性**：流程编号对得上吗？

产出：`[install.sh][bug|risk|nit]` 分级清单，每项附行号 + 原文 + 建议。

---

## Subagent B — `scripts/apply-koder-overlay.sh`（274 行）

目标文件：[scripts/apply-koder-overlay.sh](/Users/ywf/ClawSeat/scripts/apply-koder-overlay.sh)

重点检查：

1. **destructive 覆盖的安全性**：确认 `--on-conflict backup` 在所有被改文件上生效？有没有漏给某个文件加备份？
2. **`list_openclaw_tenants()` 空列表的处理**：fresh 机器上为空时怎么回退？
3. **用户确认 prompt 的逃逸路径**：按 Ctrl-C 会不会留半成品？
4. **`--dry-run` 模式的真实性**：dry-run 里自动选第一个 tenant 的行为会不会让人误以为真装了？
5. **Python subprocess 调用的异常路径**：`init_koder.py` / `configure_koder_feishu.py` 失败时 overlay 状态是不是半成？
6. **幂等性**：重复跑会不会覆盖已装 koder？应该怎么提示？
7. **tests/test_apply_koder_overlay.py 的覆盖**：3 个测试是否真覆盖主要路径？有没有明显漏的 case？

---

## Subagent C — `core/scripts/bootstrap_machine_tenants.py` + 相关（SCAN-034 产出）

目标文件：
- [core/scripts/bootstrap_machine_tenants.py](/Users/ywf/ClawSeat/core/scripts/bootstrap_machine_tenants.py)
- [core/lib/openclaw_home.py](/Users/ywf/ClawSeat/core/lib/openclaw_home.py)
- [core/skills/memory-oracle/scripts/scan_environment.py](/Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/scan_environment.py) (只看 `scan_openclaw()` 和 `_discover_openclaw_home()`)

重点检查：

1. **OpenClaw home 发现三级链**是否按设计（env → CLI → fallback）？CLI 超时/异常处理？
2. **agents 字段枚举**：`workspace-*` 和直名目录的兼容是否有遗漏？.DS_Store / 其他非 agent 目录会不会误报？
3. **bootstrap 幂等**：已有 tenant 真不覆盖吗？workspace 被删了但 machine.toml 里还有咋办？
4. **并发安全**：多个 seat 同时跑 bootstrap 会不会破坏 machine.toml？
5. **测试覆盖**：9 个测试是否真覆盖关键路径？`_discover_openclaw_home` 的 fallback 链测了吗？

---

## Subagent D — MEMORY-035 产出

目标文件：
- [scripts/hooks/memory-stop-hook.sh](/Users/ywf/ClawSeat/scripts/hooks/memory-stop-hook.sh) (198 行)
- [core/skills/memory-oracle/scripts/install_memory_hook.py](/Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/install_memory_hook.py) (112 行)

重点检查：

1. **Stop-hook 协议**：codex 说用 stdin JSON + `transcript_path` 字段，这和 `~/.claude/settings.json` 里已有的样例是否一致？用 `cat ~/.claude/settings.json` 和 `cat /Users/ywf/.pixel-agents/hooks/claude-hook.js` 对照确认
2. **`set -euo pipefail` + `|| true` 的搭配**：hook 失败真不会阻塞 Claude Code 关闭流程吗？
3. **正则 parse `[DELIVER:seat=X]`**：边界 case（多个 marker / marker 在代码块里被误匹配）有没有漏？
4. **`tmux send-keys /clear` 的时序**：sleep 0.5 够不够？会不会打断正在渲染的消息？
5. **auto-deliver 的 fallback**：只有 seat 没有 task_id 时走哪条路？是否有 silent-fail 风险？
6. **install 幂等**：重复装同一个 hook 会不会把 settings.json 里加好几份？
7. **测试覆盖**：4 个测试（clear / deliver / no-marker / tmux-fail）是否真覆盖关键路径？

---

## 产出

写 `DELIVERY-REVIEW-039.md`：

```
task_id: REVIEW-039
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话：共 N 个 bug / M 个 risk / K 个 nit>

## Subagent A — install.sh review
[install.sh:<line>][bug|risk|nit] <desc> + <建议>

## Subagent B — apply-koder-overlay.sh review
<同上>

## Subagent C — bootstrap_machine_tenants.py + SCAN-034 review
<同上>

## Subagent D — memory-stop-hook.sh + install_memory_hook.py review
<同上>

## 总评级
- 可否直接 commit / 需要几个 fix / 需要重做
- 最高优先级 top 3 必须修的项

## v0.7 范式一致性检查
- 每份代码和 v0.7 范式哪些地方矛盾（若有）
```

完成后通知 planner: "DELIVERY-REVIEW-039 ready"。
