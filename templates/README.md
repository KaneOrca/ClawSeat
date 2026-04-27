`scripts/install.sh` 首次拉起 v2 项目：创建 `<project>-memory`，打开共享 memories 窗口，并为 planner / builder / designer 建立 workers 窗口。
旧 `templates/clawseat-monitor.yaml` tmuxp 恢复入口已删除；v2 使用 `agent_admin window open-grid --project <project> --recover` 按 project.toml 动态恢复 workers 窗口。
