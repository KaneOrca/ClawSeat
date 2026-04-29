# Claude Code 安装驱动

本文把通用 [安装 Agent Prompt](../../INSTALL_AGENT_PROMPT.zh-CN.md) 映射到
Claude Code 的工具行为。

## Voice & Tone

沿用通用 prompt 的语气协议：简洁、明确、每次给推荐理由。整个会话都支持
`/en`、`/zh`、空回车默认、`详`、推荐★。

## Confirmation Pattern

Claude Code 工具使用顺序：

1. **Read** `docs/INSTALL.zh-CN.md`、`docs/INSTALL_AGENT_PROMPT.zh-CN.md` 和相关安装脚本。
2. **Bash** 运行 Step 0：`bash scripts/install.sh --detect-only`。
3. **Bash run_in_background** 执行长时间的 `install.sh`，方便继续叙述和监控。
4. **Monitor** 后台命令，并总结每个状态变化。
5. **TaskCreate** 在执行前建立 11 步 progress checklist。

确认行保持：

```text
推荐★：<choice>
理由：<一句话>
确认：[回车=默认 / 修改 / 详 / 取消]
```

## Failure Pattern

Bash 或 Monitor 失败时，先分类失败，再给 2-3 个具体修复选项。不要 kill
无关 tmux 或 iTerm session。PTY 资源耗尽时，停止并按项目协议升级。

## detect_all JSON Reference

把 Step 0 输出按 JSON 读取，并保留给后续决策：OAuth 状态、PTY 状态、branch
状态、已有项目、timestamp。
