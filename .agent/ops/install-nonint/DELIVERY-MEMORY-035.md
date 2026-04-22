task_id: MEMORY-035
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: Added a Claude Code Stop hook for the memory seat that self-issues `/clear`, best-effort auto-delivers via `memory_deliver.py`, and ships with an idempotent settings installer plus subprocess contract tests.

## 改动清单
- `scripts/hooks/memory-stop-hook.sh` (新建, 198 行)
- `core/skills/memory-oracle/scripts/install_memory_hook.py` (新建, 112 行)
- `tests/test_memory_stop_hook.py` (新建, 183 行)

## Claude Code Stop hook 协议调研结论
- 官方文档：Claude Code hooks 通过 **stdin JSON** 把事件 payload 传给 command hook，不是把 transcript 文件路径直接塞进环境变量。
  - 参考：`https://docs.anthropic.com/en/docs/claude-code/hooks`
- Stop hook 相比通用 hook payload，额外可用的关键字段是：
  - `transcript_path`
  - `stop_hook_active`
  - `last_assistant_message`
- 本机样例：`~/.claude/settings.json` 已存在 `"hooks": { "Stop": [...] }` 配置，command 形式与官方文档一致。
- 本机现有 `~/.pixel-agents/hooks/claude-hook.js` 也是直接 `for await (const chunk of process.stdin)` 读 JSON，再转发给本地 server，进一步确认了 stdin JSON 约定。

## 实现说明
- `memory-stop-hook.sh`
  - 读取 Stop-hook stdin JSON，优先从 `transcript_path` 读全量 transcript，再用 `last_assistant_message` 补足。
  - 发现 `[CLEAR-REQUESTED]` 后，best-effort 向 `machine-memory-claude` 发送 `/clear`；兼容尝试 `install-memory-claude` / `memory-claude`。
  - 发现 `[DELIVER:seat=<X>]` 后，尝试从 transcript / assistant message 中提取：
    - `task_id`
    - `project`
    - 可选 marker attrs（`seat` / `target` / `task_id` / `project` / `profile`）
  - 能解析出 `task_id + profile + target` 时，调用 `memory_deliver.py` 自动回执；否则 stderr 打一条 `[memory-hook] deliver_skipped: ...`，但 hook 仍返回 0。
  - `tmux` / `memory_deliver.py` 失败都会被吞掉，避免阻塞 Claude Code Stop 流程。
- `install_memory_hook.py`
  - 幂等写入 `<workspace>/.claude/settings.json`
  - 在 `hooks.Stop` 下追加或复用：
    - `type=command`
    - `command="bash /abs/path/to/scripts/hooks/memory-stop-hook.sh"`
    - `timeout=10`
  - 不改 `init_koder.py`，保持 memory hook 安装语义独立。

## Verification
```text
$ bash -n scripts/hooks/memory-stop-hook.sh
hook syntax ok

$ python3 -m py_compile core/skills/memory-oracle/scripts/install_memory_hook.py
install py ok

$ python3 core/skills/memory-oracle/scripts/install_memory_hook.py --workspace <tmp>/memory --dry-run
target: <tmp>/memory/.claude/settings.json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /Users/ywf/ClawSeat/scripts/hooks/memory-stop-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}

$ pytest -q tests/test_memory_stop_hook.py
4 passed in 2.80s

$ manual clear smoke (PATH wrapper)
RC:0
tmux  send-keys -t =machine-memory-claude /clear Enter

$ manual deliver smoke (PATH wrapper)
RC:0
python /Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/memory_deliver.py \
  --profile /Users/ywf/.agents/profiles/install-profile-dynamic.toml \
  --task-id MEMORY-QUERY-123 \
  --target planner \
  --response-inline {"answer": "Done.", "claims": [], "sources": [], "confidence": "medium"} \
  --summary Auto-delivered by memory Stop hook.

$ install idempotence smoke
1
bash /Users/ywf/ClawSeat/scripts/hooks/memory-stop-hook.sh
```

## 已知限制
- auto-deliver 成功依赖 transcript 或 marker 中能解析出 `task_id` 和 `project/profile`；只有裸 `[DELIVER:seat=planner]` 而没有这些上下文时，hook 会跳过交付并打 stderr 提示。
- 当前只提供了独立安装脚本 `install_memory_hook.py`；还没有把它接进更高层 install flow。
- 没改 `memory-oracle/SKILL.md`；文档与产品契约的统一仍应放在后续文档清理任务里处理。
- 当前改动全部未提交，留给 planner 审。
