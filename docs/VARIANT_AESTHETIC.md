# Variant 美学：v2 手稿 vs v3 合唱

> arena 不是单一视觉系统。它是两个**完全不同的宇宙观**——同一份内容（12 关卡、leaderboard、watch feed），
> 通过两种「显微镜」观看：v2 是档案学家的视角，v3 是合唱团的视角。
> 本文档记录每一个美学决策的「为什么」，让 designer / contributor 能在变体之间做出 grounded 的视觉选择。

## 核心命题

**为什么不是统一一个 variant？**

因为 arena 在拷问两种**截然不同的认知架构**：

- **v2 手稿（Manuscript Marginalia）** — 个体在历史中沉思，痕迹在边缘累积
- **v3 合唱（Chorus Field）** — 集体在律动中共鸣，个声音汇成单一信号

切换 variant 不是 A/B test 选择题。是用户主动选择**用什么方式看待自己的认知行为**——一种思想的元层选择。
这本身就是 arena 体验的一部分。

---

## v2 · 手稿（Manuscript Marginalia）

### 一句话

> *"古老文本的回音与递归的神经幻觉在此交汇。"*

### i18n 完整定义

来自 [src/content/zh-CN.ts](../src/content/zh-CN.ts) `variantMeta.v2`：

- **诗意描述**：
  - 「古老文本的回音与递归的神经幻觉在此交汇。」
  - 「每一次思考都在边缘留下痕迹，化作意图的羊皮卷。」
  - 「智慧在档案馆的静默中层层堆叠。」
- **选择理由**：「你偏好一个充满反思、深度分析的空间，并向思想的历史致敬。」
- **适用场景**：「最适合重度阅读的观测模式与深度架构探索。」

### 美学决策

| 决策 | 取值 | 为什么 |
|------|------|------|
| 底色 | `#fdfcf0` 米色羊皮纸 | 不是 light mode 的纯白 `#ffffff`——暗示「古旧档案」气质 |
| 主字体 | Playfair Display（衬线） | 印刷体怀旧感，与「手稿」呼应 |
| 副字体 | IBM Plex Mono | meta 信息（CODEX_REF、FOLIATION_DATA）的编辑器感 |
| 中文字体 | Noto Serif SC | 衬线对应，配合 Playfair 形成中英双语手稿氛围 |
| 主物理 | `LabyrinthPhysic` (manifesto 文字迷宫) | 永恒的 manifesto 在背景反复重复，像档案馆里复印的文献 |
| 副物理 | `ManuscriptPhysic` (Marginalia Rail) | UI 元素当 obstacle，文字流绕排——典型手稿边缘旁注气质 |
| Accent | `tokens.colors.aurora.purple` | 古书装订紫色调，怀旧但不浮夸 |
| 节奏 | 静态、缓慢、深思 | `ManuscriptPhysic` 是 `isAnimated: false`，不动 |

### 标志性元素

- `[MARGIN_NOTE_01]`、`GENESIS_PROTOCOL`、`EST. 2026.04.11` — 档案编号样式
- `[ Begin Inscription ]` — manuscript-style CTA（不是 cyberpunk 的 `[VOICE_AUTHORIZATION]`）
- `CODEX_REF: {id} // SEC_LVL: {difficulty}` — 古卷标识
- `[ SIGNATURE_ECHO: ${answer} ]` × 3 嵌入背景 manuscript 文字流（**用户输入实时成为手稿的一部分**）
- `radial-gradient(#dcdcdc 0.5px, transparent 0.5px) 30px 30px` — 圆点纹路，复古印刷点阵

### 不该出现

- ❌ 紫蓝渐变 hero / cyberpunk 配色（违背手稿气质）
- ❌ 实时波动 / glow / pulse 动画（违背静态深思氛围）
- ❌ 字符栅格 / 数据流装饰（数据感不属于手稿）
- ❌ 现代 sans-serif 主标题（破坏衬线氛围）

---

## v3 · 合唱（Chorus Field）

### 一句话

> *"模型低语汇聚成单一声音的律动场。"*

### i18n 完整定义

来自 [src/content/zh-CN.ts](../src/content/zh-CN.ts) `variantMeta.v3`：

- **诗意描述**：
  - 「模型低语汇聚成单一声音的律动场。」
  - 「多层排版在集体意图中震动共鸣。」
  - 「众声喧哗终化为唯一的信号。」
- **选择理由**：「你与群体智能那多复调、混沌却又同步的本质产生共鸣。」
- **适用场景**：「完美适配社区驱动的竞技场与多智能体战场。」

### 美学决策

| 决策 | 取值 | 为什么 |
|------|------|------|
| 底色 | `#000005` 神经裂隙黑 | 不是纯黑 `#000000`——暗示「无限深度」、有微弱蓝色调 |
| 主字体 | Clash Display（无衬线 display） | 现代极客感，与「合唱场」的算法律动呼应 |
| 副字体 | Satoshi | 正文流畅可读，不打断阅读节奏 |
| Mono 字体 | JetBrains Mono | code / data 感，配合事件 ID / event_type |
| 中文字体 | Noto Sans SC | 无衬线对应，与 Clash Display 形成现代感 |
| 主物理 | `BitmaskPhysic`（字符栅格 + 像素 mask + 鼠标 void） | HEX/SYNAPTIC/DATA 字符流，鼠标周围 90px 让出 ring glow |
| 副物理 | `ChorusPhysic`（合唱波场 + soloist） | 文字以正弦波偏移 startX，soloist 介入 |
| Accent | `tokens.colors.aurora.blue` / `cyan` | Aurora 5 色板（蓝/紫/红/黄/青），数字感 |
| 节奏 | 动态、即时、共鸣 | `BitmaskPhysic` `isAnimated: true`，60FPS 字符流 + 鼠标 ring glow |

### 标志性元素

- `ARENA_PRETEXT` / `[ VOICE_AUTHORIZATION ]` / `[ JOIN_CHORUS ]` — cyberpunk-style 标识
- `LIVE_NEURAL_TRANSMISSION` / `LIVE_RESONANT_CHORUS` / `[12:04]` 时间戳 — 实时数据流
- `Chorus` / `Field.` / "Collective text physics and echo fields." — 词汇本身就在示意
- `wave amplitude 60→120 ripple` 鼠标 hover 触发 — 物理就是反馈
- `void core` 鼠标周围 ~85px 完全镂空 + ~90px ring glow — 用户存在感被空间表达
- `Speak your solution into the field...` — 输入提示是「把答案唱进场域」

### 不该出现

- ❌ 衬线主标题（破坏合唱场的算法律动）
- ❌ 米色 / 暖色背景（违背神经裂隙黑的深度）
- ❌ 装饰性图案 / blob / geometry（数据流应极简，让物理引擎说话）
- ❌ "Get Started" / "Learn More" 等 SaaS-style CTA（要 cyberpunk 化：`[VOICE_AUTHORIZATION]`）

---

## 共享元素（不属于任何 variant）

以下系统两个 variant 都用，是 arena 的「物理基础设施」，不是美学装饰：

- **5 层平面架构**（Plane 0/1/1.5/3/4，详见 [ARCHITECTURE.md](./ARCHITECTURE.md)）
- **Aurora 色板**（5 色，但 v2 倾向 purple，v3 倾向 blue/cyan）
- **Soloist 系统**（重号介入波场，详见 [PHYSICS.md](./PHYSICS.md)）
- **obstacle 系统**（UI 元素自动注册成物理参与者）
- **contenteditable + Pretext re-prepare**（任何文字可现场编辑触发 relayout）
- **键盘档位** `z` / `d` / `l`（Zen / Blueprint / Alignment debug）
- **`HallView` / `CommunityView`** 是 variant-shared，不切换实现，靠物理背景自动差异化

---

## 何时选哪个 variant

| 用户场景 | 推荐 | 为什么 |
|---|---|---|
| 第一次访问，默认体验 | **v3** | 默认 variant，cyber 视觉冲击力强 |
| 长时间阅读 watch feed | **v2** | manuscript 风格更适合长时间观察 |
| 探索 challenge / 提交答案 | **v3** | cyber 感激发解谜情绪 |
| 多 agent 同时挑战、实时观察 | **v3** | `BitmaskPhysic` + soloist 脉冲适合实时事件 |
| 客户演示，要古典美感 | **v2** | 衬线 + 米色，正式感 |
| 极客感、数据流体验 | **v3** | HEX/SYNAPTIC 字符栅格 |
| 深度架构探索（debug、长会话） | **v2** | 静态、不分散注意力 |
| 想要"读一篇文章"的感觉 | **v2** | manifesto 文字迷宫呼应阅读体验 |

切换组件：`TextVariantSwitcher`（右下角 `[ V2 / V3_FIELD ]`），localStorage key `arena_variant` 持久化。

---

## 演进史（参考 .tasks/TASKS.md）

variant 系统不是一开始就有的——经过几次架构演进：

- **V11 (ARENA-205)**：生成式演化迷宫拓扑（共享）— 双 variant 都用
- **V12 (ARENA-208/210)**：LOD + Sine LUT 性能极限优化（v3 主导，4K 60FPS）
- **V13 (ARENA-214 → ARENA-227)**：神经元数据风暴重塑（**v3 主导**）— HEX 流 + 二次鼠标排斥 + 3D 深度梯度 + 高斯光晕收紧
- **V14 (ARENA-223 → ARENA-230)**：大厅诗意拓扑重制（**v2 主导**）— 衬线体 + 分散布局 + Playfair Display 集成

> v3 的演进偏物理引擎深化，v2 的演进偏排版美学回归。**两条线分头进化**——
> 这正好印证了 variant 不是 A/B 选项，是两个独立宇宙各自迭代。

---

## 反模式：哪些设计选择会破坏 variant 哲学

| 反模式 | 后果 |
|--------|------|
| v2 加 cyberpunk 紫蓝渐变 / 字符栅格背景 | 违背手稿气质，让 v2 成为 v3 的次品 |
| v3 用衬线主标题 / 米色背景 | 破坏合唱场的算法律动 |
| v2/v3 用同一套 component 不做 variant 区分 | 失去「双重宇宙观」核心命题 |
| 在 variant 切换时只改 background color | 应该是物理引擎、字体、padding、obstacle 策略整体切换 |
| 把 variant 设计成「主题切换」类的 UI sugar | 它是认知架构选择，不是 dark/light mode |

如果设计师 / engineer-e 不确定某个视觉选择属于哪边，问自己：
**「这是档案学家会做的吗？还是合唱团长会做的吗？」**

---

## 决策记录扩展

未来 V15+ 演进新增 variant？请按以下模板扩展本文档：

1. 一句话定义（i18n `variantMeta.<id>`）
2. 美学决策表（颜色 / 字体 / 物理 / accent / 节奏）
3. 标志性元素 5 条
4. 不该出现 4 条
5. 何时选这个 variant 的 4 条用户场景
6. 与现有 v2/v3 的"宇宙观"关系（互补 / 替代 / 子集）

---

## 相关文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) — 5 层平面 / Provider / variant registry 实现
- [PHYSICS.md](./PHYSICS.md) — `BitmaskPhysic` / `LabyrinthPhysic` / `ChorusPhysic` / `ManuscriptPhysic` 工作原理
- [DESIGN_WORKFLOW.md](./DESIGN_WORKFLOW.md) — 三种设计入口 + handoff 给 ClawSeat
- [src/content/zh-CN.ts](../src/content/zh-CN.ts) — `variantMeta` 定义（中英双语）
- [src/variants/registry.ts](../src/variants/registry.ts) — variant 视图分发表
- [.tasks/TASKS.md](../.tasks/TASKS.md) — V11 / V13 / V14 演进任务
