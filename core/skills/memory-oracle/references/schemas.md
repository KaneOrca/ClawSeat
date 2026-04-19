# Memory Oracle — 数据结构参考

所有磁盘上的 JSON 布局、凭证 dual-write schema、response.json 结构和证据格式。
SKILL.md 的 "查询回答铁律" 章节约束了你输出什么；本文件告诉你数据长什么样。

## 记忆库目录树

```
~/.agents/memory/
├── system.json                      # OS/hardware/brew packages
├── environment.json                 # env vars, PATH
├── credentials.json                 # 凭证元数据 + 明文 value（向后兼容）
├── openclaw.json                    # OpenClaw config, skills, agents, feishu groups
├── gstack.json                      # gstack repos, skills
├── clawseat.json                    # ClawSeat profiles, sessions, workspaces
├── repos.json                       # local git repos and remotes
├── network.json                     # proxy, endpoints
├── github.json                      # git/gh 身份、SSH 公钥，含 _provenance 旁表
├── index.json                       # metadata: scan_version, 文件列表, secrets_file 指针
├── response.json                    # query responses (written by you, read by caller)
└── secrets/                         # 0700，只含原始凭证 + audit log
    ├── credentials.secrets.json     # 0600，raw {KEY: value} 表
    └── audit.log                    # JSONL，每次 --unmask 追加一行
```

## credentials.json 双写 schema (v2 起)

每个 key 条目同时含 "日志安全的元数据" 和 "原值"。日志安全字段永远可以入
`response.json` 或 stdout；原值在 `secrets/` 旁表里，需要 `--unmask` 才能拿。

```json
{
  "value": "sk-cp-...",                 // 向后兼容：明文
  "source": "/Users/ywf/.env.global",   // 向后兼容：来源文件
  "value_preview": "sk-cp-****OkRr2yM", // 可安全入日志
  "value_length": 121,
  "value_sha256": "e7f3...",            // 用于 hash 证据
  "value_type": "api_key",              // api_key / base_url / token / secret / unknown
  "_provenance": {
    "source_file": "/Users/ywf/.env.global",
    "source_line": 7,
    "scanned_at": "2026-04-19T..."
  }
}
```

## response.json — 你交付的东西

这是 caller（koder/planner）读回来校验的文件。schema 是硬的：

```json
{
  "claims": [
    {
      "statement": "designer-1 uses gemini + oauth + google provider",
      "evidence": [
        {
          "file": "clawseat",
          "path": "profiles.install-profile-dynamic.seat_roles.designer-1",
          "expected_value": "designer"
        }
      ]
    }
  ],
  "confidence": "high",
  "timestamp": "2026-04-17T12:34:56Z"
}
```

`query_id` 不用填——`memory_deliver.py` 用 `--task-id` 自动填好。

### evidence 格式宽容度

- `file` 可以写短名 `github` / `github.json` / `/full/path/github.json`，caller 的
  `verify_claims()` 会归一化。
- `path` 可以写点号 `gh_cli.active_login` / JSONPath `$.gh_cli.active_login` /
  斜杠 `gh_cli/active_login`，都会被归一化。
- **但 `expected_value` 必须和磁盘上完全相等**，否则 verify 报 mismatch。

### hash 证据（推荐用于凭证类 claim）

对凭证字段，用 `expected_value_sha256` 代替 `expected_value`，不把明文塞进
response.json。`verify_claims()` 会对 `actual` 做 sha256 并比对。非凭证字段仍用
`expected_value`（更直观）：

```json
{
  "claims": [{
    "statement": "MINIMAX_API_KEY 存在且源自 .env.global",
    "evidence": [
      {"file": "credentials",
       "path": "keys.MINIMAX_API_KEY.value",
       "expected_value_sha256": "e7f3..."},
      {"file": "credentials",
       "path": "keys.MINIMAX_API_KEY._provenance.source_file",
       "expected_value": "/Users/ywf/.agents/.env.global"}
    ]
  }]
}
```

### confidence 等级

- `high` — 每个 claim 都能用磁盘 JSON path 直接拿到原值
- `medium` — 组合了多个字段的事实推理（但每个字段仍可 verify）
- `low` — 部分依赖常识/推测——caller 应警惕
