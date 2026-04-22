task_id: DEADREF-036
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 0 处残留 — experimental 工作区 clean，无运行时死引用。

## 扫描结果

**所有命中均在 `.agent/ops/install-nonint/` 内部文件**（research TODO 和 delivery 报告本身），非运行时代码。

| 命中位置 | 性质 | 判断 |
|---------|------|------|
| `TODO-TESTER-MINIMAX-DEADREF-036.md` | grep 命令本身（搜索串在 TODO 里） | C) 误报 |
| `DELIVERY-INST-RESEARCH-022.md` | 报告正文中描述 agent-monitor 删除事件 | B) 文档引用（非运行时） |
| `DELIVERY-AUDIT-027.md` | 同上，报告正文中描述 | B) 文档引用（非运行时） |

**核心代码 / 脚本 / 配置文件中：0 处残留。**

---

## 建议

- **A 类（真死引用）**：无，无需修复。
- **B 类（文档引用）**：无需本次处理 — DELIVERY-INST-RESEARCH-022.md 和 DELIVERY-AUDIT-027.md 中的引用是研究任务的报告正文，属于交付记录，不是需要清理的运行时文档。
- **C 类（误报）**：grep 命令串本身在 TODO 文件中，已排除。

---

## 结论

**CLEAN** — SWEEP-023 删除的 `agent-monitor/` 目录（包括 `screenshot-to-feishu.sh`、`msg_focus.sh`、`msg_paste.sh`、`msg_send.sh`、`tmux-send-delayed.sh`）没有任何残留硬编码路径指向它们。真实文件 `core/shell-scripts/send-and-verify.sh` 仍完好存在。
