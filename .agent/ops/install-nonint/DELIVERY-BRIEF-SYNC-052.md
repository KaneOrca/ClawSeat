task_id: BRIEF-SYNC-052
owner: builder-codex
target: planner

## 改动清单
- `scripts/ancestor-brief-mtime-check.sh` (新增)
- `core/skills/clawseat-ancestor/SKILL.md` (§2 加 drift check + brief immutability)
- `scripts/install.sh` (OPERATOR-START-HERE.md 模板加 drift 处理段)
- `tests/test_ancestor_brief_drift_check.py` (新增)
- `tests/test_ancestor_skill_brief_drift_rules.py` (新增)

## Verification

```text
$ bash -n scripts/install.sh
$ bash -n scripts/ancestor-brief-mtime-check.sh
$ pytest tests/test_ancestor_brief_drift_check.py tests/test_ancestor_skill_brief_drift_rules.py -q
6 passed in 0.07s
$ pytest tests/test_ancestor_brief_drift_check.py tests/test_ancestor_skill_brief_drift_rules.py tests/test_install_auto_kickoff.py tests/test_install_isolation.py tests/test_install_memory_singleton.py -q
14 passed in 7.41s
```

说明:
- 我还跑过一版更宽的 install suite，`tests/test_install_lazy_panes.py` 里有 2 个当前 dirty tree 的既有失败，和本次 BRIEF-SYNC-052 无关，所以没有把它当成验收门禁。

## Patch 历程

- 先落 `ancestor-brief-mtime-check.sh`，只做 mtime detect + CLI warn 的最小实现，不引入 hot-reload。
- 再把 drift check / brief immutability 写进 `clawseat-ancestor` skill §2，并在 install 生成的 operator guide 里加 `BRIEF_DRIFT_DETECTED` 处理段。
- 最后补两条测试，覆盖 drift / no-op 路径以及文档与脚本可执行性。
- 过程中修正了一处测试缩进问题，并清理了一个无用 import；最终验证保持通过。

## Notes

- 不动 brief template / agent_admin / launcher
- 架构限制由 `SKILL.md` 文档化（Claude Code 无 system prompt hot-reload）
- 本次不 commit
