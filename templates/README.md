`scripts/install.sh` 首次拉起 v2 项目：创建 `<project>-memory`，打开共享 memories 窗口，并按模板为 workers 窗口建立 planner / builder / patrol / reviewer / designer 等 seat。`clawseat-solo` 是 memory + builder + planner-gemini 的 3-seat 极简协作模板。
旧 `templates/clawseat-monitor.yaml` tmuxp 恢复入口已删除；v2 使用 `agent_admin window open-grid --project <project> --recover` 按 project.toml 动态恢复 workers 窗口。
`patrol` 是唯一 verification seat 名称；旧 verification-seat 别名已于 2026-04-29 移除，历史状态请用 `scripts/migrate-qa-to-patrol.sh` 迁移。
