task_id: MEMORY-IO-051
owner: builder-codex
target: planner

## 结果

- Part A 的 memory KB IO 已补成原子写路径：
  - `memory_write.py` 现在走 canonical drop CLI，markdown note 用 tmp+rename 落盘，`index.json` 更新在 `flock` 保护下执行。
  - `query_memory.py --ask` 已降级为 deprecated 兼容入口，只告警并退出 `1`，不再触发同步 TUI 调用。
  - `scan_environment.py` 现在也改成 tmp+rename 原子写，避免 scanner 中断时留下半文件或 torn JSON。
- Part B 的 ancestor memory 调用文档化已补齐：
  - brief template 增加 ready-to-run 的 `query_memory.py` / `memory_write.py` 示例和禁用项。
  - `clawseat-ancestor` skill 补了 canonical memory CLI 入口与直接脚本用法。
- Part B5 / Part C 的架构护栏已落到 skill 文档：
  - Pyramid L2/L3 硬边界 + B3.5.0 pre-flight check 已写进 brief / skill。
  - operator red-flag 识别表 + `ARCH_VIOLATION` 拒绝模板 + `operator-override` 流程已写进 `SKILL.md §11`。
- 新增并发回归测试：
  - `tests/test_memory_write_concurrency.py` 证明多 writer / reader 并发下不会撞名、不会把 `index.json` 搞坏，也覆盖了 `scan_environment.write_json()` 的 atomic replace 语义。

## 改动清单

- `core/skills/memory-oracle/scripts/memory_write.py`
- `core/skills/memory-oracle/scripts/query_memory.py`
- `core/skills/memory-oracle/scripts/scan_environment.py`
- `core/templates/ancestor-brief.template.md`
- `core/skills/clawseat-ancestor/SKILL.md`
- `tests/test_memory_write_concurrency.py`
- `tests/test_ancestor_brief_memory_tools.py`
- `tests/test_ancestor_brief_pyramid_rules.py`
- `tests/test_ancestor_rejects_arch_violations.py`

## Verification

```text
$ bash -n scripts/install.sh
$ bash -n scripts/ancestor-brief-mtime-check.sh
$ pytest tests/test_memory_write_concurrency.py -q
2 passed in 0.12s
$ pytest tests/test_install_isolation.py tests/test_install_lazy_panes.py tests/test_ark_provider_support.py tests/test_install_auto_kickoff.py tests/test_install_memory_singleton.py tests/test_session_start_ancestor_env.py tests/test_ancestor_brief_memory_tools.py tests/test_ancestor_brief_pyramid_rules.py tests/test_ancestor_rejects_arch_violations.py tests/test_ancestor_brief_drift_check.py tests/test_ancestor_skill_brief_drift_rules.py tests/test_agent_admin_session_isolation.py tests/test_memory_write_concurrency.py -q
59 passed in 7.54s
```

## Patch 历程

- 先补 `memory_write.py` 的 atomic drop + `index.json` flock，再把 `query_memory.py --ask` 收口成 deprecated 兼容路径。
- 然后把 `scan_environment.py` 改成原子写，补齐 scanner 在中断/并发下的文件完整性。
- 再把 ancestor brief / skill 的 memory CLI 示例、Pyramid 边界和 operator 拒绝模板补齐。
- 最后新增 `tests/test_memory_write_concurrency.py`，把 writer / reader 并发和 atomic replace 行为一起锁住。

## Notes

- 本次不 commit。
- `core/templates/ancestor-brief.template.md` 和 `core/skills/clawseat-ancestor/SKILL.md` 后面还有 BRIEF-SYNC-052 的独立 drift overlay；本交付只记录 MEMORY-IO-051 的那部分改动。
- 顺手修了 `scan_environment.py` 原子写，根因是原先直接 `write_text()` 在并发/中断下可能留下半文件；风险/影响只限 memory scanner 输出完整性，不改对外 query 协议。
