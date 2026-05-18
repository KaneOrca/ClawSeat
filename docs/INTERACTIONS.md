# Arena 交互与特效词汇表

> 结构化、模块化的交互效果定义文档。所有特效的名称、触发条件、视觉表现均在此统一定义。

---

## 1. 全局物理效果

### 1.1 字符挤压 (Cell Push)

- **别名**: 鼠标推力、mouse push
- **引擎**: BitmaskPhysic
- **触发**: 鼠标光标存在于视窗内
- **停止**: 鼠标离开视窗
- **视觉**: 光标周围字符向远离鼠标方向位移，最大推力半径 ~108px (pushRadius 1.8 × 60px)，force = 24
- **平滑**: 帧间 lerp 0.2
- **文件**: `src/components/text-physics/BitmaskPhysic.tsx`
- **适用文本块**: 无需任何标记，对背景字符栅格全局生效

### 1.2 字符绕排 (Cell Flow)

- **别名**: 鼠标圆弦、mouse chord
- **引擎**: LabyrinthPhysic
- **触发**: 鼠标光标存在于视窗内
- **停止**: 鼠标离开视窗
- **视觉**: 背景文字行以圆形轮廓绕开鼠标，chord 半径 = 鼠标 obstacle 宽度 × 0.7
- **缓存**: 鼠标移动 <2px 不重算
- **文件**: `src/components/text-physics/LabyrinthPhysic.tsx`
- **适用文本块**: 无需任何标记，对 v2 背景文字流全局生效

### 1.3 波场涟漪 (Wave Ripple)

- **别名**: 高亮脉冲、amplitude surge
- **引擎**: PhysicsContext (waveAmplitude)
- **触发**: 鼠标 hover 进入 `data-functional-text="true"` 元素 → `useWaveRipple`
- **停止**: 600ms 后自动衰减回基线值 (60)
- **视觉**: 背景字符栅格整体变亮——BitmaskPhysic 的 lightness 因 surgeNorm 提升，LabyrinthPhysic 的 waveAmplitude 升高
- **振幅**: 60 → 120
- **文件**: `src/hooks/useWaveRipple.ts`
- **适用文本块**: 所有 `data-functional-text="true"` 元素

### 1.4 光标空洞 (Cursor Void)

- **别名**: ring glow、void core
- **引擎**: BitmaskPhysic (像素 mask 采样)
- **触发**: 鼠标光标始终存在
- **停止**: 鼠标离开视窗
- **视觉**: 鼠标周围 ~85px 区域完全镂空（字符不渲染），~90px 处高斯光晕峰值
- **文件**: `src/components/text-physics/BitmaskPhysic.tsx` (`getOcclusionAlpha`, `sampleMask`)
- **适用文本块**: 无需标记，全局生效

### 1.5 波场偏移 (Wave Shift)

- **别名**: 正弦波排版
- **引擎**: LabyrinthPhysic
- **触发**: 始终运行（基于时间正弦函数）
- **停止**: 无
- **视觉**: 每行文字按 `sin(currentY * 0.05 + time * 0.002) * 40` 偏移 startX
- **振幅**: 40
- **文件**: `src/components/text-physics/LabyrinthPhysic.tsx`
- **适用文本块**: 无需标记，v2 背景文字流全局生效

---

## 2. Logo 效果

### 2.1 虎鲸喷泉 (Orca Spray)

- **别名**: 吐水、spray
- **触发**: 鼠标 hover 进入 `data-prompt-card` 元素（PromptCard 组件）
- **持续**: 鼠标停留在 PromptCard 上期间持续喷水
- **停止**: 鼠标离开 PromptCard ~200ms 后停止
- **视觉**: 虎鲸 Logo 前方喷射粒子团，颜色按 variant 自适应（v3: cyan / v2: manuscript red），带 glow boxShadow
- **检测方式**: 帧驱动 `elementsFromPoint` + `hasAttribute('data-prompt-card')`
- **文件**: `src/components/OrcaLogo.tsx`
- **适用文本块**: **仅** `data-prompt-card` 元素（PromptCard 组件）

### 2.2 虎鲸随动 (Orca Follow)

- **别名**: 视线跟随、mouse pull
- **触发**: 鼠标移动
- **停止**: 鼠标静止
- **视觉**: 虎鲸 Logo 朝鼠标方向微微倾斜/位移
- **文件**: `src/components/OrcaLogo.tsx` (第一个 useEffect)

---

## 3. 文本块交互效果

### 3.1 磁吸 (Magnetic Pull)

- **别名**: 磁力吸、magnetic surface
- **触发**: 鼠标 hover 进入包裹在 `<MagneticSurface>` 内的元素
- **停止**: 鼠标离开
- **视觉**: 元素朝鼠标方向微微移动并放大，使用 framer-motion spring 物理
- **参数**: pull (0.1-0.4), scale (1.05), spring (damping:15, stiffness:200)
- **文件**: `src/components/MagneticSurface.tsx`
- **适用文本块**: Navigation、PretextButton、PromptCard 等被 MagneticSurface 包裹的组件

### 3.2 文本块推挤 (Text Push)

- **别名**: DOM 字符避开鼠标、mousePush
- **触发**: 鼠标靠近 `data-functional-text="true"` 元素 → `useMousePush`
- **停止**: 鼠标远离
- **视觉**: 功能文本元素朝远离鼠标方向微移（CSS transform + RAF lerp 0.2）
- **文件**: `src/hooks/useMousePush.ts`
- **适用文本块**: 所有 `data-functional-text="true"` 元素（PretextButton、PromptCard、PretextEditorial、Navigation）

---

## 4. 视图模式

### 4.1 禅模式 (Zen Mode)

- **别名**: 专注模式
- **激活**: 按 `Z` 键
- **退出**: 再按 `Z` 键
- **视觉**: 所有 UI 元素 opacity → 0.05，`pointerEvents: none`；waveAmplitude → 90
- **文件**: `src/layouts/MainLayout.tsx`

### 4.2 蓝图模式 (Blueprint Mode)

- **别名**: 线框模式
- **激活**: 按 `D` 键
- **退出**: 再按 `D` 键
- **视觉**: `.blueprint-mode` CSS 类启用，元素以线框方式审视

### 4.3 对齐调试 (Alignment Debug)

- **别名**: 辅助线
- **激活**: 按 `L` 键
- **退出**: 再按 `L` 键
- **视觉**: AABB（青）和 charRect（洋红）辅助线叠加显示

---

## 5. 功能文本分类

### 5.1 定义

**功能文本 (Functional Text)** = 所有非背景的 DOM 文字元素。标记为 `data-functional-text="true"`。

### 5.2 触发效果对照表

| 文本块 | 涟漪 | 推挤 | 磁吸 | 喷泉 | 字符挤压 | 字符绕排 |
|--------|------|------|------|------|---------|---------|
| PromptCard (agent briefing) | ✅ | ✅ | ✅ | ✅ | N/A (光标触发) | N/A (光标触发) |
| PretextButton | ✅ | ✅ | ✅ | ❌ | N/A | N/A |
| Navigation | ✅ | ✅ | ✅ | ❌ | N/A | N/A |
| PretextEditorial | ✅ | ✅ | ❌ | ❌ | N/A | N/A |
| 静态文本 (marginalia, hero, 描述) | ❌ | ❌ | ❌ | ❌ | N/A | N/A |

---

## 6. 实现契约

### 6.1 文件映射

| 文件 | 负责特效 |
|------|---------|
| `src/components/text-physics/BitmaskPhysic.tsx` | 1.1 字符挤压, 1.4 光标空洞 |
| `src/components/text-physics/LabyrinthPhysic.tsx` | 1.2 字符绕排, 1.5 波场偏移 |
| `src/hooks/useWaveRipple.ts` | 1.3 波场涟漪 |
| `src/components/OrcaLogo.tsx` | 2.1 虎鲸喷泉, 2.2 虎鲸随动 |
| `src/components/MagneticSurface.tsx` | 3.1 磁吸 |
| `src/hooks/useMousePush.ts` | 3.2 文本块推挤 |
| `src/layouts/MainLayout.tsx` | 4.1 禅模式, 4.2 蓝图模式, 4.3 对齐调试 |

### 6.2 禁止事项

- MagneticSurface **禁止** 调用 `setEnvironment`（会触发全局物理引擎重算）
- 新效果 **禁止** 使用 `setInterval`/`setTimeout` 定时器驱动（用 RAF 帧驱动）
- 效果触发标记统一使用 `data-functional-text` 或专用属性如 `data-prompt-card`
