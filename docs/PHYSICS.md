# Arena 物理引擎

> 本文档讲 arena 文字物理系统的工作原理——为什么 hover 一个文字会让背景波场避让、
> 为什么字母 `o` 的孔洞会真的透明、为什么滚动时字符栅格不会撕裂。
> 配合 [ARCHITECTURE.md](./ARCHITECTURE.md) 一起读。

## 核心理念

> **文字本身就是物理参与者，不是装饰。**

每个 DOM 文字元素被注册成 `RectObstacle`——拥有 bbox、可选 `charRects`（字符级 sub-rect）。
全局物理引擎（`BitmaskPhysic` / `LabyrinthPhysic` / `ChorusPhysic`† / `ManuscriptPhysic`）
从中央追踪器读取这些 obstacle，实时让背景文字 / 字符 / 波场避让。

> † `ChorusPhysic` 当前为 **planned**，未在任何 view / layout 挂载——`grep ChorusPhysic src/` 仅命中导出文件本身。详见下方章节。

结果：**整页文字像漂浮在不断重组的力场中**——hover 触发涟漪，输入扰动振幅，新事件激起波澜，
滚动 1.5 帧预测对齐。

---

## PhysicsContext —— 中央追踪器

`src/context/PhysicsContext.tsx` 是整个物理系统的中枢。

### Obstacle 追踪

每个 UI 文字元素通过 `useObstacle()` hook（`src/hooks/useObstacle.ts`）注册：

```tsx
const ref = useObstacle();   // 或 useObstacleDetached for memo'd components
return <span ref={ref}>ARENA_PRETEXT</span>;
```

注册流程：

1. `trackObstacle(id, element)` → 加入 `trackedRef` Map
2. `IntersectionObserver` 跟踪可见性（`rootMargin: '50px'` lazy-init）
3. 单 RAF loop 每帧扫所有 tracked 元素：
   - `getBoundingClientRect()` 拿 bbox
   - `getCharRects()` 字符级分解（Range API / canvas measureText fallback）
   - 与上一帧对比 `CHANGE_THRESHOLD = 1` px
4. 变化超阈值 → `pushSnapshot(next)` debounce `SNAPSHOT_DEBOUNCE_MS = 50` ms 推 React state
5. 同时把 obstacles 实时渲染到 offscreen `maskRef.canvas` 当像素 mask（白底字形）

### CharRect 字符级分解

`getCharRects(id, el, bbox)` 把一段文字拆成字符 sub-rect：

- **Strategy 1 — Range API**：`range.getBoundingClientRect()` 准确处理 multi-line / wrapping / mixed content
- **Strategy 2 — Canvas measureText fallback**：单行准确

每个 charRect 缓存（key: `id + text + font`），重渲染零开销。

**为什么需要字符级**：BitmaskPhysic 的像素 mask 采样要精确到字形孔洞——
字母 `o` / `d` / `e` 的 counter 必须透明，让背景字符栅格"穿过"字形内部。
（ARENA-140 暴露这个问题，V6 解决：从 bounding box → 像素 mask 缓冲区）

### Pixel Mask Buffer

`maskRef.canvas` 是 offscreen `<canvas>`（`willReadFrequently: true`）：

1. 每帧 `renderMask()` 把所有 obstacle 渲染成白底字形
2. BitmaskPhysic 的 `sampleMask(maskData, x, y)` 读 alpha 通道：
   - `> 0.5` → 完全切除（occlusion = 0，cell 跳过）
   - `> 0.01` → 边缘渐变（`occlusion = 1 - alpha`）
   - `< 0.01` → 完整渲染（`occlusion = 1`）

### Viewport + 滚动预测

`viewportRef.current = { width, height, scrollX, scrollY, dpr, scrollVelX, scrollVelY }`

每帧更新 `scrollVelX/Y = sx - prevSx`（px / 帧）。
BitmaskPhysic 采样 mask 时用 `1.5 * scrollVelY` 提前对齐——
抵消 Chrome 渲染管线的 1-2 帧延迟（ARENA-169 演进的结果，[BitmaskPhysic.tsx:222-223,313-314](../src/components/text-physics/BitmaskPhysic.tsx) 硬编码 `1.5×` 速度外推）。

**滚动同步**：

- `addEventListener('scroll', { passive: false })` 同步更新 `scrollX/Y`
- `forceAllMeasure = scrollVel > 0.01` ——滚动时绕过 IO，强制测量所有 tracked
- 修复 ARENA-178：长距离滚动 60 帧掩码黑屏

### Soloist 系统

Soloist 是 PhysicsContext 维护的另一个 Map：

```ts
interface Soloist {
  id: string;
  text: string;
  lineIndex: number;  // 强制行号
  color?: string;
  opacity?: number;
}
```

注册：`registerSoloist({ id, text, lineIndex, color })`
注销：`unregisterSoloist(id)`

**用途**：让重要文本（用户输入、feed event、标题）在 ChorusPhysic / LabyrinthPhysic 的背景文字流中
以**重号字体**介入——背景文字让位（isolation factor 0.05），soloist 用更大字号在 mapped line 渲染。

**典型用例**：

- `WatchViewV3` 把每条 feed event 注册成 soloist：
  `{ id: 'watch-event-${i}', text: 'PLAYER :: EVENT :: REF_target', lineIndex: 12 + i*4 }`
- `ChallengeDetailV3` 把用户 textarea 内容注册成 soloist：
  `{ id: 'challenge-user-input', text: answer, lineIndex: 11, color: cyan }`

### Environment 设置

```ts
interface EnvironmentSettings {
  ambientColor?: string;
  waveAmplitude?: number;       // default: 60
  waveFrequency?: number;       // default: 0.03
  opacity?: number;             // default: 0.15
  debugAlignment?: boolean;     // L 键
}
```

`setEnvironment({ waveAmplitude: 90 })` 触发**所有**物理引擎的振幅扰动，
通过 `mergeEnvironment` 保留其它字段。

**典型扰动**：

- 鼠标 hover UI 元素（`useWaveRipple`）：60 → 120，600ms 衰减
- ChallengeDetailV3 textarea 输入：60 → 90，500ms 衰减
- WatchViewV3 新 feed event：60 → 100 → 60，800ms 脉冲

---

## 4 个物理引擎

### 1. BitmaskPhysic（v3 默认背景）

`src/components/text-physics/BitmaskPhysic.tsx`

字符栅格背景：用 HEX / SYNAPTIC / DATA 三组字符在网格上渲染流动数据风暴。

#### 字符集

```ts
HEX = '0123456789ABCDEF';
SYNAPTIC = ['∞', 'Σ', 'Δ', 'Ω', 'λ', 'π', 'μ', '∂', '∇', '≡', '⊕', '⊗'];
DATA = ['0', '1', ':', '.', '·', '∘'];
```

字符选择由 `flowAngle = (flowA + 2) * 3 + flowB` 伪哈希决定，
每帧偏移 → 字符随时间漂移。

#### LOD（详细等级）

`getCellSize()` 按 viewport 宽度 + DPR 选格子大小：

| 条件 | cell w × h |
|------|-----------|
| `vw > 2500` 或 `dpr > 2`（4K） | 24 × 32 |
| `dpr > 1`（Retina） | 14 × 19 |
| 普通 | 10 × 14 |

目的：4K 屏幕保持总 cell 数 < 6000，4K 60FPS 闭环（ARENA-210）。

#### Sine LUT

预计算 4096 size sin 表，`fsin(x)` 比 `Math.sin` 快 5×——消除每 cell `sin` 调用开销。

#### 鼠标 Repulsion + Ring Glow + Void Core

```
mouseFactor = max(0, 1 - dist / 300)

if mouseFactor > 0.85: cell skip                // 核心 void
if mouseFactor > 0.75: smoothstep fade          // 边缘

ringDist = mouseFactor - 0.7
ringGlow = exp(-ringDist² × 40) × mouseFactor   // 高斯光晕峰值 ~90px
```

效果：鼠标周围 ~85px 完全镂空，~90px 是发光环（高斯峰值），300px 外恢复正常。
（V13 演进 ARENA-217 / ARENA-220 / ARENA-221 / ARENA-224 / ARENA-227）

#### Flow Field

```
flowA = fsin(col*0.12 + row*0.08 + phase) + fsin(row*0.15 - col*0.05 + phase*1.4)
flowB = fsin(col*0.07 - row*0.11 + phase*0.7) + fsin((col+row)*0.06 + phase*1.1)

density = max(0, flowStrength - repulsion)
```

两条交叉流场叠加，鼠标排斥让数据流"远离"光标——形成视觉上数据被吸引绕开的效果。

#### Pixel Mask 占用

```
if maskSample > 0.5:    occlusion = 0           // 完整字形 → 完全透明
elif maskSample > 0.01: occlusion = 1 - maskSample
else:                   occlusion = 1
```

字符栅格在文字 obstacle 区域**完全消失**，包括字母 `o` 的孔洞会再次出现字符
——形成"字符栅格穿过字形内部"的奇幻效果。

#### 颜色

HSL 神经渐变：

```
hue = 200 + fsin(flowA * 0.5 + t*0.2) * 60 + hueDistort * fsin(t*2 + col*0.1)
sat = 60 + mouseFactor * 20
lightness = 50 + depthFade * 20 + mouseFactor * 15 + surgeNorm * 10
```

200 起步（cyan）+ ±60 抖动（青—紫渐变），靠近鼠标更亮、更饱和。

---

### 2. LabyrinthPhysic（v2 主背景）

`src/components/text-physics/LabyrinthPhysic.tsx`

把 `manifesto` + `chorus` 文字重复 10 次拼成迷宫背景，UI obstacle 让文字流绕开。

#### Multi-span 避让

`computeFreeSpans(y, lineHeight, width, obstacles)`：

1. 找所有与该行 y 重叠的 obstacle，每个 obstacle 拆成 charRects 进一步精确（字符级 padding 15px）
2. 排序 + merge 重叠区间
3. 取反得到 free spans
4. 过滤 `< MIN_SPAN_WIDTH = 20` 的太窄 span

#### 迷宫 Inset

每行根据 `pathSeed = sin(y * 0.01) * 100`：

- `pathSeed > 88`：左 inset 60px
- `pathSeed < -88`：右 inset 60px

效果：文字流主线弯曲穿行——形成迷宫感。
（ARENA-205 V11 生成式演化迷宫拓扑）

#### Variant 风格

| | v2 手稿 | v3 合唱 |
|---|---|---|
| 字体 | `400 8px 'Noto Serif SC'` 或 `400 9px 'Playfair Display'` | 父配置传入（默认 Satoshi） |
| 颜色 | `rgba(40, 30, 20, alpha)` | HSL 270° + hueShift |
| 波动 | 静态 | `sin(y*0.05 + t*0.002) * (20 + waveAmp * mouseFactor)` |

#### Soloist 渲染

每行渲染时记录 `lineMap.set(lineIdx, { text, x })`。最后 pass：

```ts
soloists.forEach(soloist => {
  const lineData = lineMap.get(soloist.lineIndex);
  if (lineData) {
    ctx.font = `900 ${variant === 'v2' ? '32px' : '48px'} ${variant === 'v2' ? 'serif' : 'sans-serif'}`;
    ctx.fillText(soloist.text, lineData.x, soloist.lineIndex * lineHeight - 10);
  }
});
```

Soloist 用 32px / 48px 重号在 mapped line 上覆盖渲染——成为整页"独奏者"。

---

### 3. ChorusPhysic（合唱波场 + Soloist 介入）— planned，未挂载

`src/components/text-physics/ChorusPhysic.tsx`

> ⚠️ **当前未在任何 view / layout 中挂载**——`MainLayout.tsx:99-109` 在 v3 走 `BitmaskPhysic`、v2 走 `LabyrinthPhysic`。`grep ChorusPhysic src/` 仅命中导出文件本身。下文为引擎 API 设计文档，**挂载点尚待补全**。

行级波形排版：每行文字按正弦波偏移 startX + 收窄 availableWidth。

#### Wave 公式

```ts
primaryWave = sin(y * frequency + phase)
interferenceWave = cos(y * frequency * 1.5 - phase * 0.5)
waveShift = primaryWave * amp + interferenceWave * amp * 0.3
startX = w * 0.1 + waveShift
```

主波 + 干涉波叠加 → 整页文字像被声波震动。

#### Mouse Settling（焦点凝静）

```ts
distToMouseY = abs(y + lineHeight/2 - mouse.y)
mouseFactor = max(0, 1 - distToMouseY / 300)
focalSettling = 1 - mouseFactor * 0.9    // 鼠标 0px 时 amp × 0.1
```

鼠标靠近时波场振幅近乎归零——形成 **calm void**，让文字"安静下来"。
（zh-CN 文案中"凝静"与此对应）

#### Soloist Isolation

```ts
isSoloistZone = soloists.some(s => abs(s.lineIndex - lineIdx) <= 1)

isolationFactor = isSoloistZone ? 0.05 : 1.0
backgroundAlpha = 0.3 * (1 - mouseFactor*0.5) * isolationFactor
```

Soloist 上下 ±1 行的背景文字 alpha 降到 5%——让 soloist "独占舞台"。

---

### 4. ManuscriptPhysic（v2 手稿绕排）

`src/components/text-physics/ManuscriptPhysic.tsx`

文字流绕开矩形 obstacle 排版（Marginalia Rail）。**静态**（`isAnimated: false`）。

#### Rail 算法

```ts
for (const rect of obstacles) {
  if (currentY + lineHeight > rect.y && currentY < rect.y + rect.h) {
    if (rect.x < w / 2) {
      startX = max(startX, rect.x + rect.w + padding);            // 左半 → 推 startX
    } else {
      availableWidth = min(availableWidth, rect.x - padding - startX);   // 右半 → 收宽
    }
  }
}
```

**用例**：

- `WatchViewV2` 让 feed event 卡片当 obstacle，背景 manuscript 文字绕开
- `ChallengeDetailV2` 让 FOLIO_DATA + TRANSCRIPTION_AREA 当 obstacle；用户的
  `[ SIGNATURE_ECHO: ${answer} ] ` × 3 嵌入背景文字流——**用户输入实时成为手稿的一部分**

---

## Hooks 速查

| Hook | 作用 | 文件 |
|------|------|------|
| `useObstacle()` | 自动注册 / 注销 obstacle，跟随 isZenMode 自动 unregister | `hooks/useObstacle.ts` |
| `useObstacleDetached(active, isZenMode)` | 同上但跳过 useArena context（perf-critical memo'd） | 同 |
| `useWaveRipple()` | 鼠标 hover 触发 `waveAmplitude: 60→120`，600ms 衰减；全局 `activeRippleCount` 防干扰 | `hooks/useWaveRipple.ts` |
| `usePretextCanvas({ onRender, isAnimated })` | 共享 canvas RAF 循环 hook | `hooks/usePretextCanvas.ts` |
| `usePhysicsRegistry()` | 拿 PhysicsContext 全部接口 | `context/PhysicsContext.tsx` |

---

## 演进历史（参考 .tasks/TASKS.md）

物理系统经过 14 次大版本迭代：

| 版本 | 关键变化 | Tasks |
|------|---------|-------|
| V4 | safeStr 普适化 + 内存安全 | ARENA-124 / 127 / 128 |
| V6 | **像素级遮罩缓冲区**，字形孔洞穿透（解决 V5 bounding box 无法穿透 `o` 中心问题） | ARENA-144 / 145 / 153 / 156 |
| V7 | 滚动同步 + 1.5 帧预测 + 同步可见性 | ARENA-163 / 166 / 169 / 172 / 178 |
| V8 | 顶层物理掩码 + Vivid Separation（混合模式 + 动画生动化） | ARENA-188 / 192 / 193 |
| V9 | 三级掩码算法 + 湍流流体模拟 | ARENA-196 / 197 / 198 |
| V11 | 生成式演化迷宫点阵场（结构化、不断重构） | ARENA-205 |
| V12 | LOD + Sine LUT 性能极限优化（4K 60FPS） | ARENA-208 / 209 / 210 |
| V13 | 神经元数据风暴重塑（HEX 流 + 二次鼠标排斥 + 3D 深度梯度 + 高斯光晕收紧 + 排斥真空硬阻断） | ARENA-214 → ARENA-227 |
| V14 | 大厅诗意拓扑重制（衬线体 + 分散布局）+ 力场张力 + Playfair 字体 | ARENA-223 → ARENA-230 |

---

## Debug 工具

按 `L` 切换 alignment 辅助线：

- **AABB（青）**：每个 obstacle 的 bounding box
- **charRect（洋红）**：字符级 sub-rect

应用预测偏移（`scrollVelX/Y * 1.5`），让你看到物理采样位置和 DOM 实际位置的差异。

按 `D` 切 Blueprint 模式（线框审视）。
按 `Z` 进 Zen mode（隐藏 UI 只剩物理）。

---

## 相关文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) — 5 层平面、Provider、Router、State flow
- [.tasks/TASKS.md](../.tasks/TASKS.md) — 完整 ARENA-### 任务历史
- [.tasks/ROADMAP.md](../.tasks/ROADMAP.md) — V15 后续路线图（包括 D2/D3/D4 视觉收尾）
