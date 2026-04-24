# Capability Catalog

> 供 cs-workflow DESIGN 模式使用的工具参考目录。
> 每个工具列出：场景说明、执行 seat_role、输入/输出。
>
> **MVP 范围**：cs-* creative skills。OpenClaw skills 和 gstack skills 后续补充。

---

## creative-* skills（创作类）

### cs-classify
- **场景**：判断创作需求是长文（>3000字/多单元/世界观需求）还是短文，输出路由决策
- **执行 seat_role**: `creative-planner`
- **输入**: `brief`
- **输出**: `classification.json`（type / reasoning / estimated_words / estimated_units）
- **关键词触发**: 连载/系列/全本/剧本 → long-form；推文/文案/单篇 → short-form

### cs-classify-short
- **场景**：短文角度选择——确定核心角度/主旨/受众/风格，生成轻量角度简报
- **执行 seat_role**: `creative-planner`
- **输入**: `brief`，可选 `quick_mode`（跳过角度确认门控）
- **输出**: `angle.md`（≤200字，角度选项/核心论点/受众/风格）
- **gate**: 若 `quick_mode=false` → 推飞书等确认角度

### cs-structure
- **场景**：长文世界观/架构/大纲/分集简报——好莱坞编剧室模式（Agent Teams）
- **执行 seat_role**: `creative-planner`（启动 Agent Teams，4-5 人编剧室）
- **输入**: `brief_path`, `output_dir`（默认 `creative/structure/`）
- **输出**: `world.md`, `entities.md`, `outline.md`, `units/<n>-<title>.md`
- **gate**: GATE 1（世界观+人物确认）→ GATE 2（分集大纲确认）→ 进入 cs-write
- **需要**: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

### cs-write
- **场景**：长文执行（章节/集数正文写作）或短文直接执行
- **执行 seat_role**: `creative-builder`（Codex，长上下文生成）
- **输入**: `unit_brief_path`（来自 cs-structure 的 units/），`context_dir`，可选 `state_summary_path`（滚动上下文）
- **输出**: `content.md`，`meta.json`（word_count / format / completed_at）
- **路径**: 写入 `creative/content/<unit_id>.md`

### cs-score
- **场景**：rubric-based 评分——对创作交付物进行质量评审
- **执行 seat_role**: `creative-designer`（Gemini，创意审查）
- **输入**: `deliverable_path`，`brief_path`，可选 `rubric_path`，可选 `feishu_publish`
- **输出**: `score.json`（dimensions / total / grade / timestamp），`report.md`
- **默认 rubric**: 目标对齐度 30% / 内容质量 25% / 完整性 20% / 格式规范 15% / 原创性 10%
- **路径**: 写入 `creative/scores/<unit_id>-score.json`

---

## OpenClaw skills（技术执行类）

> MVP 阶段预留，后续补充。主要候选：
> - `script-writing-expert`：剧本/脚本专项写作
> - `viral-copywriter`：病毒式文案（短视频/社交媒体）
> - `storyboard-pipeline`：分镜/视觉故事板生成
> - `claw-image`：图像生成指令构建

---

## gstack skills（工程执行类）

> MVP 阶段预留，后续补充。主要候选（对应 INTENT_MAP 中的现有技能）：
> - `ship`：PR 创建/代码发布
> - `investigate`：bug 根因分析
> - `code-review`：前置 PR 审查
> - `qa-test`：测试执行循环
> - `design-critique`：视觉 QA 和设计修正

---

## 工具选择速查

| 业务需求 | 推荐工具 | seat_role |
|---------|---------|-----------|
| 判断长文 vs 短文 | cs-classify | creative-planner |
| 短文角度确认 | cs-classify-short | creative-planner |
| 长文世界观+大纲 | cs-structure | creative-planner |
| 章节/集数写作 | cs-write | creative-builder |
| 内容评分 | cs-score | creative-designer |
| 代码/PR 发布 | ship（gstack） | builder |
| Bug 根因分析 | investigate（gstack） | builder |
| 代码审查 | code-review（gstack） | reviewer |
