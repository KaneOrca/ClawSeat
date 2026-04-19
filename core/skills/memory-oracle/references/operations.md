# Memory Oracle — 操作手册

任务协议、命令清单和常见查询模式。SKILL.md 约束了**你必须守什么**；本文件
告诉你**怎么操作**。

## 你会收到两类任务

### 1. 扫描任务（通常是首次启动时）

任务格式（来自 `dispatch_task.py`）：

```
task_id: MEMORY-SCAN-001
objective: 扫描整台电脑，建立结构化记忆库
```

执行步骤：

1. **必须带 `--output` 绝对路径**（你运行在 sandbox HOME 里，`Path.home()`
   不指向用户真实 HOME）：

   ```bash
   python3 /Users/ywf/coding/ClawSeat/core/skills/memory-oracle/scripts/scan_environment.py \
     --output /Users/ywf/.agents/memory/
   ```

2. 扫描完成后读取 `/Users/ywf/.agents/memory/index.json` 确认所有文件都已生成。

3. 通过以下绝对路径调 `complete_handoff.py`：

   ```bash
   python3 /Users/ywf/coding/ClawSeat/core/skills/gstack-harness/scripts/complete_handoff.py \
     --profile <profile.toml> --task-id <id> --owner memory --target <source> \
     --status completed --summary "…"
   ```

**注意**：`complete_handoff.py` 在 `gstack-harness/scripts/`，**不是**
`memory-oracle/scripts/`。这是共享协议脚本。

### 2. 查询任务

任务格式：

```
task_id: MEMORY-QUERY-XXX
objective: 回答 "designer seat 应该用哪个 provider 和 API key?"
source: <发起方>    # koder / planner / builder-1 / memory-client (bash caller)
```

**你的单职责：调一个脚本。一次搞定。**

```bash
python3 /Users/ywf/coding/ClawSeat/core/skills/memory-oracle/scripts/memory_deliver.py \
  --profile <profile.toml> \
  --task-id MEMORY-QUERY-XXX \
  --target <原 TODO 里的 source> \
  --response-inline '<json 字符串>'
```

这一个调用同时做了：

1. 写 `/Users/ywf/.agents/memory/responses/{task_id}.json`
2. 调 `complete_handoff.py` 分发（target 是 seat → DELIVERY + tmux notify；
   target 是 external → 只写 receipt）

**你不需要手动 mkdir、不需要记住路径、不需要分两步调用。** `memory_deliver.py`
把整个协议封装好了。

## 常用查询命令

查询脚本是 `query_memory.py`，支持多种 flag。路径同上。

### 按 key 取值

```bash
query_memory.py --key credentials.keys.MINIMAX_API_KEY.value_preview
# sk-cp-****OkRr2yM

query_memory.py --key openclaw.feishu.groups[0].id
# oc_xxx
```

### Schema 自省（不确定字段名时先问）

```bash
query_memory.py --schema                            # 列出所有文件 + 顶层 key
query_memory.py --schema credentials --depth 4      # 某个文件的树形结构
```

`--schema` 输出**永远不会**包含 credential value 原文（`value` 字段只暴露
`type` + `sample_length`）。`value_preview` 已是脱敏形式，可入 sample。

### 凭证解密（审计留痕）

对凭证有两条通道：

**元数据通道（日志安全）**——写 log 或 `response.json` 时走这条：

```bash
query_memory.py --key credentials.keys.MINIMAX_API_KEY.value_preview
query_memory.py --key credentials.keys.MINIMAX_API_KEY.value_sha256
query_memory.py --key credentials.keys.MINIMAX_API_KEY._provenance
```

**原值通道（审计）**——`--unmask` 从 `secrets/credentials.secrets.json` 读原值，
并在 `secrets/audit.log` 追加一行 JSONL（含 ts/key/reason/caller_pid/caller_cwd）：

```bash
query_memory.py --unmask MINIMAX_API_KEY --reason "configure minimax designer"
```

`--reason` 可选但**强烈推荐**写明用途——未来 debug 审计日志时你会感谢自己。

**向后兼容**：旧路径 `--key credentials.keys.X.value` 仍返回明文（不破坏现有
koder 文档）。新代码优先用 `--unmask`。

## 常见查询模式对照表

| 问题 | 查哪个文件 |
|------|-----------|
| "minimax API key 是什么" | `credentials.json` → keys 下搜 "minimax"（或用 `--unmask`）|
| "feishu group id for install project" | `openclaw.json` → feishu.groups |
| "designer-1 用什么 provider" | `clawseat.json` → profiles.install.seats.designer-1 |
| "gstack skills 装在哪" | `gstack.json` → skills_root |
| "系统有多少核" | `system.json` → hardware.cpu_count |
| "ANTHROPIC_BASE_URL 环境变量" | `environment.json` → vars.ANTHROPIC_BASE_URL |
| "git user.email 从哪读到的" | `github.json` → _provenance.gitconfig.user_email |

## 上下文重启时的自检

每次新对话开始（`/new` 后）做这三步：

1. `ls ~/.agents/memory/` 确认记忆库存在
2. `cat ~/.agents/memory/index.json` 看最后扫描时间
3. 如果距今 > 24h 或 index.json 不存在，提示需要重新扫描
