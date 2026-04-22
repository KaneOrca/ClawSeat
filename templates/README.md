`scripts/launch-grid.sh` 用于首次拉起：创建 `clawseat-*` seat sessions，并建立监控六宫格。
`tmuxp load templates/clawseat-monitor.yaml` 用于恢复：tmux server 重启后重建单个 monitor session。
该 tmuxp 模板不会创建 seat session，只会把 pane attach 到已存在的 `clawseat-*` session。
若目标 seat session 不存在，该 pane 会回退到登录 shell。
