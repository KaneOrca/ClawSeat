# Memory Seat v3 — 重构规格

> **定位**: authoritative spec。所有 M1-M6 实施、review、test 都以本文件为准。
> **对齐来源**: 2026-04-18 始祖 CC ↔ 张根铭 的 16 轮对齐讨论结论。
> **实施责任**: koder 派 planner 编排 → builder-1 实施 → reviewer-1 审 → qa-1 测 → planner 闭环回 koder。
> **始祖 CC 角色**: 规格所有者 + reviewer（不直接写代码）。

---

## 1. 重构动机（why）

当前 memory seat 有 8 个根本缺陷：

1. **只懂环境** — scanner 只扫 machine-wide facts，答不了项目级 / 业务级问题
2. **只读** — 没写 API，其它 agent 无法沉淀 decisions / deliveries / findings
3. **无时间维度** — 每次 scan 覆盖，无 event log，答不了 "何时变的 / 谁改的"
4. **无项目命名空间** — 所有 *.json 是 machine-wide，多项目并存会混
5. **无 provenance** — fact 不知道来源 (scanner / write / 推断)，出错不可回溯
6. **无 schema 演进** — 没 `schema_version`，改结构会破老查询
7. **无主动性** — 被动等 `query_memory.py --ask`
8. **无写权治理** — 将来加了写也无 audit trail

目标：把 memory seat 从 "pure-function oracle" 升级成 **L3 Reflector 成长型 agent**。

---

## 2. 13 条设计决策（authoritative）

| # | 决策 | 含义 |
|---|---|---|
| 1 | 职责级别 = **L3 Reflector** | 记录+整理+反思+**研究**（bypass-plan的 research lane）；不主动拦 dispatch |
| 2 | 写权限 = **软治理** | 记 `author + ts + source`，不 reject；违规靠 audit log 事后查 |
| 3 | Reflect 触发 = **外部调度** | memory 不自己反思；**koder heartbeat** 负责派 refresh dispatch；memory 接到 dispatch 才跑 |
| 4 | 命名空间 = **完全重构** | `machine/projects/<proj>/shared/` 三档；不迁移旧 flat *.json（直接弃） |
| 5 | `events.log` 生产者 = **自动钩子** | `dispatch_task.py / complete_handoff.py / notify_seat.py` 每次动作追加 1 行 JSONL |
| 6 | Context 注入 = **仅用户隐私 + 实效性 + 当前项目 dev_env** | 其它全按需 query。单轮 context 预算 20-40KB，跟知识库规模脱钩 |
| 7 | `dev_env.json` 扫描范围 | manifest + versions + lock + build + lint + style + git + **.env 全量不脱敏** + scripts + CI + dev-server + **测试框架** + **deploy 配置 (Dockerfile/Caddyfile/docker-compose)** |
| 8 | Research lane = **SOUL 例外** | koder 可直接 dispatch memory 做 research 任务（kind ∈ `research / investigate / sumup`），**仅** memory 享此例外 |
| 9 | Research workspace = **全局共享** | `~/.agents/memory/research/<topic>/`，按 topic 而非按 project 组织 |
| 10 | Research 默认深度 = **浅**（fetch 3-5 URL, <2min），`--depth mid/deep` 显式升级 | mid = 下载 npm/cargo/PyPI 包源码分析；deep = clone repo + 跑示例 |
| 11 | Research 完成 = **handoff + sediment library_knowledge + reflect 一次** | 三件事一并做，不能只 handoff |
| 12 | 每条 finding **强制** `trust_level + source_url` | 无 trust/url 不能写入 library_knowledge |
| 13 | shared/ 命名空间包含 **CLI guides** | `shared/cli_guides/{claude-code,codex,gemini}.json`，每个 CLI 的 /slash commands + hooks + 最佳实践 + 已知 gotchas |

---

## 3. 目录布局（目标态）

```
~/.agents/memory/
├── machine/
│   ├── credentials.json          [自动注入] API keys / tokens
│   ├── network.json              [自动注入] proxy / endpoints
│   ├── openclaw.json             [自动注入子集] agents roster + feishu accounts/groups
│   ├── github.json               [自动注入] gh_cli.active_login
│   ├── current_context.json      [自动注入] NEW: 当前 project 指针 + last_refresh_ts
│   ├── system.json               [按需]
│   ├── environment.json          [按需]
│   ├── gstack.json               [按需]
│   └── clawseat.json             [按需]
│
├── projects/<project-name>/
│   ├── meta.json                 [按需] README/DEPLOYMENT 摘要 + tech stack
│   ├── dev_env.json              [自动注入 — 仅当前 project] 开发环境完整指纹
│   ├── structure.json            [按需] src/ 树 + 每目录 top 文件
│   ├── tasks.json                [按需] .tasks/{PROJECT,TASKS,STATUS}.md 摘要
│   ├── git.json                  [按需] 最近 30 commit 按类型分桶
│   ├── decisions/<id>.json       kind=decision (planner 写)
│   ├── deliveries/<id>.json      kind=delivery (complete_handoff 自动写)
│   ├── issues/<id>.json          kind=issue (qa/reviewer 写)
│   ├── findings/<id>.json        kind=finding (specialist 写)
│   └── reflections.jsonl         JSONL append-only (memory 写)
│
├── shared/
│   ├── library_knowledge/<topic>.json    (memory research 产出)
│   ├── patterns/<pattern-id>.json        跨项目 pattern
│   ├── examples/<lib>-<pattern>.json     API 用例
│   └── cli_guides/
│       ├── claude-code.json
│       ├── codex.json
│       └── gemini.json
│
├── research/<topic>/                     research workspace
│   ├── fetched/                          原始 web fetches 缓存
│   ├── cloned/                           源码 clone（mid/deep 深度时）
│   ├── notes.md                          memory 边研究边写的笔记
│   └── MANIFEST.json                     研究过程 metadata
│
├── events.log                            全局 JSONL append-only
└── responses/<query-id>.json             query 响应缓存
```

---

## 4. 通用 schema v1（所有 fact kind 共享）

```json
{
  "schema_version": 1,
  "kind": "decision|delivery|issue|finding|reflection|library_knowledge|example|pattern|event",
  "id": "<kind>-<project|shared>-<hash>",
  "project": "arena-pretext-ui | _shared",
  "author": "planner | builder-1 | memory | ...",
  "ts": "2026-04-18T...",
  "title": "short",
  "body": "long-form (markdown ok)",
  "related_task_ids": ["T-001"],
  "evidence": [
    {"type": "commit|file|memory_id|url", "value": "...", "trust": "high|medium|low"}
  ],
  "supersedes": null,
  "confidence": "high|medium|low",
  "source": "scanner|write_api|reflection|event_derived|research"
}
```

**硬验证**（`memory_write.py` 里实现）:
- `schema_version` 必 `== 1`
- `kind` 必在白名单里
- `author` 必在当前 profile 的 seats 列表里（**软治理**：不在 → 警告不 reject）
- `ts` 必 ISO-8601
- kind = `library_knowledge` | `finding` 时，`evidence[]` 必非空 **且** 每条 `evidence` 必有 `trust` + `source_url`（决策 12）

---

## 5. M1 Foundation — 本轮实施范围

本 spec 只定义 **M1**。M2-M6 另立 spec 文件。

### 5.1 交付文件（全部新加 / 新写）

| 路径 | 类型 | 行数估 | 职责 |
|---|---|---|---|
| `core/skills/memory-oracle/scripts/_memory_schema.py` | 新 | ~120 | schema v1 定义 + 验证函数（供 write / query 共用） |
| `core/skills/memory-oracle/scripts/memory_write.py` | 新 | ~200 | `--kind <k>` 写 fact，schema 验证，软治理记 author |
| `core/skills/memory-oracle/scripts/_memory_paths.py` | 新 | ~80 | 目录布局常量 + id 生成函数（跨所有 memory 脚本复用） |
| `core/skills/memory-oracle/scripts/query_memory.py` | 改 | +150/-50 | 加 `--project --kind --since`；支持新布局；**不再全量 inject** |
| `core/skills/memory-oracle/scripts/scan_environment.py` | 改 | +100 | 输出落到 `machine/` 子目录；新增 `current_context.json` |
| `core/skills/memory-oracle/SKILL.md` | 改 | 重写 | 精简到 L3 Reflector 定位（~60 行以内） |
| `core/skills/memory-oracle/inject_memory.sh.template` | 新 | ~30 | 新 inject 脚本模板（隐私+实效性 only）—— 给 init_koder.py 部署到 memory workspace 的 .claude/hooks/ |
| `tests/test_memory_schema.py` | 新 | ~150 | schema 验证 / kind 白名单 / evidence 强制 |
| `tests/test_memory_write.py` | 新 | ~180 | 各 kind 写入正确 / 软治理不 reject / 错误 author 仍写但带 warn flag |
| `tests/test_memory_query_v2.py` | 新 | ~200 | 新布局下 `--project --kind --since` 过滤正确 |
| `tests/test_memory_current_context.py` | 新 | ~80 | `current_context.json` 写入/读取，last_refresh_ts 正确 |

### 5.2 旧布局处理

**不做 migration**。M1 结束时：
- `~/.agents/memory/*.json`（flat）废弃 **但暂不删**（留 fallback 以防紧急回滚）
- 新布局在 `~/.agents/memory/{machine,projects/,shared/}/` 下
- 新 inject 只读新布局
- Memory CC SKILL.md 明确"只读新布局，老 flat *.json 忽略"

M6（koder heartbeat）落地后**专门 commit** 清理老 flat *.json，留 2-3 次 chain 观察期。

### 5.3 acceptance criteria（qa-1 验收必须全绿）

1. **schema**：能写 9 种 kind，错 kind 名 reject，`library_knowledge` 无 evidence reject，`author` 不在 seats 产 warn
2. **query**：`query_memory.py --project install --kind decision` 列出 install 项目所有 decision；`--since 2026-04-01` 过滤按 ts；老 query 形式（`--key X`）依然兼容
3. **inject**：新 inject 脚本跑出来 ≤ 40KB，不含任何 decision/finding/library_knowledge 正文；只含 privacy + 实效性 + current project dev_env
4. **scanner**：`scan_environment.py` 跑一次 → `machine/` 下有 5-6 个文件，`current_context.json` 存在且 `last_refresh_ts` 合法
5. **pytest**：60 新测试全绿 + 已有 106 + 2 selftests 不回归
6. **live smoke**：重启 install memory seat，发 `query_memory.py --ask "github active login?"` 能正确返回（说明隐私层 inject 生效）

### 5.4 M1 **不包含**

- 项目扫描（M2）
- memory_refresh dispatch handler（M3'）
- memory_research（M4）
- events.log 钩子（M5）
- koder heartbeat 扩展（M6）
- CLI guides 内容种子（M2）

---

## 6. 实施流程（chain 如何走）

1. **koder** 接到用户 "实现 memory-seat v3 M1" 需求 → 读本 spec → 用 `--intent eng-review` 派 planner 先审 M1 可行性
2. **planner** 走 `gstack-plan-eng-review` 审 M1 scope → 必要时**回 koder 澄清 decision-gate**（走 Feishu bridge decision-gate，OC_DELEGATION_REPORT_V1）
3. planner 细分为：
    - builder-1 写 schema + write + paths + scanner 改 → `--intent ship`
    - builder-1 写 inject + SKILL.md 改 → 同上
    - reviewer-1 review 最终 diff → `--intent code-review`
    - qa-1 验收跑 acceptance → `--intent qa-test`
4. planner 逐个 dispatch + consume ACK
5. **planner closeout** → koder via `complete_handoff.py --frontstage-disposition AUTO_ADVANCE --user-summary '<给用户的一句话>'`
6. koder 在 Feishu 里告诉用户 "M1 done, 下一个 M？"
7. 始祖 CC（bash）spot check：
    - 每个 commit 对应本 spec 的 5.1 clause？
    - acceptance 5.3 全绿？
    - 有没有超出 5.4 "不包含" 范围（scope creep）？

---

## 7. 保留字段 / 已知遗留

- `machine/` 下 `system.json / environment.json / gstack.json / clawseat.json` 暂保留按需查（决策 6）；M2 scanner 时可能按需精简
- `responses/` 目录 (query 响应缓存) 保持不动，归属在 machine-wide 层
- `dev_env.json` 扫 .env 不脱敏（决策 7），memory seat 被定位为 **pure 内部 agent**（永不外发）—— reflection 不得引用 .env value 文本，只能提 "env var `X` 已配置"
- CLI guides 种子内容落 M2（本轮不做）

---

## 8. 回滚策略

若 M1 上线后发现严重问题：

1. 恢复 Memory CC 的 `.claude/hooks/inject_memory.sh` 到旧版本（读 flat `*.json` 全量）
2. 回退 SKILL.md 到 v1 文本
3. `git revert <M1 commit>`
4. 老 flat `*.json` 未删，可直接读

---

## 9. spec 变更纪律

- 本文件是 authoritative；koder / planner / 任何 seat 不得 "按自己理解" 改范围
- 需要 scope 调整 → planner 回 koder `USER_DECISION_NEEDED` + 走 Feishu decision-gate → 用户同意后 spec 作者（始祖 CC / 张根铭）更新文件 → **重新 commit** 再动工
- spec 更新后 `git diff --stat` 必可见，避免悄悄移动

---

## 10. Post-closeout correction log

以下条目在 M1 / M2 chain 跑完后实地发现原文字与代码事实不符，保留 §4 正文不动，
用本节记录真相与裁决，保证 SPEC 可追溯。

### 10.1 §4 通用 schema — `ALLOWED_KINDS` 白名单（实施于 M2 eng-review 阶段）

**原文字**（§4 记录的 "M1 existing kinds"）:
```
decision, finding, library_knowledge, reflection,
credential, network, environment, repo, agent_config
```

**实际 M1 实现**（`core/skills/memory-oracle/scripts/_memory_schema.py:37-47`）:
```
decision, delivery, issue, finding, reflection,
library_knowledge, example, pattern, event
```

后 5 个（credential / network / environment / repo / agent_config）是**规格作者主观脑补**、
实际 M1 实施时采用不同的 9 项选择。两套名单**完全不重合后 5**。

**裁决**（koder 2026-04-18，option A）: 接受实际 M1 9 项为 canonical 白名单。
M2 时 §4 又加 8 项（`runtime / tests / deploy / ci / lint / structure / env_templates / dev_env`），
合并总数 = 9 + 8 = **17 项**，固化为代码层事实。

**追责**: 规格作者写 §4 时未 grep 实际代码交叉验证 → SPEC 文字与实现脱节。
未来规格修改前必须先跑 `grep -n ALLOWED_KINDS core/skills/memory-oracle/scripts/_memory_schema.py`
确认真实状态。

**影响**: §5.2 的"M1 files 只读"红线**保住**（没被"按字面改 §4"触发 M1 regression）。

**Credit**: 此修正由 planner 在 M2 eng-review 阶段识别差异 → `USER_DECISION_NEEDED`
回 koder → koder 自行 grep 实际代码验证 → 选 option A → chain 恢复派发。
整套流程是 §9 spec 变更纪律的活体示范。
