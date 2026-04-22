task_id: ARCH-CLARITY-047
owner: builder-codex
target: planner

## 改动清单

- `docs/ARCHITECTURE.md`
  - 新增 `§3z — Seat lifecycle entry points (v0.7 Pyramid)`，位置约在 155-184 行
  - 明确 L1 / L2 / L3 分层、sandbox HOME contract、`init_*.py` 不是 user-facing entry points
- `docs/INSTALL.md`
  - 在 Overview 表格后插入说明，位置约在 18-25 行
  - 同时把 install 流程描述对齐 post-046 事实：六个项目 seat 和 memory seat 都是经 `agent-launcher.sh` 起，不再写成手工 tmux session bootstrap
- `docs/CANONICAL-FLOW.md`
  - 在顶部 Overview 段补一句，位置约在 10-13 行
  - 明确本文件只描述“已启动 seat 之间”的 dispatch / completion / ACK，不负责解释如何 launch seat
- `core/launchers/agent-launcher.sh`
  - 顶部新增 INTERNAL 注释，位置约在 2-9 行
  - 明确它是 v0.7 Pyramid 的 L3 execution primitive

## Verification

- `markdownlint`: `NO_MARKDOWNLINT`
- grep / 目视：
  - `docs/ARCHITECTURE.md` 有锚点 `<a id="seat-lifecycle-entry-points-v07-pyramid"></a>` 和 `## §3z — Seat lifecycle entry points (v0.7 Pyramid)`
  - `docs/INSTALL.md` 与 `docs/CANONICAL-FLOW.md` 都链接到 `ARCHITECTURE.md#seat-lifecycle-entry-points-v07-pyramid`
  - `core/launchers/agent-launcher.sh` 顶部有 `# INTERNAL — do not call directly.`
- git status:
  - `M docs/ARCHITECTURE.md`
  - `M docs/INSTALL.md`
  - `M docs/CANONICAL-FLOW.md`
  - `M core/launchers/agent-launcher.sh`

## Notes

- 措辞按 ISOLATION-046 的落地结果对齐：
  - `install.sh` 现在是 L1 user-facing entry
  - 它内部调用 `agent-launcher.sh` 拉起 seat，获得 sandbox HOME isolation
  - `agent-launcher.sh` 本身被明确降格为 INTERNAL-only 的 L3 primitive
- 我额外修正了 `docs/INSTALL.md` 的一处已过时描述：post-046 事实不是“install 只 create tmux sessions”，而是“install 通过 launcher 启动 seats 并保持稳定 session 名”。
- 没有改任何代码逻辑；只改了 4 个指定文件，并补了本交付文件；全部保持未提交。
