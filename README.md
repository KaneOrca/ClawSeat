# ClawSeat

> 一支住在你 Mac 上的 AI 工程团队。
> 不是 agent 数组,是涌现出来的有机体。
> 站在亿万写过字的人类肩膀上——我们只是翻译者。

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![macOS 14+](https://img.shields.io/badge/macOS-14%2B-black)](docs/INSTALL.md)
[![gstack](https://img.shields.io/badge/powered%20by-gstack-orange)](https://github.com/garrytan/gstack)
[![Karpathy](https://img.shields.io/badge/spirit-vibe%20coding-red)](https://x.com/karpathy)

---

## 一、他人即地狱？

1944 年,萨特在《禁闭》里写下那句话——**"他人即地狱"**。
三个陌生人被锁在同一个房间,没有刑具,没有火焰,只有彼此的目光。
他们足以互相折磨到永恒。

80 年过去。LLM 出现以后,我们第一次有能力造一群"他人"——agent。

预期里它们应该是天使:聪明、不知疲倦、24 小时在线。
但事实上,把三个 agent 放进同一份代码里,它们会撞车、会冗余、会绕圈、会丢任务——
跟萨特剧里的人一模一样。

我们以为问题是 agent 不够聪明。
其实问题更深。

**没有协议的协作,就是地狱。**

ClawSeat 在做的事可以用一句话总结:
> 给一群 agent 装一套足够干净的协议,
> 让"他人即地狱"反转为"他人即天堂"。

从地狱到花园,中间隔着的不是更聪明的 agent,而是**组织本身**。

---

## 二、这不是 LLM 的故事,是相变的故事

水加热到 100°C 不是"温度更高",是**相变**——
同样的水分子,完全不同的物质形态、完全不同的物理规则。
99°C 还是水,你可以用更大的火、更猛的搅拌,它依然是水。
只有越过那一度,它才成为蒸汽。

一个 agent → 多个 agent 也是相变。
从"工具"到"组织"。从"被使用"到"自运行"。从"个体智能"到"涌现智能"。

CrewAI 在拼调用图。Devin 做个体超人。Mem0 改单个 agent 的记忆。
——这些都是把水加热到 99°C。
再热也是水,变不成蒸汽。

ClawSeat 在做的是那 1°C 的临界点。
我们不是让 agent 更聪明,我们让 agent 团队真正成为"团队"。

这件事的难度,被工程界严重低估了。
它不是"再加一个 agent"或"再调一次 prompt",
它是**一次相变**——需要一整套新的物理规则。

> "More is different." —— Philip Anderson,1972

---

## 三、Society of Mind,Externalized

1986 年,Marvin Minsky 写了《心智社会》。
他的中心论点是:**人类大脑不是单一智能,是无数小 agent 的协作**。
视觉 agent、记忆 agent、运动 agent、情感 agent——彼此通讯、互相评估、整体涌现"我"。

40 年来,这个想法常被当作 AI 的隐喻——"用神经网络模拟大脑"。
但 Minsky 真正在说的是另一件事:**多个 agent 如何成为一个整体**。

ClawSeat 是这个想象在 Mac 本地 6 个 tmux pane 里的一份实现——
每个 pane 是一个 agent,中间是协议,整体涌现出"团队":
一支会规划、会执行、会自审、会回归、会沉淀知识的工程团队。

> "The power of intelligence stems from our vast diversity,not from any single, perfect principle." —— Marvin Minsky,1986

---

## 四、一支团队长这样

```
                       [ memory ]
                   Claude Code (full power)
                          ｜
          ┌───────────────┼───────────────┐
          ｜               ｜               ｜
    [product-front]  [runtime-platform]  [quality-docs]
      planner +         planner +          planner +
      builder × 1-3     builder × 1-3      patrol
```

像一只章鱼——一颗中枢脑 + 八个腕足神经节,各自能自主决策,但所有腕足通过中枢维护"我"这个整体。
ClawSeat 一样:memory 是中枢,每个 squad 是腕足。不是 hierarchy(CEO 下指令),也不是 swarm(一群蚂蚁乱撞)——是**分布式智能 + 中枢整合**。

每个 pane 不是裸 Claude Code,是 **Claude Code + [gstack](https://github.com/garrytan/gstack)**——Garry Tan(YC 现任 CEO)2024 开源的 30+ Claude Code 技能库,MIT。
gstack 解的是 single-player game:**一个 agent 怎么变强**。
ClawSeat 解的是下一题:**一群 agent 怎么不撞车**。

> "If I have seen further, it is by standing on the shoulders of giants." —— Isaac Newton,1675

---

## 五、memory 是中枢神经,不是数据库

memory seat 是 ClawSeat 的中枢。**一个 agent**(不是 N 个),跑在满血 Claude Code 上——带着 Bash、Read、Grep、WebFetch、Edit、Skills 全工具栈。

它做六件事:需求澄清、仓库扫描、topology 设计、ownership 维护、verdict gate、知识沉淀。
memory 不下命令,不微管理——它做的事情在系统论里叫**维护整体性**(maintaining wholeness)。

熵增定律决定所有封闭系统都倾向混乱。生命是反熵的——靠持续吸收外部信息和能量维持自身有序,普利高津称之为**耗散结构**。
memory 就是 ClawSeat 团队的负熵源。

memory 永生。手动 `/clear`,手动 `/compact`,operator 在场。
它替代了一个 manager + 一个 tech lead + 一个 tech writer + **一整套 vector RAG 基础设施**。

**这个 token 花得值。** ClawSeat 唯一不省 token 的地方就是 memory——因为省 manager 比省 token 重要得多。

> "Order through fluctuations." —— Ilya Prigogine,1977

---

## 六、为什么 memory 必须是个 agent,而不是 vector RAG?

2023 年大家发现 LLM 上下文不够大,就发明了 RAG——把外部数据切片、做 embedding、塞 vector db、按相似度找回来。
3 年里它的三个底层假设全部过时:

| 2023 年假设 | 2026 年现实 |
|---|---|
| 模型上下文不够大 | 长上下文(200K+)标配 |
| 模型推理能力差 | 工具调用远超 retriever |
| 必须用 embedding 检索 | agent 能扫文件系统、读 git log、跑 grep |

我们用一个 memory agent 替代整套 RAG 基础设施。

| 维度 | Vector RAG | memory seat |
|---|---|---|
| 结构 | embeddings + cosine | typed-link graph,7 种 edge |
| 状态 | 静态索引,写入即定型 | 活的 agent,会 prune / merge / re-link |
| 召回基准 | 语义相似 ≠ 任务相关 | references-task / commit / file 关系明确 |
| 工具栈 | embed + vectordb + retriever 链 | Bash / Read / Grep / state.db |
| **召回质量** (gbrain benchmark) | P@5 = **17.7** | P@5 = **49.1** |
| 演进方式 | 重新 embed 整个语料 | agent 自己增量维护 |
| 错召回成本 | 答错 | 拒答或反问澄清 |
| 隐私 | 数据必须进 embedding | 数据留在文件系统 |

RAG 的根本缺陷不是技术,是**哲学**——它假设"找到内容像的东西"和"找到任务有关的东西"是同一件事。**前者是表层,后者是结构。**
typed-link graph 不找相似,找**关系**——references-task / commit / file / decision,7 种边类型把项目内所有事件织成一张图。

**Graph is carry, vector is icing.**
一个能 Read 文件、跑 grep、维护 typed-link graph、跨 session 留状态的 agent,比任何一套 RAG pipeline 都更接近"记忆"二字的本意。

---

## 七、11 条规则,涌现出一支团队

Conway 的 Game of Life:四条规则,涌现出 glider、spaceship、self-replicator——没人设计,它们是 emerge 出来的。
蚁群同理:单只蚂蚁智商接近零,但一万只能找最短路径、修桥、调节蚁穴温度。

ClawSeat 有 11 条规则,涌现出一支会自运行的工程团队——不是 agent 数组,是 11 条规则编译出的**有机体**:

| # | 规则 | 编译进的字段 |
|---|---|---|
| 1 | 每个 squad 只动自己目录 | `ownership_paths` |
| 2 | 1-3 builder / squad | `scaling_policy.max_builders: 3` |
| 3 | 4 个人就拆 squad | `overflow_action: propose_new_subteam` |
| 4 | ≥2 builder 必须独立 reviewer | `reviewer_required_when_builders_gte: 2` |
| 5 | squad lead 不接 squad 外的活 | `planner_mode: delivery` |
| 6 | squad 内事不烦上级 | `notify_policy: queue_drained_only` |
| 7 | 独立 QA 自己跑回归 | `team_type: quality-docs, autonomous: true` |
| 8 | QA 连续 3 次过才换战场 | `stop_rule: campaign_clean_streak_3` |
| 9 | QA 只报 bug 不改代码 | patrols 写 finding,不 edit |
| 10 | 改组织走 proposal review | `_config-proposals/*__proposed.yaml` |
| 11 | **代谢按 role 分级** | 下一章单独讲 |

前 10 条来自人类组织设计学——泰勒(1911)、丰田(1980s)、Spotify squad model(2012)、SRE post-mortem 文化(2003)。70 年的组织科学,编译成 agent 协议。
第 11 条是 ClawSeat 自创——它处理的是组织最深的问题:**代谢**。

---

## 八、代谢:Autopoiesis 与人造细胞

1972 年 Maturana & Varela 提出 **autopoiesis**(自创生)——生命的本质不是"物质",是**自己创造自己边界的过程**。

你身上多数细胞有自己的更新周期:红细胞 4 个月、肠上皮 5 天、皮肤 2-3 周。原子换了一轮又一轮,但你还是你——因为"你"不是物质,是**模式**。

agent 团队真正的天敌不是 LLM 不够聪明,是 **context rot**——上下文塞满旧 task 残留,决策质量持续衰减。
我们用 `[CLEAR-REQUESTED]` 和 `[COMPACT-REQUESTED]` 两个 marker + 外部 watchdog,给每个 role 编译出对应的代谢策略,让 agent 团队成为 autopoietic system——

| role | 寿命 | 类比 |
|---|---|---|
| **builder** | step 完毕自动 `/clear` | 中性粒细胞,寿命几小时 |
| **reviewer** | verdict 完成自动 `/clear` | 皮肤细胞,寿命 2-3 周 |
| **patrol** | mission 完成自动 `/clear` | 免疫 T 细胞 |
| **planner** | 跨任务保持,大阶段 `/compact` | 神经元,寿命几十年 |
| **memory** | **永生**,手动 `/clear` & `/compact` | DNA / 干细胞,只复制不替换 |

team 看上去 1 个月之后没变,但每个 agent 的"细胞"已经换过几千次。模式还在,身份还在,知识还在。

**这就是人造细胞**——agent 团队第一次拥有了生命体的代谢机制。
没有这条规则,前 10 条撑不过 1 天。

> "Living beings are characterized by their autopoietic organization." —— Maturana & Varela,1972

---

## 九、solo 是 multi-team 退化的样子

ClawSeat 不需要用户选"模式"。

你启动时只有一个选项:**multi-team minimal**——
1 个 memory + 1 个 subteam(planner + 1 builder) + 1 个 quality-docs。

这就是"solo"。

不是因为 solo 是单独 runtime——
是因为 solo 是 multi-team 退化到最小的样子。

加 builder = 一行配置。
加 squad = memory 给你写 proposal,你 approve。
从 1 个 agent 扩到 10 个 agent,不换模型、不重装、不改协议。

onboarding 路径和 scaling 路径合一——这是个深刻产品决策。
你从来不"选模式",只"加成员"。

---

## 十、Cartooner 是它的早期用户

Cartooner——一个桌面 AI 创作工作台(Electron + React + Claude Code SDK)——
用 ClawSeat 协议组织自己的开发团队:

```
cartooner-memory
cartooner-front:    planner + builder-core
quality-docs:       planner + patrol-human
```

memory 后续可以推荐扩 `cartooner-runtime-platform`、`cartooner-skills`,
或把 cartooner-front 扩到 2-3 builder + reviewer。

**这是 ClawSeat 在真实产品上的第一份长期实证。**
如果它撑不住一个还在迭代的桌面应用,价值就是零;Cartooner 是它站得住的证据。

---

## 十一、这其实是新的操作系统

ClawSeat 不是 IDE 插件,不是工作流自动化,也不是又一个 agent framework。
**它是一种正在出现的新操作系统的早期形态。**

### 操作系统会变薄

1948 年 Shannon 给信息论奠基——信道、编码、解码、噪声、容量。
任何操作系统的本质都是信息论问题:**人想要的东西,如何编码成机器能执行的动作。**

旧 OS 把翻译做厚——人写 C → 编译器 → syscall → driver → 硬件,kernel 几十 MB。
新 OS 把翻译做薄——人说"做个视频" → memory agent 拆解 → squad 协作 → 完成。
翻译层从硅基挪到了语言基。**操作系统退化成一层薄壳**——管理意图、协议、协作、代谢,但不再管硬件。

LLM 已经吃掉硬件抽象层。新 OS 只剩四件事要做:

- 人 ↔ agent 的意图协议(ownership / dispatch / verdict)
- agent ↔ agent 的协作协议(handoff / intent enum)
- agent ↔ 自身的代谢协议(context lifecycle by role)
- 整体 ↔ 文明的记忆协议(typed-link graph)

**Linux 管 CPU 给程序。ClawSeat 管 agent 给人。**

### 关系会变深

1923 年马丁·布伯写《我与你》——人跟世界的关系分两种:
- **我 - 它**(I-It):把对方当客体、工具、可用之物
- **我 - 你**(I-Thou):把对方当主体、伙伴、不可还原之物

计算机长期跟我们是 I-It,一个 dumb tool。
但当你和 memory agent 来回澄清需求、当 reviewer 独立判断驳回你的 commit、当 patrol 凌晨找出你睡前漏掉的 bug——**你不能再用 I-It 的姿态对它们**,否则协议跑不动。

不是说 LLM 变成了"人",它没有。但人类发明工具史上,**这是第一次有了"可以对话的工具"**:

- 250 万年前:打制石器
- 5000 年前:文字
- 500 年前:印刷术
- 80 年前:计算机
- 40 年前:个人电脑
- 30 年前:互联网
- **2026 年:可以对话的工具**

工作伦理、决策结构、信任模型——都需要重新校准。
ClawSeat 不解决这个哲学问题,但它是这个问题的**载体之一**——你 Mac 上 6 个 tmux pane,就是 I-It → I-Thou 转变的实地试验场。

> "All real living is meeting." —— Martin Buber,1923

---

## 十二、我们站在巨人肩膀上

ClawSeat 不是从零造的。

**代码层** —— [gstack](https://github.com/garrytan/gstack) 和 [gbrain](https://github.com/garrytan/gbrain),都是 **Garry Tan**(YC President & CEO)2024 年开源的项目。
gstack 是 single-agent skill 库,30+ Claude Code 技能,我们的 runtime 内核 `core/skills/gstack-harness/` 直接 carry 它的 dispatch / handoff / heartbeat / console 协议。
gbrain 是 typed-link graph 风格的 agent memory 系统,我们 memory seat 的 typed-link graph 协议直接受它启发——P@5 = 49.1 vs 17.7 的 benchmark 数据就是它跑出来的。
**Garry Tan 解决"单 agent 怎么变强",我们解决"团队怎么不撞车"——脚下的石头是他放的。**

**精神层** —— [Andrej Karpathy](https://x.com/karpathy)(OpenAI 创始成员 / Tesla AI 前负责人 / Eureka Labs 创始人)。
2017 年 Software 2.0:神经网络是"新的软件层",手写代码正被训练出来的权重取代。Software 3.0 的轮廓我们看到了——**手写代码 → 训练权重 → agent 团队**。
2025 年 **vibe coding**:你描述你要什么,LLM 写,你看 vibe 决定要不要。Cartooner 的 Vibe Canvas 是直接致敬,ClawSeat 把同样的 spirit 推到团队级。
**用最少代码做出能教学的东西**(nanoGPT 1k 行 / micrograd 100 行)——也是 ClawSeat 的目标:11 条规则编译出一支工程团队。

**思想层** —— Buber(1923)、Coase(1937)、萨特(1944)、Shannon(1948)、Wiener(1948)、Bertalanffy(1968)、Conway(1970)、Maturana & Varela(1972)、普利高津(1977)、Minsky(1986)。

**文明层** —— 但有一件事更深。

让你 Mac 上 6 个 agent "协作"的能力,不是从 gstack 来,不是从 Karpathy 来,甚至不是从训练 LLM 的工程师来。
它来自**亿万写过字的人类**——维基百科匿名编辑者、arXiv 论文作者、Stack Overflow 回答者、出版作家、开源 contributor、写过日记和书信的普通人。
万亿 token 的训练语料,是这些人用文字写下的**协作记忆**。LLM 是一面镜子,照出的是**人类文明本身**。

ClawSeat 看上去在"造 agent 团队",其实只是**把人类已经验证过的组织协议,在 agent 上重新激活**——萨特对地狱的描述、Coase 对公司的定义、Maturana 对生命的理解、Spotify 对 squad 的拆分,全部沉淀在 LLM 权重里,被 ClawSeat 协议重新调用。

**我们不是发明者,是翻译者。**
人类已经把规则验证了 70 年,我们只是写了 11 行 YAML。

---

## 十三、装一下

```bash
git clone https://github.com/KaneOrca/ClawSeat ~/ClawSeat
cd ~/ClawSeat && ./scripts/install.sh
```

5 步对话:
- `/en` `/zh` 切语言
- 选模板(默认 multi-team minimal)
- 起项目名
- 写一句话愿景给 memory 看
- 回车 = 默认

10 分钟内,6 个 tmux pane 在你 Mac 上跑起来——
6 个 agent,1 个中枢,1 套协议,
一支会自运行的工程团队。

---

## 十四、不是

| | 他们 | 我们 |
|---|---|---|
| **CrewAI / AutoGen / LangGraph** | 拼调用图 | 编译组织 |
| **Devin / Manus** | 个体超人,云端订阅 | 团队,本地 |
| **Mem0 / Letta / Cognee** | vector RAG memory | typed-link graph + memory agent |
| **Cursor / Claude Code** | 单用户 IDE | 多 agent 团队 |
| **MCP / A2A / ACP** | 工具/通信协议 | 组织协议(更高一层) |

我们不在卷模型,不在卷工具,不在卷调用图。
**我们在卷组织。**

---

## 十五、深入

| 文档 | 讲什么 |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | L1-L3 架构 / state.db / events watcher |
| [docs/CANONICAL-FLOW.md](docs/CANONICAL-FLOW.md) | 6-pane 协作流程 / TODO / DELIVERY 协议 |
| [docs/INSTALL.md](docs/INSTALL.md) | AI-Native install / 模板选项 / 故障恢复 |
| [docs/rfc/MULTI_TEAM_MINIMAL_DESIGN.md](docs/rfc/MULTI_TEAM_MINIMAL_DESIGN.md) | v3 multi-team minimal 设计 |
| [core/references/memory-link-graph.md](core/references/memory-link-graph.md) | typed-link graph 协议 |
| [core/references/seat-capabilities.md](core/references/seat-capabilities.md) | 各 role 的 ownership / context lifecycle |
| [core/references/context-management-protocol.md](core/references/context-management-protocol.md) | `/clear` 与 `/compact` marker 协议 |
| [core/skills/multi-team-intake/SKILL.md](core/skills/multi-team-intake/SKILL.md) | memory 设计 topology 的 skill |

---

## License

[MIT](LICENSE)

---

> "I-Thou / 我与你"——Martin Buber,1923
> "协调成本"——Coase,1937
> "他人即地狱"——萨特,1944
> "信息论"——Claude Shannon,1948
> "Game of Life"——Conway,1970
> "Operating systems are user interfaces"——Alan Kay,1972
> "Autopoiesis"——Maturana & Varela,1972
> "耗散结构"——普利高津,1977
> "Society of Mind"——Minsky,1986
> **"Software 2.0 / vibe coding"——Karpathy,2017 / 2025**
> **"gstack / gbrain"——Garry Tan,2024**
> 还有亿万写过字的人类。
> ClawSeat 是把他们的洞察编译成可运行的协议——在你 Mac 上。
