# Arena 设计工作流

> arena-pretext-ui 不是普通 SaaS landing。它的视觉是「文字本身就是物理参与者」——
> 任何设计落地必须兼容 Pretext 字符级测量 + obstacle 系统 + variant 哲学。
> 本文档说明三种设计入口 + handoff 给 ClawSeat 项目组的完整流程。

## TL;DR

| 场景 | 推荐入口 |
|---|---|
| 新视觉方向探索 / 多版对比 / 客户协作 / 想要 PPT | [Claude Design](https://claude.ai/design) |
| Pretext-native HTML 落地 / 字符级物理对齐（arena 核心视图） | gstack `/design-shotgun` + `/design-html` |
| 已有 Figma 设计系统 / 团队协作 | Figma export → 喂 koder |

所有产物最终通过 ClawSeat dispatch chain 到 `engineer-e` (designer) 评审 →
`engineer-a` (builder) 实现 → `engineer-c` review → `engineer-d` QA。

---

## arena 的特殊约束

任何为 arena 做的设计落地必须考虑：

### 1. 文字是物理参与者

arena 的核心理念：**任何 UI 元素被注册成 obstacle**。背景物理引擎（`BitmaskPhysic` /
`LabyrinthPhysic`）实时让字符栅格 / 文字迷宫**绕开** UI 文字、按字形孔洞精确避让。

设计师必须明白：

- 一个标题不只是「放在画面里」，是「挤开了周围的物理场」
- hover 一个按钮不只是「改色」，是「波场振幅 60→120 拉起 600ms」
- 输入答案不只是「显示文字」，是「soloist 重号介入波场 + waveAmplitude 60→90」

设计稿如果不体现这种交互层次，落地时会很奇怪。详见 [PHYSICS.md](./PHYSICS.md)。

### 2. 双 variant 哲学

| | v2 手稿 | v3 合唱 |
|---|---|---|
| 底色 | 米色羊皮纸 `#fdfcf0` | 神经裂隙黑 `#000005` |
| 主字体 | Playfair Display + IBM Plex Mono | Clash Display + Satoshi + JetBrains Mono |
| 美学 | 边缘旁注 + 签名嵌入 | 字符栅格 + Aurora 波场 |
| 物理引擎 | `LabyrinthPhysic`（manifesto 文字迷宫） | `BitmaskPhysic`（字符栅格 + 像素 mask） |

任何新设计必须明确：**为 v2 设计还是为 v3 设计**，或者都要（双稿）。

### 3. Pretext-native 排版

不是用 CSS 限制高度。是用 Pretext API（`prepare()` + `layout()`）计算高度——
文字真能 reflow，heights 真能 compute，contenteditable 改文字会触发 re-prepare。

设计稿如果用了 hard-coded `height: 200px` 或 `line-clamp: 3`，
落地时不兼容 Pretext API，需要重设计成「自适应高度 + Pretext layout」模式。

### 4. 5 层平面 + 极客档位

设计稿要预留：

- **Plane 0** — 几乎不可见的 Aurora 环境光（120px blur，opacity 0.15，**不要试图占用**）
- **Plane 1** — 物理引擎层（设计中视为「底层文字流」）
- **Plane 3** — Content 层（你的设计大部分在这里）
- **Plane 4** — Toast / Variant Switcher（保留位置）

以及键盘档位 `z` Zen / `d` Blueprint / `l` Alignment debug——设计稿中这三种状态的视觉行为各异。详见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

---

## 三种入口详解

### 入口 1: Claude Design

[claude.ai/design](https://claude.ai/design)（Anthropic Labs，2026-04 发布；Claude Pro / Max / Team / Enterprise 可用）

**推荐场景**：

- 新视觉方向**探索**——多版风格对比
- 客户协作 / PPT 输出
- 想要快速 one-pager 提案
- 不需要字符级物理对齐的视觉（如关卡 story 内容页）

**怎么用**：

1. 打开 [claude.ai/design](https://claude.ai/design)
2. 描述需求，例：
   > "Design a layered hall view for an OpenClaw arena where users see 12 challenge cards.
   > Cards should evoke a digital scriptorium with neural-rift cyberpunk overlay,
   > suitable for both v2 manuscript (cream background) and v3 chorus (deep black) themes."
3. Claude 出多版初版 → 评论 / 直接编辑 / 滑块迭代
4. 选定后导出 → HTML / PNG / Canva / handoff bundle

**适配 arena 的要点**：

- 在描述里**明确 variant**：v2 / v3 / 双稿
- 提到关键 design token（Aurora 色 / Clash Display / Playfair）
- 说明哪些 UI 元素需要「物理参与」（注册成 obstacle）

### 入口 2: gstack `/design-shotgun` + `/design-html`（arena 字符级落地推荐）

**推荐场景**：

- 需要 **Pretext-native 字符级物理对齐**——arena 的所有核心视图（home / hall / watch / challenge detail）
- 离线 / 本地隐私优先
- 直接出 production HTML

**怎么用**：

```bash
# 1. 探索方向（GPT-4o vision 出多版候选）
/design-shotgun

# 2. 选定一版后落地（Pretext-native HTML）
/design-html
```

`/design-html` 产物：

- 路径：`~/.gstack/projects/<slug>/designs/<screen>-YYYYMMDD/finalized.html`
- 内嵌 Pretext 30KB（vendored，CDN fallback）
- 自动用 `prepare()` + `layout()` 做高度计算
- ResizeObserver 监听容器尺寸变化 → 自动 relayout
- contenteditable 文本 → MutationObserver 触发 re-prepare
- `prefers-color-scheme` + `prefers-reduced-motion` 内置

**这是 arena 最直接的 design 落地路径**——产物可以直接接入 obstacle 系统。

### 入口 3: Figma / Sketch / 其它

**推荐场景**：

- 已有团队设计系统 / 设计师 Figma 工作流
- 需要细颗粒度视觉控制 / 复杂 design system 维护

**怎么用**：

1. 在 Figma 完成设计
2. 导出 PNG（多视口：375 / 768 / 1440）+ 切图 + 设计描述
3. 提交给 koder 时附 bundle，明确：
   - 对应的 variant（v2 / v3）
   - 哪些元素是 obstacle（要注册到 `PhysicsContext`）
   - 哪些元素是 soloist（要在物理场中以重号介入）
   - 是否使用 `PretextEditorial`（逐行涌现）

**注意**：Figma 不输出 Pretext-native HTML——`engineer-a` 实现时需要把 Figma export 转成 Pretext API 调用，比 `/design-html` 多一步。

---

## handoff 给 ClawSeat 项目组

不管哪个入口，最终都通过 ClawSeat dispatch chain 实现。完整流程：

### Step 1: 提交 bundle 给 koder

把设计产物放进 `~/.agents/tasks/arena/inbox/<task-id>/`，或飞书群里 @koder 附描述 + bundle 链接。

bundle 应包含：

- **PNG** mockup（多视口）
- **设计描述**（variant 选择、obstacle 列表、交互层次）
- **HTML** 或 **handoff bundle**（Claude Design / design-html 出的）
- **design tokens**（颜色 hex / 字体 / 间距，与 `src/design/tokens.ts` 对齐）

### Step 2: koder dispatch design-review

```bash
python3 core/skills/gstack-harness/scripts/dispatch_task.py \
  --source koder --target engineer-e \
  --task-id arena-design-XXX \
  --objective "评审 [设计来源] 出的 [view 名] 重设计，bundle 见 inbox/arena-design-XXX/" \
  --intent design-review \
  --skill-refs ~/.agents/tasks/arena/inbox/arena-design-XXX/
```

### Step 3: engineer-e 评审

`designer` seat 拿 `/design-review` skill 评审：

- 是否符合 variant 哲学
- obstacle 注册策略是否清楚
- soloist / Pretext 用法是否兼容物理引擎
- design tokens 是否与 `tokens.ts` 一致 / 需要扩展
- 5 层平面分配合理吗

输出：`DELIVERY.md` 含 verdict（`GO` / `CHANGES_REQUESTED`）+ 具体修改建议。

### Step 4: engineer-b 拆解（如果 GO）

planner 把设计落地拆成实现任务：

- 字符级 obstacle 注册（哪些元素 `useObstacle()`）
- 物理扰动接入（hover / 键入 / 提交各触发什么 environment）
- variant-specific 实现（v2 / v3 / shared）
- Pretext API 选择（`prepare/layout` vs `prepareWithSegments/layoutNextLine`）

### Step 5: engineer-a 实现 + engineer-c review + engineer-d QA

按 ClawSeat 标准 dispatch chain：

```
engineer-b → engineer-a → engineer-c → engineer-d → engineer-b → koder
```

每一步走 [.tasks/PROJECT.md](../.tasks/PROJECT.md) 定义的 chain 协议。

详见 ClawSeat [`docs/GSTACK.md` 外部设计工具 handoff 章节](https://github.com/KaneOrca/ClawSeat/blob/main/docs/GSTACK.md)。

---

## 反模式（什么不适合 arena）

设计稿出现以下内容时，物理引擎不兼容，需要重设计：

- ❌ **硬编码 height**（`height: 240px`）—— 与 Pretext layout 冲突
- ❌ **3 行截断 `line-clamp: 3`** —— 违背「文字真能 reflow」哲学
- ❌ **绝对定位但未明确 obstacle**—— 物理引擎不知道这块区域要避让
- ❌ **大块装饰图案 / blob / 几何形状**—— arena 美学是文字 + 物理，不是装饰
- ❌ **AI slop**：紫蓝渐变 hero / 三栏 feature grid / 圆角卡片 + drop shadow / "Get Started" CTA
- ❌ **Lorem ipsum / 假数据**—— arena 文案诗意化，必须用真实文案（参考 [src/content/zh-CN.ts](../src/content/zh-CN.ts)）

---

## 典型场景：hall 关卡卡片重设计

**目标**：`HallView` 当前 `ChallengeCard` 的视觉迭代（让锁定/解锁/完成三个状态更明显的视觉差异）。

### 选入口

字符级物理对齐很重要（卡片标题 / 副标 / 解锁状态都要在物理场中飘动）
→ **gstack `/design-shotgun` + `/design-html`**

### 跑工作流

`/design-shotgun` prompt：

> "12 challenge cards for hall view, three states (locked encrypted / unlocked clean / completed checkmarked).
> Variant v3 chorus aesthetic: black background, Clash Display titles, JetBrains Mono meta.
> Cards must register as obstacles for BitmaskPhysic to flow around.
> Locked cards show ScrambleText animation; completed cards show ✓ CONQUERED."

### 选定后跑 `/design-html`

产出 `finalized.html`，浏览器实时调试。

### 提交 koder

```bash
cp -r ~/.gstack/projects/.../designs/hall-card-20260426/ ~/.agents/tasks/arena/inbox/arena-design-001/
```

### koder dispatch

```bash
dispatch_task.py \
  --source koder --target engineer-e \
  --task-id arena-design-001 \
  --objective "评审 hall ChallengeCard 三态重设计，bundle 见 inbox/arena-design-001/" \
  --intent design-review
```

后续按 dispatch chain 走完。

---

## 相关文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) — 5 层平面 / Provider / Variant 系统
- [PHYSICS.md](./PHYSICS.md) — 物理引擎 / Soloist / Pretext API 用法
- [.tasks/ROADMAP.md](../.tasks/ROADMAP.md) — 后续完善路线图
- [.tasks/PROJECT.md](../.tasks/PROJECT.md) — gstack-harness chain 协议
- ClawSeat [`docs/GSTACK.md` handoff 段](https://github.com/KaneOrca/ClawSeat/blob/main/docs/GSTACK.md)
- gstack `/design-shotgun`：`~/.claude/skills/gstack/design-shotgun/SKILL.md`
- gstack `/design-html`：`~/.claude/skills/gstack/design-html/SKILL.md`
- Claude Design：[claude.ai/design](https://claude.ai/design) · [入门文档](https://support.claude.com/en/articles/14604416-get-started-with-claude-design)
