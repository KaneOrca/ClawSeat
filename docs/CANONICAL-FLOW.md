# Canonical Flow

> 最简明、最不容误解的 ClawSeat dispatch/completion/ACK 协议说明。
>
> 看架构分层：[ARCHITECTURE.md](ARCHITECTURE.md) ｜
> 装完怎么用：[POST_INSTALL.md](POST_INSTALL.md) ｜
> iTerm/tmux 故障定位：[ITERM_TMUX_REFERENCE.md](ITERM_TMUX_REFERENCE.md)

---

## 1. Dispatch（前端 → 执行位）

```bash
python3 dispatch_task.py \
  --profile <profile> \
  --source <source_seat> \
  --target <target_seat> \
  --task-id <TASK_ID> \
  --title '<TITLE>' \
  --objective '<OBJECTIVE>' \
  --reply-to <reply_to_seat>
```

**dispatch_task.py 自动完成：**
1. 写入 `TODO.md`（target 的 inbox）
2. 更新 `TASKS.md` / `STATUS.md`
3. 通过 tmux 通知 target seat（`send-and-verify.sh`，1 秒后 Enter）
4. 若配置了飞书群且 `CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST=1`，则向飞书群广播任务发布
5. 写入 machine-readable handoff receipt

> **飞书群广播默认关闭**。需显式设置 `CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST=1` 才启用。

---

## 2. Completion（执行位 → 前端）

```bash
python3 complete_handoff.py \
  --profile <profile> \
  --source <source_seat> \
  --target <target_seat> \
  --task-id <TASK_ID> \
  --title '<TITLE>' \
  --summary '<CHAIN_SUMMARY>' \
  --frontstage-disposition AUTO_ADVANCE \
  --user-summary '<SHORT_USER_SUMMARY>'
```

**complete_handoff.py 自动完成：**
1. 写入 `DELIVERY.md`（planner inbox）
2. 若配置了飞书群且 `CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST=1`，则向飞书群广播delegation report
3. 写入 machine-readable handoff receipt（`Consumed:` 待前端标记后写入）

> **Review gate**：如果任务会修改 docs / templates / skills / protocol / config / source code，planner 不应直接把它当成 review-free 的自闭环任务。默认先走 `builder-1`（如需实现），再走 `reviewer-1`，最后才允许 frontstage closeout。纯审查/调研任务只有在任务本身明确声明 review-free 时才可跳过 review lane。

---

## 3. OC_DELEGATION_REPORT_V1（唯一 machine-readable control packet）

 planner → koder 通过 `lark-cli --as user` 发送结构化信封：

```
[OC_DELEGATION_REPORT_V1]
project=<project>
lane=<planning|builder|reviewer|qa|designer|frontstage>
task_id=<TASK_ID>
dispatch_nonce=<nonce>
report_status=<in_progress|done|needs_decision|blocked>
decision_hint=<hold|proceed|ask_user|retry|escalate|close>
user_gate=<none|optional|required>
next_action=<wait|consume_closeout|ask_user|retry_current_lane|surface_blocker|finalize_chain>
summary=<单行摘要>
[/OC_DELEGATION_REPORT_V1]
```

**koder 只需看四个字段即可判断行为：**

| report_status | decision_hint | user_gate | next_action | koder 行为 |
|---|---|---|---|---|
| `done` | `proceed` | `none` | `consume_closeout` | 自动推进 |
| `done` | `close` | `none` | `finalize_chain` | 收尾 chain |
| `needs_decision` | `ask_user` | `required` | `ask_user` | 问用户 |
| `blocked` | `retry` | `none` | `retry_current_lane` | 重试当前 lane |
| `blocked` | `escalate` | — | `surface_blocker` | 向用户呈现阻塞点 |

> **不需要依赖 sender 语义**。消息通过用户身份发送，planner lane 身份已在 `lane` 字段中标识。

**不依赖 sender 语义的协议规则：**
- `source=planner` 禁止出现在 envelope 中
- `lane` 字段标识执行 lane，不是发送者身份
- 所有字段均为结构化枚举，koder 可机器解析

---

## 4. Consumed ACK（ durable 收据）

specialist 完成任务后，planner 写入 `Consumed:` ACK 到 handoff receipt：
```json
{
  "task_id": "<TASK_ID>",
  "source": "<source>",
  "target": "<target>",
  "consumed_at": "<timestamp>",
  "status": "consumed"
}
```

---

## 5. 三 Artifact 缺一不可

planner closeout 回 frontstage 必须同时有：
1. `DELIVERY.md`（内容文档）
2. seat-to-seat notify（tmux 或飞书群通知）
3. machine-readable handoff receipt（`handoffs/` 下的 JSON）

---

## 6. 席位通知路径选择

| koder 类型 | 通知路径 |
|------------|---------|
| koder = tmux session | `send-and-verify.sh` 直送 tmux session |
| koder = OpenClaw | 飞书群（`lark-cli --as user` via `send_delegation_report.py`） |

> **旧群广播已废弃**。飞书群通知仅通过 `send_delegation_report.py` + `lark-cli --as user` 发送 OC_DELEGATION_REPORT_V1，默认关闭 opt-in。

---

## 7. Project-Group Bridge Binding

project ↔ Feishu group 的 durable bridge mapping 存储在：

`~/.agents/projects/<project>/BRIDGE.toml`

Schema:

```toml
[bridge]
project = "<project_name>"
group_id = "<feishu_group_id>"
account_id = "<koder_app_id>"
session_key = "<openclaw_session_key_or_prefix>"
bridge_mode = "user_identity"
bound_at = "<ISO8601_timestamp>"
bound_by = "<user_who_authorized>"
```

约束规则：

1. 一项目一群
2. 一群一项目
3. 禁止多个项目绑定到同一个群
4. 绑定操作必须带显式用户授权确认

OpenClaw bridge 操作方法：

- `bind_project_to_group(project, group_id, account_id, session_key, bound_by, authorized=True)`
- `list_project_bindings()`
- `get_binding_for_group(group_id)`
- `unbind_project(project)`

---

## 8. Configuration And Verification

安装完成并不意味着可以直接进入业务执行。canonical 主线应先进入配置阶段：

1. `configuration entry`
   - 选择当前项目 / 切换项目
   - 完成 Feishu `group_id` 绑定
   - 选择 tool / auth_mode / provider
   - 配置 API key / secret
   - 配置 base URL / endpoint URL

2. `configuration verification`
   - 验证 Feishu bridge 是否可用
   - 验证 API key 是否能完成最小调用
   - 验证 base URL / endpoint 是否可达
   - 验证 auth_mode / provider 是否与 seat 配置一致

`qa-1` 默认不负责明文 secret 录入，但应在配置变更具备连通性或回归风险时介入验证，尤其包括：

- Feishu bridge 配置
- 新 API key
- key rotation
- base URL / endpoint 修改
- auth_mode / provider 切换

配置阶段完成且验证通过后，才进入正常执行阶段。
