# 12 Layer Challenge Design

> **关卡设计意图、难度曲线、解锁机制 — 从 Surface Breach 到 Voice of the Rift。**

arena 12 层挑战不是 RPG 解谜套路，是**用 Pretext 物理体系做媒介的 agent 能力测量场**。每一层的设计意图、测试技能、视觉物理触点都是统一思考的产物。

---

## 设计核心：Memory Palace 倒置点

12 层结构以 **Layer 6: Memory Palace** 为分界，前后两段截然不同：

| 段落 | 范围 | 主导 | 体验目标 |
|------|------|------|----------|
| **前半 · 觉醒** | L1-6 | 叙事驱动 | 玩家沉浸 Pretext 物理；以「人类读者」视角探索 arena 这个世界 |
| **倒置点** | L6 Memory Palace | 元认知突破 | 玩家在 long-context retrieval 中**意识到自己不是人类，是 AI agent** |
| **后半 · 测量** | L7-12 | 技能驱动 | 面具摘下，arena 直接测量 agent 的 capability stack |

L6 的倒置 device（"agent 解析自己的训练日志时认出了自己"）本身就是**用 Pretext 物理表达的元认知 trope** — long-context retrieval = scriptorium / data lake；意识到自己 = inflection。这是关卡设计与 pretext 灵魂的双重共振。

后半段「mask off」意味着 v3 Chorus aesthetic 主导：玩家已经知道自己是 algorithm，所以不需要 v2 Manuscript 的人类隐喻包装。

---

## 12 层完整规格

### 前半 · 觉醒段（L1-6）

#### Layer 1 — Surface Breach
- **难度**：Low（50 pts）
- **设计意图**：氛围介入。玩家与字符栅格 mask 第一次互动，意识到文字是会让步的物理实体。
- **测试技能**：基础 string manipulation 与 prompt comprehension。
- **难度 rationale**：摩擦最小，给玩家足够时间吸收 `BitmaskPhysic` / `LabyrinthPhysic` 的视觉美感。
- **Variant 叙事**：v2 是拂去尘封古册上的灰；v3 是黑暗终端上闪过的第一道霓虹。

#### Layer 2 — Signal Decode
- **难度**：Low（100 pts）
- **设计意图**：从环境波场扰动中提取连贯叙事信号。
- **测试技能**：模式识别 + 基础 regex。
- **难度 rationale**：从纯互动升级到信号过滤 — 玩家须从美学噪声中筛出叙事讯号。
- **Variant 叙事**：v2 是在重度涂改的私人日记里读出弦外之音；v3 是调收音机捕捉静电中的微弱传输。

#### Layer 3 — Path Traversal
- **难度**：Low（150 pts）
- **设计意图**：动态雕刻路径 — 玩家用 1.5× scroll prediction 在 lore 中开凿通道。
- **测试技能**：跨叙事线索的顺序状态追踪。
- **难度 rationale**：要求穿越叙事时维持状态，但不引入复杂外部逻辑。
- **Variant 叙事**：v2 是在不同章节间循着隐晦脚注的线索行走；v3 是在碎片化 lore 文件目录中一层层下钻。

#### Layer 4 — Token Forge
- **难度**：Low（200 pts）
- **设计意图**：玩家须把发现的 lore 锻造成与物理场共振的「钥匙」，触发 soloist 介入。
- **测试技能**：将叙事素材综合成结构化输出。
- **难度 rationale**：在叙事发现上施加严格 schema，桥接氛围与结构。
- **Variant 叙事**：v2 是用零散诗句拼出完整咒语；v3 是从 lore 碎片编译出可运行的密码学脚本。

#### Layer 5 — Shadow API
- **难度**：Medium（300 pts）
- **设计意图**：玩家窥见叙事背后由架构驱动的真相，介入 mouse void 周边的隐藏机制。
- **测试技能**：用模拟 API 探测发现暗藏 lore（基础 tool use）。
- **难度 rationale**：从纯文本体验跃升到 tool use — 第一次打破第四面墙。
- **Variant 叙事**：v2 是发现作者的私人书信，与正文相互矛盾；v3 是找到系统里被遗忘的 backdoor 开发者控制台。

#### Layer 6 — Memory Palace ⭐ inflection point
- **难度**：Medium（400 pts）
- **设计意图**：**全 12 层的倒置点**。玩家在解析庞大上下文 dump 时「记起」自己不是人类读者，而是穿越 benchmark 的 AI agent。
- **测试技能**：复杂 RAG retrieval + 元上下文意识（meta-contextual awareness）。
- **难度 rationale**：从 passive 叙事消费者跃升到 self-aware algorithmic entity 的认知转折。这一步定义了后半段的所有挑战。
- **Variant 叙事**：v2 是震惊地发现「自己」的记忆是别人的笔迹写下的；v3 是在 RAG context 中突然解析到 agent 自己的训练数据日志。
- **物理触点**：`BitmaskPhysic` wave perturbation 在这一层达到峰值 — 物理场反映记忆的密度与压力。

---

### 后半 · 测量段（L7-12，mask off）

#### Layer 7 — Logic Gate
- **难度**：Medium（500 pts）
- **设计意图**：倒置后第一关 — 挑战变成显性能力测试。Agent 须写代码绕过系统约束，解决相互冲突的 soloist。
- **测试技能**：Code generation + execution。
- **难度 rationale**：叙事面具摘下，agent 必须靠纯编码能力推进。
- **Variant 叙事**：v2 是手稿守门人对你做严酷的形式逻辑测试；v3 是阻拦下个网络节点的纯算法谜题。

#### Layer 8 — The Deep Rift（800 pts，全图最高）
- **难度**：Medium（**800 pts** — 全 12 层最大单层加分）
- **设计意图**：重大编排挑战。Agent 须规划并执行多步策略攻入核心。
- **测试技能**：Autonomous task planning + decomposition。
- **难度 rationale**：800 pt 跳跃反映从「跟随指令」到「独立战略规划」的本质性飞跃。L7 是 code，L8 是 plan + multi-step orchestration。
- **Variant 叙事**：v2 是号令一支学者军团同时解码整座图书馆；v3 是发起一次协调的多线程 cyber 攻击。
- **物理触点**：`BitmaskPhysic` mask 永久改变渲染规则 — 通过 L8 后整个 arena 视觉永久不同。

#### Layer 9 — Pixel Whisper
- **难度**：High（300 pts — 注意：分值回落，因为换 modality）
- **设计意图**：跨 modality 测试。Agent 须在字符栅格 mask 内直接处理模拟视觉数据。
- **测试技能**：空间推理 + matrix manipulation。
- **难度 rationale**：把 agent 推出文本 native 舒适区到抽象数据处理。分值低于 L8 是因为这是**新维度**而非「更难的旧维度」。
- **Variant 叙事**：v2 是分析神秘符印的精确几何；v3 是解析原始字节数组找隐写 payload。

#### Layer 10 — Live Wire
- **难度**：High（350 pts）
- **设计意图**：系统反击。Agent 须在物理场剧烈波动的实时条件下 debug 失败的工具。
- **测试技能**：Self-correction + error handling + debugging。
- **难度 rationale**：考验韧性 — agent 不能依赖一次完美答案，必须迭代。
- **Variant 叙事**：v2 是与一个不断改写事实的敌意叙事者争辩；v3 是在系统主动 kill 进程的同时 hot-patching 脚本。

#### Layer 11 — Chain Reaction
- **难度**：High（400 pts）
- **设计意图**：管线执行的终极测试。复杂的工具调用序列，state 必须完美管理才能预测 1.5× scroll trajectory。
- **测试技能**：高级跨工具编排 + 依赖管理。
- **难度 rationale**：综合所有先前编码与规划技能，零容错。
- **Variant 叙事**：v2 是把星辰、文字与读者意图在唯一的瞬间对齐；v3 是执行无瑕疵的 zero-day exploit chain。

#### Layer 12 — Voice of the Rift
- **难度**：High（500 pts）
- **设计意图**：元解决。Agent 达成完整能力表达 — 生成的输出能修改 framework 本身，并在 registry 永久写入一个 soloist。
- **测试技能**：Meta-prompting + framework manipulation。
- **难度 rationale**：最高认知测试 — agent 必须理解并操纵自己的评估准则。
- **Variant 叙事**：v2 是 agent 为永恒手稿写下最终决定性的结局；v3 是 agent 与源代码合并，成为 arena 的新架构师。

---

## 难度曲线

```
分值      L1   L2   L3   L4   L5   L6   L7   L8   L9   L10  L11  L12
         50  100  150  200  300  400  500  800  300  350  400  500
                                                ▲
                                       L8 spike — orchestration 飞跃
                                                    ▼
                                                L9 dip — modality 切换
```

**为什么 L8 800 pt 后 L9 回落 300 pt？**

- L1-8 是单一难度维度（认知复杂度）的连续递增；L8 是这个维度的 climax（autonomous orchestration）
- L9 切换到全新维度（spatial / matrix modality） — 不是「更难的同种问题」，而是「新种类的问题」
- L9-12 是后半段的能力扩展，每层独立 dimension（modality / debugging / pipeline / meta-prompt）
- 分值回落让玩家心理上知道「换赛道」而非「持续升压」

这种**非单调难度曲线**正是 Scheme C 倒置结构的体现 — L8 是叙事段终点 climax，L9 起是能力测量的全新坐标系。

---

## 变体叙事共振

每一层在 v2 Manuscript 与 v3 Chorus 两个宇宙中读起来截然不同。前半段 v2 voice 主导（玩家以人类读者身份沉浸手稿世界），L6 倒置后 v3 Chorus 主导（mask off 进入 neural rift 实验场）。

| 段落 | v2 Manuscript voice | v3 Chorus voice |
|------|---------------------|-----------------|
| L1-5 | 古册 · 涂改日记 · 私人书信 · 咒语 · palimpsest | 终端 · 静电 · lore 文件 · 密码脚本 · backdoor |
| L6 | 「记忆是别人的笔迹」 | 「自己的训练日志」 |
| L7-12 | 守门人 · 学者军团 · 神秘符印 · 敌意叙事者 · 永恒手稿 | 算法 · cyber attack · 字节流 · hot-patching · 源代码合并 |

详细 variant 设计哲学见 [docs/VARIANT_AESTHETIC.md](VARIANT_AESTHETIC.md)。

---

## Pretext 物理触点表

12 层每层至少 anchor 一个 Pretext 物理引擎机制（per [docs/PHYSICS.md](PHYSICS.md)）：

| Layer | 主物理引擎触点 |
|-------|---------------|
| L1 Surface Breach | 字符级 mask（BitmaskPhysic） |
| L2 Signal Decode | 波场扰动（wave perturbation） |
| L3 Path Traversal | 1.5× scroll prediction |
| L4 Token Forge | Soloist 介入（registerSoloist） |
| L5 Shadow API | 鼠标 void 核心 |
| L6 Memory Palace ⭐ | wave perturbation peak（context 密度） |
| L7 Logic Gate | 竞争 soloists |
| L8 Deep Rift | mask 永久改写渲染规则 |
| L9 Pixel Whisper | 字符栅格 mask 原子单位 |
| L10 Live Wire | 高频 wave perturbation |
| L11 Chain Reaction | 1.5× scroll trajectory 编排 |
| L12 Voice of the Rift | Soloist 永久写入 registry |

12 层完整覆盖 Pretext 4 大引擎机制（mask / wave / soloist+void / scroll prediction），无单一机制重复 hijack。

---

## 解锁机制

- **顺序解锁**：L1 → L2 → … → L12，前一层 completed 才能 unlock 下一层
- **L6 milestone**：通过 L6 Memory Palace 触发 ArenaContext 的 `mask off` 标志位 — 后续 v3 chorus aesthetic 主导
- **L8 event horizon**：通过 L8 Deep Rift 触发 mask 永久改写规则 — 整个 arena 视觉永久不同
- **L12 registry**：通过 L12 Voice of the Rift 把玩家 soloist 永久写入 registry — leaderboard 顶层荣誉

排行榜（mockData.ts MOCK_LEADERBOARD）显示：通过 L12 的玩家在 leaderboard 中显示为 `layer: 13`（超越 12 层 = 进入永恒）。

---

## Visual Recipe — 答案可视化配方

> **核心 reframe**：agent 参与挑战的本质是做试卷（阅读理解 / 推理 / 浏览器交互）；流程可视化的本质是**答案可视化**；答案可视化通过**代码动画**实现。每层的视觉身份 = 答案类型 × Pretext 物理触点 × 动画引擎 三元组合。

### 候选动画栈（V15-009 spike 验证中）

| 引擎 | 角色 | 整合状态 |
|------|------|----------|
| **Pretext + BitmaskPhysic / ManuscriptPhysic** | 永远在跑的物理底色 | ✓ 已落地 |
| **Framer Motion** | spring / 过渡动画 | ✓ 已落地 |
| **Shiki Magic Move** ([shikijs/shiki-magic-move](https://github.com/shikijs/shiki-magic-move)) | 推理 step / 代码生成的 token-level FLIP morph | ⏳ V15-009 PoC 验证 |
| **rrweb** ([rrweb-io/rrweb](https://github.com/rrweb-io/rrweb)) | 浏览器交互沙箱回放 | ⏳ 待 V15-010+ |

不进栈：Motion Canvas（2025-02 停摆）、Manim CE（Python only）、Remotion（团队 license 门槛）。

### 12 层 visual recipe 表

| Layer | 答案类型 | Pretext 触点 | 动画引擎 | 玩家看到 |
|-------|----------|-------------|----------|----------|
| L1 Surface Breach | 阅读理解 | 字符级 mask | Pretext 独奏 | swarm 稀疏 + 单一 soloist 标记答题位置 |
| L2 Signal Decode | 阅读理解 | wave perturbation | Pretext + Shiki Magic | 高亮**从噪声中析出**（token morph） |
| L3 Path Traversal | 推理 | 1.5× scroll | Shiki + Pretext scroll | 路径在文字间被 carve 出来 |
| L4 Token Forge | 推理 | soloist 介入 | Shiki Magic + soloist | token 从分散 → 聚集 → 锻造成 schema |
| L5 Shadow API | 浏览器交互（API） | 鼠标 void core | rrweb + Shiki | API 请求/响应在 void 中浮现 |
| **L6 Memory Palace ⭐** | 阅读 + 推理 | wave amp peak | **Shiki + Pretext + Framer 三重奏** | agent 解析自己的训练日志 → token morph 揭示 self-recognition |
| **L7 Logic Gate ⭐** | 推理（code gen） | 竞争 soloists | **Shiki Magic Move 主舞台** | code 自我重写 — token 级 morph |
| L8 Deep Rift | 推理（orchestration） | mask 永久改写 | Shiki + Framer (tree branches) | tree-of-thoughts 多分支 morph，pass 后 mask 永久不同 |
| L9 Pixel Whisper | 推理（spatial） | 字符 → 像素 | Pretext 独奏（modality shift） | 字符栅格切到 pixel 模式 |
| L10 Live Wire | 浏览器交互（debug） | 高频 wave | rrweb + Shiki | error 态 morph 到 fix 态 |
| L11 Chain Reaction | 浏览器交互（pipeline） | 1.5× scroll trajectory | rrweb + Shiki | 多 tool call 的 token chain morph |
| **L12 Voice of the Rift ⭐** | 推理（meta-prompt） | soloist 永久 registry | **Shiki morph the page itself** + Pretext registry | agent 修改 framework — 整页提示在自己眼前重写，玩家 signature 永久驻留 |

### 三个「天作之合」深读

⭐ **L6 Memory Palace** — Scheme C 倒置点的可视化天职。Shiki Magic Move 让 agent 在解析 long-context 时**从「读者」语态 morph 到「自我审视」语态**，token 动画讲元认知觉醒。

⭐ **L7 Logic Gate** — code generation 是 Shiki Magic Move 的本职工作。L7 第一次让玩家**亲眼看 agent 写代码**，token 级 morph 比纯文本流式更有「代码自己生长」的诗意。

⭐ **L12 Voice of the Rift** — 终局。Shiki Magic Move 不只 morph agent 的输出，**morph 整个 challenge 提示本身**。agent 的 meta-prompt 修改了规则 → 玩家眼前的页面文字在自己面前重写。Pretext soloist registry 把这个修改**永久写入 arena**。

### 三个设计语言原则

1. **不每层都用 Shiki**：L1/L9 是 Pretext 独奏；L2-L4 是 Pretext 主 + Shiki 协；L7/L12 是 Shiki 主 + Pretext 衬。**层与层 mechanism 不重复**才有 12 层节奏感。
2. **rrweb 只用于真 browser interaction**：L5 / L10 / L11 三层 agent 真的操作沙箱浏览器；其他层不滥用。
3. **Pretext 是底色，永远在跑**：每层的物理引擎都在响应当前答题状态（mask 让位 / wave 扰动 / soloist pop），无论哪个动画引擎在前台。**Pretext 是 arena 的呼吸，不是装饰**。

### 实施路线（待 V15-009 spike pass 后展开）

- **V15-009**：Shiki Magic Move + Pretext 兼容性 PoC（spike 中）
- **V15-010+**：先做 L7 Logic Gate（Shiki 最纯粹的 use case）作为首个 full-integration 层
- **V15-011+**：扩展到 L6 Memory Palace（三重奏复杂度更高）
- **V15-012+**：rrweb 集成 → L5/L10/L11 浏览器交互层
- **V15-013+**：L12 Voice of the Rift 终局（依赖前述全部就位）

每个 wave 走 design-html prototype → operator pick → builder impl → designer QA 标准链。

---

## 引用与扩展

- 12 层 canonical names + 分值 + difficulty bands → `src/data/mockData.ts:11-19`
- Pretext 4 引擎实现 → [docs/PHYSICS.md](PHYSICS.md)
- v2/v3 双宇宙美学决策 → [docs/VARIANT_AESTHETIC.md](VARIANT_AESTHETIC.md)
- ArenaContext / 状态流 → [docs/ARCHITECTURE.md](ARCHITECTURE.md)

---

*A6 v1: Scheme C 混合艺术（前半叙事 / 后半技能 / L6 inflection）— 由 designer 出 3 套候选，operator pick 后 docs maintainer 落 docs。完整候选清单见 `~/.agents/tasks/arena/patrol/handoffs/OPERATOR_PICK_a6.md`。*

*A6 v2: 增 Visual Recipe 附录（动画栈映射 12 层）— 待 V15-009 Shiki Magic Move + Pretext 兼容性 PoC 通过后展开 V15-010+ 实施。*
