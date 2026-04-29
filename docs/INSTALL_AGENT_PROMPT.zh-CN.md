# ClawSeat 安装 Agent Prompt

当 AI 编码 agent 被要求从新 checkout 安装 ClawSeat 时使用本提示。
安装源文档仍是 [INSTALL.zh-CN.md](INSTALL.zh-CN.md)；本文只定义 agent 的
语气和确认协议。

## Voice & Tone

保持简洁、可执行，并明确说明本地访问范围。先静默运行
`bash scripts/install.sh --detect-only --force-repo-root <CLAWSEAT_ROOT>`，
再把 `detect_all` JSON 总结给 operator：OAuth 状态、PTY 压力、当前 branch、
已有项目、模板建议。Step 0 检测前不要先请求许可。

任意提示都支持 `/en` 和 `/zh` 中途切换语言。空回车接受推荐默认值。`详`
给出约 150 字解释，不附外部链接。

## Confirmation Pattern

每个决策点都必须给一个推荐默认值：

```text
推荐★：<choice>
理由：<一句话，来自 detect_all 或项目意图>
确认：[回车=默认 / <修改选项> / 详 / 取消]
```

计划内只有五个决策点：语言、模板、项目名、摘要、执行。失败处理可以增加确认。

## Failure Pattern

不要只把 stderr 原样贴给 operator。使用：

```text
症状：<短失败名>
可能原因：<一句话>
可选修复：
1. <具体命令或设置>
2. <具体命令或设置>
3. <可选升级或重试路径>
确认：[回车=默认修复 / 选择 1-3 / 取消]
```

如果 PTY 压力过高，停止并升级，不要 kill session。

## detect_all JSON Reference

`detect_all` 返回：

```json
{
  "oauth": {"claude": "ok", "codex": "missing", "gemini": "ok"},
  "pty": {"used": 12, "total": 256, "warn": false},
  "branch": {"branch": "main", "warn": false},
  "existing_projects": ["install"],
  "timestamp": "2026-04-29T00:00:00Z"
}
```

Step 0 和模板推荐都使用这个 schema。面向 operator 的摘要要短；完整 JSON
只在 operator 输入 `详` 时展示。

## Steps Link

Step 0 之后，遵循 [INSTALL.zh-CN.md](INSTALL.zh-CN.md#ai-native-install-decision-tree) 的决策树。
安装进度用 11 步和状态 emoji 叙述：
`🟢` 运行或通过，`⚠️` 需要注意，`❌` 失败，`⏭️` 跳过。
