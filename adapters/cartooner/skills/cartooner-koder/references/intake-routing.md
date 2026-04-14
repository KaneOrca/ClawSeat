# Intake Routing

在 `cartooner` 项目里，`koder` 先做前台分诊，再决定是否委派。

先把请求压成：

```text
Request type: [discovery / implementation / review / qa / design / mixed]
Need intake skill: [office-hours / plan-ceo-review / none]
Next seat: [engineer-b / none]
Need user decision: [yes/no]
```

规则：

- 顶层仍然先按 seat 路由，不先按工具名路由
- `engineer-b` 是 planner-dispatcher
- `engineer-a` 是 builder
- `engineer-c` 是 reviewer
- `engineer-d` 是 qa
- `engineer-e` 是 optional designer
- 默认保持 delegate-first

Accepted two-review split:

- `engineer-b` = execution-plan review and next-hop routing
- `engineer-c` = code review
- `koder` = intake framing + routing + tracking, not execution planner and not default final reviewer
