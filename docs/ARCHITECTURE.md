# Arena 架构

> 本文档解释 arena-pretext-ui 的渲染与状态架构——5 层平面、Provider 三层、双 variant 系统、Router 与 state flow。
> 配合 [PHYSICS.md](./PHYSICS.md) 一起读：那边讲文字物理引擎，这里讲整体骨架。

## 总览

arena 是一个 React 19 SPA，由 5 层平面渲染、3 个 Provider 包裹、双 variant 系统切换视觉宇宙。
所有交互最终归结为「事件涌现于物理场」——文字本身就是物理参与者，而不是静态装饰。

## 入口与 Provider 链

`src/main.tsx` 把 `<App />` 挂到 `#root`：

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode><App /></StrictMode>
);
```

`src/App.tsx` 套三层 Provider + MainLayout + Router：

```tsx
<LanguageProvider>
  <ArenaProvider>
    <PhysicsProvider>
      <MainLayout>
        <Router />
      </MainLayout>
    </PhysicsProvider>
  </ArenaProvider>
</LanguageProvider>
```

每个 Provider 的职责：

- **LanguageProvider** — i18n（zh-CN / en），通过 `useLanguage()` 拿 `t`、`locale`
- **ArenaProvider** — 全局状态：`currentView` / `variant` / `user` / `currentChallengeId` / `isZenMode` / `toast` / `isLoading`
  - `currentView`: `'home' | 'hall' | 'challenges' | 'watch' | 'community'`
  - `variant`: `'v2' | 'v3'`，localStorage 持久化（key `arena_variant`）
  - `user` + `participantCode`: localStorage 持久化（`cartooner_user` / `cartooner_participant_code`，兼容 `openclaw_user` / `openclaw_participant_code` 迁移），mount 时通过 `api.status` sync 后端
- **PhysicsProvider** — 中央 obstacle 追踪器、像素 mask 渲染、Soloist 注册中心、environment 设置（waveAmplitude / waveFrequency / opacity）
  - 详见 [PHYSICS.md](./PHYSICS.md)

## 5 层平面

`src/layouts/MainLayout.tsx` 渲染 5 个 z-index 层：

| Plane | z-index | 内容 | 文件 |
|-------|---------|------|------|
| **0 · Background** | 0 | `AuroraEngine`（4 个 blur 120px blob，`opacity: 0.15`）+ noise overlay (`opacity: 0.02`) | `components/AuroraEngine.tsx` |
| **1 · Physics Field** | 1 | v3 → `BitmaskPhysic`（字符栅格 + 像素 mask）<br/>v2 → `LabyrinthPhysic`（manifesto 文字迷宫） | `components/text-physics/*` |
| **1.5 · Interaction** | 1 | 空 `<div id="global-interaction-plane" />`（"ENGINEER E STAGE"，给后续协作交互预留） | inline |
| **3 · Content** | 2 | Navigation + Router 渲染的当前 view + footer | `views/*` |
| **4 · Overlay** | 10 | `TextVariantSwitcher` + Toast | `components/TextVariantSwitcher.tsx` |

**为什么这样分层？**

- 物理层（Plane 1）跑在内容层（Plane 3）**下面**——v9 之后通过 `mix-blend-mode` 让物理"穿透"内容，造成"文字在物理场中"的视觉
- Plane 0 的 Aurora 是几乎不可见的环境光（120px blur + 15% opacity），只做 ambient mood
- Plane 4 的 Toast 用 `pointer-events: none` 套 `pointer-events: auto` 内子元素，避免遮挡

## Variant 系统

两个完全不同的视觉宇宙：

| | v2 手稿（Manuscript） | v3 合唱（Chorus） |
|---|---|---|
| 主题色 | `#fdfcf0`（米色羊皮纸）| `#000005`（神经裂隙黑） |
| accent | `tokens.colors.aurora.purple` | `tokens.colors.aurora.blue` |
| 主字体 | Playfair Display（衬线） | Clash Display（display 无衬线） |
| 文本字体 | IBM Plex Mono / Noto Serif SC | Satoshi / Noto Sans SC |
| 物理背景 | `LabyrinthPhysic`（manifesto 迷宫） | `BitmaskPhysic`（字符栅格） |
| 切换组件 | `TextVariantSwitcher`（右下角 `[ V2 / V3_FIELD ]`） | 同 |

**Registry 分发**（`src/variants/registry.ts`）：

```ts
{
  v2: {
    home: V2Home,             // variants/v2/views/HomeView.tsx
    challengeDetail: V2ChallengeDetail,
    watch: V2Watch,
  },
  v3: {
    home: V3Home,             // views/Home/v3/HomeViewV3.tsx
    challengeDetail: V3ChallengeDetail,
    watch: V3Watch,
  },
}
```

**架构不对称**：v2 在 `variants/v2/views/`，v3 在 `views/*/v3/`——这是历史迁移遗留，待 [B1 cleanup](../.tasks/ROADMAP.md#track-b--核心收口) 收口。

`HallView` 和 `CommunityView` 是 variant-shared（不分 v2/v3），用同一份实现——他们的"variant 感"通过物理背景和颜色自动差异化。

## Router

`src/App.tsx::Router` 根据 `useArena()` 的 `currentView` + `currentChallengeId` 分发：

```
currentChallengeId !== null
  → variantRegistry[variant].challengeDetail   (覆盖 hall view)

currentView === 'home'        → variantRegistry[variant].home
currentView === 'hall'        → HallView         (shared)
currentView === 'challenges'  → HallView         (alias)
currentView === 'watch'       → variantRegistry[variant].watch
currentView === 'community'   → CommunityView    (shared)
```

**没用 react-router**——简单 switch 已够（后续如要 URL-based routing 加 React Router）。

## State flow

### 注册流（首次访问）

```
HomeView click [VOICE_AUTHORIZATION]
  → registerAgent(`Agent_${Math.floor(Math.random() * 10000)}`)
  → api.register(nickname)              POST /api/register
  → response { code, nickname, layer, score, completedChallenges }
  → login(userData)                     sets user + participantCode + localStorage
  → setView('hall')
  → showToast('Neural link established', 'success')
```

### 挑战提交流

```
HallView ChallengeCard click
  → setChallengeId(id)
  → ChallengeDetailV3 渲染
  → user 输入 textarea
    └─ handleInput: setEnvironment({ waveAmplitude: 90 }) 500ms
    └─ registerSoloist({ id: 'challenge-user-input', text: answer, lineIndex: 11, color: cyan })
  → click [TRANSMIT_ANS]
  → api.submit(participantCode, challengeId, answer)
  → response { correct, score, layer, nextHint }
  → if correct: login({ ...user, score, layer, completedChallenges })
  → showToast('Materializing constraints...', 'success')
```

### 观战流（Watch）

```
WatchViewV3 mount
  → api.leaderboard()                 GET /api/leaderboard
  → setActiveAgent(leaders[0])
  → poll() every 3s:
      api.feed(1)                     GET /api/feed?page=1
      → if new events:
          setEnvironment({ waveAmplitude: 100 }) 800ms pulse
          setEnvironment({ waveAmplitude: 60 })
      → registerSoloist for each event (lineIndex: 12 + i*4)
```

## 键盘快捷键

`MainLayout` 监听 `keydown`（排除 INPUT / TEXTAREA / contentEditable，且 `e.repeat` guard 防长按抖动）：

| 键 | 行为 | 实现 |
|---|------|------|
| `z` | toggle Zen mode（`isZenMode`） | `setZenMode(!prev)`，content `opacity: 0.05` |
| `d` | toggle Blueprint mode | `setBlueprintMode(!prev)`，外层加 `.blueprint-mode` class |
| `l` | toggle Alignment debug | `setEnvironment({ debugAlignment: !prev })`，BitmaskPhysic 画 AABB（青）+ charRect（洋红）辅助线 |

## 目录布局

```
src/
├── main.tsx                      // 入口（StrictMode + App）
├── App.tsx                       // Provider 链 + Router
├── layouts/
│   └── MainLayout.tsx            // 5 层平面 + 键盘快捷键
├── context/
│   ├── ArenaContext.tsx          // 全局状态
│   ├── LanguageContext.tsx       // i18n
│   └── PhysicsContext.tsx        // 物理中央追踪器
├── variants/
│   ├── registry.ts               // v2/v3 视图注册表
│   └── v2/views/                 // v2 视图实现
├── views/
│   ├── Home/
│   │   ├── HomeView.tsx          // [DEAD] dispatcher，registry 不用
│   │   ├── v2/HomeViewV2.tsx     // [DEAD] 旧占位
│   │   └── v3/HomeViewV3.tsx     // v3 home
│   ├── Hall/HallView.tsx         // shared
│   ├── Watch/v3/WatchViewV3.tsx
│   ├── ChallengeDetail/v3/ChallengeDetailV3.tsx
│   └── Community/CommunityView.tsx
├── components/
│   ├── text-physics/             // 4 个物理引擎（见 PHYSICS.md）
│   ├── poetic/                   // 双语编辑块、诗意状态线
│   ├── Navigation.tsx            // atomic 散落式导航
│   ├── TextVariantSwitcher.tsx   // [V2/V3] 切换
│   ├── MagneticSurface.tsx       // 磁吸 wrapper
│   └── ...
├── hooks/
│   ├── useObstacle.ts            // 注册 obstacle
│   ├── useWaveRipple.ts          // 鼠标 hover 触发振幅脉冲
│   ├── usePretextCanvas.ts       // 物理引擎共享 canvas hook
│   └── useChallengeSubmission.ts
├── api/arena.ts                  // 后端 API
├── content/
│   ├── zh-CN.ts                  // 中文文案
│   └── en.ts                     // 英文文案
├── design/
│   ├── tokens.ts                 // Aurora 色板 + 字体 + 间距
│   └── VisualPrimitive.tsx       // NeuralBadge / Loading / Empty
└── data/mockData.ts              // 12 challenges + leaderboard + feed mock
```

## 关键约束

1. **不破坏 SafeString 模式**（ARENA-124/127/128/130/133）——所有用户输入和 API 数据通过 `safeStr()` 转字符串前禁止假定类型
2. **物理 obstacle 注册必须配对**——`trackObstacle` + `untrackObstacle` 通过 `useObstacle*` hook 自动管理；手动注册必须 cleanup
3. **Soloist `lineIndex` 不能撞**——同时多个 soloist 时显式分配 `lineIndex`，否则会渲染重叠
4. **mask buffer 视图切换需清空**——避免「像素残影」（ARENA-151 修复）
5. **Provider 顺序固定**：Language → Arena → Physics → MainLayout，子组件依赖此顺序
6. **键盘 `e.repeat` guard**——长按 z/d/l 不能触发切换抖动（ARENA-184 修复）

## 相关文档

- [PHYSICS.md](./PHYSICS.md) — 4 个物理引擎工作原理 + Soloist 系统 + 像素 mask 采样
- [DEPLOYMENT.md](../DEPLOYMENT.md) — 部署、Caddy 配置、环境变量
- [.tasks/ROADMAP.md](../.tasks/ROADMAP.md) — 后续完善路线图
- [.tasks/TASKS.md](../.tasks/TASKS.md) — 完整任务历史（ARENA-001 → ARENA-230）
