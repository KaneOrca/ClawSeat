# OpenClaw Boundary

当前 `cartooner` 要区分两种通信面：

- harness specialists (`engineer-a/b/c/d/e`)
- OpenClaw-native `koder`

如果某个 specialist 只是外部 harness seat，不要假设它能直接调用
OpenClaw 的 `sessions_send`。

规则：

- 正常任务链：继续走 `TODO.md / DELIVERY.md + patrol`
- 同一 OpenClaw/ACP session fabric 内部的即时中断：才考虑 direct
  session messaging
- harness -> OpenClaw-native `koder` 的未来实时桥接：走 Gateway/operator
  路径，不把 raw OpenClaw session tools 当默认协议
