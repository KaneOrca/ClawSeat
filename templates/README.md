`scripts/install.sh` 首次拉起 v2 项目：创建 `<project>-memory`，打开共享 memories 窗口，并为 planner / builder / designer 建立 workers 窗口。
`tmuxp load templates/clawseat-monitor.yaml` 是 legacy 恢复入口：tmux server 重启后重建单个 monitor session。
该 tmuxp 模板不会创建 seat session，只会把 pane attach 到已存在的 `clawseat-*` session。
若目标 seat session 不存在，该 pane 会回退到登录 shell。
