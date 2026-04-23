# DELIVERY — FEISHU-ASCII-ONLY-FIX
时间: 2026-04-23T22:30:00Z
作用域: 4 files in core/skills/gstack-harness/scripts/

## 替换摘要
| 文件 | 替换行数 | 说明 |
|---|---|---|
| complete_handoff.py | ~10 | 翻译了 Feishu 广播消息，移除非 ASCII 箭头/Section 符号 |
| dispatch_task.py | ~15 | 翻译了 Feishu 广播消息，将所有 Trigger 中的非 ASCII 符号替换为 ASCII |
| _common.py | ~20 | 翻译了 render_idle_todo 中的所有 title/objective |
| patrol_supervisor.py | ~30 | 翻译了所有巡检提醒、经验记录和 Blockage 指导消息 |

- grep: 0 行代码内残留在代码中的中文（仅余 1 行注释在 dispatch_task.py:84）
- pytest (相关模块): 172 passed, 0 failed, 1650 deselected

## 已知风险
- 无。所有修改均经过 pytest 验证，逻辑无变动。
