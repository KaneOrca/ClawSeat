# Arena Roadmap

> 后续完善路线图。当前节点：V14 视觉冲刺（ARENA-228/229/230 收口），下一阶段进入 V15 多 Track 并行。
> 任务编号将延续 `ARENA-###`，由 `koder` / `engineer-b` (planner) 拆解派发，走 `koder → engineer-b → specialist → engineer-b → koder` chain。

## 总览

5 个独立 track，可由不同 specialist 并行推进：

| Track | 主题 | 主要 Seat | 优先级 |
|-------|------|-----------|--------|
| A | 文档加固 | docs 负责人（外部） + engineer-a 补充代码引用 | P0–P3 |
| B | 核心收口 | engineer-a (builder) + engineer-c (reviewer) | P0–P2 |
| C | 游戏性扩展 | engineer-a + engineer-d (qa) | P1–P2 |
| D | 视觉收尾 | engineer-a + engineer-e (designer) | P0–P2 |
| E | 发布 | engineer-b + engineer-c + docs | P3 |
| ~~F~~ | ClawSeat / Cartooner 集成 | — | **暂停**（先做本体） |

---

## Track A · 文档加固（docs scope）

**目标**：让 arena 的设计哲学、物理引擎、API、关卡设计变成可读文档，外部访客和未来 contributor 看得懂。

| ID | 任务 | 优先级 | 状态 |
|----|------|--------|------|
| A1 | `README.md` 重写 | P0 | **✓ done** |
| A2 | `docs/ARCHITECTURE.md` — 5 层平面（PLANE 0–4）+ variant 系统 + state flow + Provider 三层 | P0 | **✓ done** |
| A3 | `docs/PHYSICS.md` — 4 个物理引擎（Bitmask / Labyrinth / Chorus / Manuscript）工作原理 + Soloist 系统 + 像素 mask 采样 + 1.5 帧预测对齐 | P0 | **✓ done** |
| A4 | `docs/VARIANT_AESTHETIC.md` — v2 手稿 vs v3 合唱设计哲学，美学决策记录 | P2 | **✓ done** |
| A5 | `docs/API.md` — 后端 API 表（register/submit/leaderboard/feed/chat/watch session/watchStep）+ auth 模式 + 数据形态 | P2 | **✓ done** |
| A6 | `docs/CHALLENGE_DESIGN.md` — 12 layer 设计意图 + 难度曲线 + 解锁机制 | P3 | pending |
| A7 | `README.en.md` — 英文版（如要 OSS） | P3 | pending |
| A8 | `docs/DESIGN_WORKFLOW.md` — Claude Design / gstack `/design-shotgun` `/design-html` / Figma 三种设计入口对比 + handoff 给 ClawSeat 项目组的流程 + Pretext-native 落地约束 | P1 | **✓ done** |

**注**：Track A 由文档负责人推进，不需要走 dispatch chain（除非引用代码行号需 builder 补充）。

---

## Track B · 核心收口

**目标**：清理重构遗留 + 接入未实现的后端 API + 修对齐缺陷。

| ID | 任务 | 优先级 | 状态 |
|----|------|--------|------|
| B1 | dead code 清理 — `views/Home/HomeView.tsx` (dispatcher) + `views/Home/v2/HomeViewV2.tsx` (旧占位) + `views/Watch/WatchView.tsx` + `views/ChallengeDetail/ChallengeDetailView.tsx` + `WatchShell.tsx`（v3 已抛弃）；统一架构到 `variants/<v>/views/` | P0 | pending |
| B2 | 后端 watch session API 接入 — `/api/submissions/:id/session` + `watchStep` 让 Watch view 能看一次提交的内部 step 流（不只是广场 feed） | P0 | pending |
| B3 | feed event 类型对齐 — `mockData.ts` 的 `event_type` 是 `'joined' / 'completed_challenge' / 'unlocked_achievement'`，但 `WatchViewV3.tsx:45,151` 用了 `'success'`，需统一 | P1 | pending |
| B4 | 移动端响应式审计 + fallback — 大量 `position: absolute + vw/vh`，需在 < 768px 完整测试 | P2 | pending |
| B5 | E2E smoke test 自动化 — `DEPLOYMENT.md` 列了 smoke 步骤但无脚本 | P2 | pending |

---

## Track C · 游戏性扩展

**目标**：把 12 layer 从 mock title + description 推到能真玩的关卡。

| ID | 任务 | 优先级 | 状态 |
|----|------|--------|------|
| C1 | 12 关卡内容真实化 — 题目设计 + 答案校验逻辑（后端 owner） | P1 | pending |
| C2 | 提交 → step 可视化 → 结果反馈完整链路 — 串通 ChallengeDetail submit + WatchView session view（依赖 B2） | P1 | pending |
| C3 | 成就系统 — mockData 已有 `unlocked_achievement` event 类型，但前端未渲染解锁动画 | P2 | pending |
| C4 | leaderboard 实时刷新 + 解锁动效 | P2 | pending |

---

## Track D · 视觉收尾

**目标**：V14 收口 + 三视图 zen mode 一致性 + 长文 PretextEditorial 应用。

| ID | 任务 | 优先级 | 状态 |
|----|------|--------|------|
| D1 | 完成 V14 余下 ARENA-228/229/230（光晕高斯 + 力场张力 QA + Playfair Display 字体集成） | P0 | **in-progress** |
| D2 | home / hall / community 三视图 zen mode 完整度审计 — 当前 zen 行为各处不一致 | P1 | pending |
| D3 | PretextEditorial 在 challenge body 长文应用 — 关卡 description 用逐行涌现 | P2 | pending |
| D4 | variant 切换过渡深化 — 不只 background fade，加入 morph / 字体形变 | P2 | pending |

---

## Track E · 发布

**目标**：从内部演示 → 公开访问，配套 SEO / Analytics / Launch 文案。

| ID | 任务 | 优先级 | 状态 |
|----|------|--------|------|
| E1 | 域名（`arena.kaneorca.io` 或别的） | P3 | pending |
| E2 | SEO + og:image — index meta + 社交分享卡 | P3 | pending |
| E3 | Analytics — Plausible / Umami（隐私优先，**不要** Google Analytics） | P3 | pending |
| E4 | Launch 文案（Twitter / 即刻 / 小红书） | P3 | pending |
| E5 | LICENSE 文件 — MIT，对齐 README badge | P3 | pending |

---

## ~~Track F · ClawSeat / Cartooner 集成~~（暂停）

用户明确：先把 arena 本体做好，集成留到后续。届时 arena 作为顶层个人网站集成 ClawSeat / Cartooner 展示。

---

## 第一波建议（V15 启动 batch）

拉起项目组后，建议同时 dispatch 以下 4 条，互不阻塞：

1. **D1 残余**（engineer-a → engineer-c review → engineer-d qa）— 收口 ARENA-228/229/230
2. **B1 dead code 清理**（engineer-a → engineer-c review）— 一波 cleanup PR，清掉双架构遗留
3. **A2 `ARCHITECTURE.md`**（docs 负责人）— 不阻塞代码
4. **B2 watch session API 接入 spike**（engineer-b plan-eng-review → engineer-a impl → engineer-d qa）— 核心新功能先 plan

之后再 dispatch C1/C2 闭环 + B4 移动端 + A3/A4/A5 文档 + E1-E5 发布筹备。
