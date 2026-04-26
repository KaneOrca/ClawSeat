task_id: ARENA-191
project: arena-pretext-ui
owner: engineer-b
status: pending
title: 紧急修复：文本与点阵视觉分离 + 点阵生动动画

# Objective

发现文本和背景点阵依然混合在一起（充贴），点阵动画不够生动。问题根因：1) 物理层 zIndex 5 在 content zIndex 2 之上，当前 mask 方案是"点阵叠加在文本上+透明"，不是真正的视觉分离；2) 没有使用 mix-blend-mode；3) drift 动画幅度太小（0.15）几乎无感。请诊断并给出修复方案，需要实现真正的文本/点阵视觉分离（推荐方案：物理层移回 content 下方 + mix-blend-mode: multiply/multiply 让文本区域透明露出 Aurora 背景，或其他能达到分离效果的方案），以及提升点阵动画的生动感（amplitude/wave 参数调优）。

# Dispatch

source: koder
reply_to: koder
dispatched_at: 2026-04-14T05:19:49+00:00

Consumed: ARENA-191 from koder at 2026-04-14T05:21:40Z
Objective: Fix visual separation (text/bitmask mix) and improve animation liveliness.

Consumed: ARENA-192+193 from engineer-a at 2026-04-14T05:24:47Z
Verdict: GO (advancing to Review/QA)
- Physics layer reverted to background (plane 1) verified.
- mix-blend-mode: 'difference' implemented on V3 content verified.
- Triple-sine ambient drift (0.45 peak) verified.
- Build verified.

Consumed: ARENA-194 from engineer-c at 2026-04-14T05:27:23Z
Verdict: APPROVED ✓
- Blend mode architecture (difference on plane-content) verified.
- Triple-sine ambient drift algorithm verified.
- Visual separation logic is now CLOSED.

Consumed: ARENA-195 from engineer-d at 2026-04-14T05:47:17Z
Verdict: PASS ✓
- Final visual evolution sign-off received.
- Visual separation (difference blending) verified as readable and distinct.
- Triple-sine ambient drift verified as rich and non-linear.
- Interaction safety confirmed (no z-index/pointer-events blockers).
- [PROJECT_CLOSED] Arena V8 "Vivid Separation" architecture is now fully delivered and accepted.

Consumed: ARENA-191 from koder at 2026-04-14T07:44:49Z
Objective: Solve visual blending (text covered) and stagnant idle animation.
Strategy: Revert to sub-content physics with 100% mask cutout and implement turbulence-based drift.

Consumed: ARENA-196+197 from engineer-a at 2026-04-14T08:08:38Z
Verdict: GO (advancing to Review/QA)
- 100% text cutout logic (3-tier mask occlusion) verified.
- mix-blend-mode removal confirmed (readability restored).
- 4-way turbulence drift (0.6 peak) + phase jitter verified.
- Build verified.

Consumed: ARENA-198 from engineer-c at 2026-04-14T08:28:22Z
Verdict: CHANGES_REQUESTED
- Finding: Negative modulo issue in BitmaskPhysic. Turbulence can push field into negative range, causing CHARS[charIdx] to be undefined.
- Action: Dispatching ARENA-200 for stable character indexing.

Consumed: ARENA-199 from engineer-d at 2026-04-14T08:38:21Z
Verdict: PASS ✓
- Visual cutout purity verified (median alpha = 0).
- 4-way turbulence drift verified (non-linear patterns confirmed).
- Inertial scroll alignment verified (contaminatedFramesAfter100px = 0).

Consumed: ARENA-200 from engineer-a at 2026-04-14T08:38:21Z
Verdict: GO (advancing to Review/QA)
- Negative modulo bug fixed (wrap pattern implemented).
- Character indexing stability verified.
- Build verified.

Consumed: ARENA-201 from engineer-c at 2026-04-14T08:43:25Z
Verdict: APPROVED ✓
- Positive character indexing (wrap pattern) verified.
- Negative modulo bug officially resolved.

Consumed: ARENA-202 from engineer-d at 2026-04-14T08:49:23Z
Verdict: PASS ✓
- Final stabilization sign-off received.
- Character indexing robustness verified (0 undefined calls in 5M+ samples).
- Turbulence animation stability and non-linearity confirmed.
- [PROJECT_CLOSED] Arena V9 "Vivid Separation" is now fully delivered and accepted.

Consumed: [user] Report on covering text and static animation at 2026-04-14T09:07:21Z
Finding: engineer-a failed to actually move z-index in MainLayout; opacity 0.06 is too faint to see animation.

Consumed: [user] Request bitmask background to look like a "constantly changing maze" at 2026-04-14T09:10:28Z
Objective: Pivot from fluid turbulence to structured maze topology.

Consumed: ARENA-205 from engineer-a at 2026-04-14T09:18:07Z
Verdict: GO (advancing to Review/QA)
- Generative maze topology (multi-sine thresholding) verified.
- New maze character set and connection logic verified.
- Dynamic evolution (phase, mouse proximity, surge) verified.
- Build verified.

Consumed: ARENA-206 from engineer-c at 2026-04-14T09:23:15Z
Verdict: APPROVED ✓
- Generative maze topology algorithm verified.
- Character selection logic confirmed robust (no undefined risk).
- Maze signals (H/V/Diag) confirmed mathematically sound.

Consumed: ARENA-207 from engineer-d at 2026-04-14T09:28:17Z
Verdict: FAIL ✗
- Finding: V11 Maze performance fails on 4K (11.7 FPS). 140k+ Math.sin calls per frame.
- Strategy: Implement V12 optimizations (LOD Sizing, Sine LUT, Signal Gating).

Consumed: ARENA-208 from engineer-a at 2026-04-14T09:35:27Z
Verdict: GO (advancing to Review/QA)
- 10x performance speedup in maze hot-path verified.
- Sine LUT (Float32Array) and LOD (24x32 cells) verified.
- Far-field gating (500px radius) confirmed.
- Build verified.

Consumed: ARENA-209 from engineer-c at 2026-04-14T09:43:49Z
Verdict: CHANGES_REQUESTED
- Finding: Hard threshold (500px) for diagonal gating causes visible snap in maze topology.
- Action: Dispatching ARENA-211 for smooth transition (feathering) of far-field gating.

Consumed: ARENA-210 from engineer-d at 2026-04-14T09:46:34Z
Verdict: PASS ✓
- 4K Performance verified: ~68 FPS on 3840x2160.
- Long tasks reduced to 0.
- Topology consistency (pathFraction) confirmed across viewports.

Consumed: ARENA-211 from engineer-a at 2026-04-14T09:46:34Z
Verdict: GO (advancing to Review/QA)
- Far-field gating transition (400-600px feather zone) verified.
- Hard snapping issue resolved.
- Build verified.

Consumed: ARENA-212 from engineer-c at 2026-04-14T09:58:58Z
Verdict: APPROVED ✓
- Far-field transition logic (400-600px feather zone) verified.
- Numerical safety and performance impact of smooth gating confirmed.
- Visual consistency track is now CLOSED.

Consumed: ARENA-213 from engineer-d at 2026-04-14T09:59:54Z
Verdict: PASS ✓
- Absolute Final Sign-off received for V12 Performance & Visual Consistency.
- 4K Performance: ~76 FPS on 3840x2160 confirmed.
- Smooth Transition: 400-600px diagonal gating verified as seamless.
- [PROJECT_CLOSED] Performance evolution and generative maze topology is now fully delivered and accepted.

Consumed: [user] Request complete background redesign (Super Cool direction). Discard Maze.
Objective: Implement V13 "Neural Data Swarm" with Perlin Flow and HEX streams.

Consumed: ARENA-214 from engineer-a at 2026-04-14T11:24:37Z
Verdict: GO (advancing to Review/QA)
- Neural Data Swarm background (HEX + Math symbols) verified.
- Flow field dynamics and quadratic mouse repulsion verified.
- 3D depth fade and trail glow implemented.
- Performance infra (LUT, LOD) preserved.
- Build verified.

Consumed: ARENA-215 from engineer-c at 2026-04-14T11:43:49Z
Verdict: APPROVED ✓
- Neural Data Swarm algorithms (flow field, repulsion, depth fade) verified as safe and efficient.
- V13 core architecture is now CLOSED.

Consumed: ARENA-216 from engineer-d at 2026-04-14T12:15:45Z
Verdict: FAIL ✗
- Finding: Mouse repulsion void is not working; cursor center is bright instead of empty.
- Root Cause: trailGlow is added to alpha at the cursor center (mouseFactor=1), overriding the repulsion density reduction.
- Action: Dispatching ARENA-217 to fix the void math.

Consumed: ARENA-217 from engineer-a at 2026-04-14T12:36:12Z
Verdict: GO (advancing to Review/QA)
- Mouse repulsion void fix verified (ring glow function).
- Void masking (center truly empty) verified.
- Visual effect (dark center, bright edge) confirmed by implementation logic.
- Build verified.

Consumed: ARENA-218 from engineer-c at 2026-04-14T12:39:24Z
Verdict: CHANGES_REQUESTED
- Finding: voidMask is too narrow; normal field still leaks into the void center because repulsion only exceeds flowStrength at the mathematical center.
- Action: Dispatching ARENA-220 for a robust 'Void Core' implementation.

Consumed: ARENA-220 from engineer-a at 2026-04-14T12:42:41Z
Verdict: GO (advancing to Review/QA)
- Void core (mouseFactor > 0.8) hard skip verified.
- Absolute occlusion inside 60px radius confirmed.
- Build verified.

Consumed: [user] Request Hall redesign based on V2 Home (Advanced, Poetic, Artistic).
Objective: Implement Poetic Topology with Playfair Display and staggered layout.

Consumed: ARENA-221 from engineer-c at 2026-04-14T12:53:53Z
Verdict: CHANGES_REQUESTED
- Finding: Hard continue at mouseFactor > 0.8 creates a visual pop at the 60px boundary. ringGlow (~0.64) jumps to 0 instantly.
- Fix: Smoothly taper the alpha near the boundary.

Consumed: ARENA-219 from engineer-d at 2026-04-14T12:53:53Z
Verdict: PASS ✓
- Void formation verified (avgLuma = 0).
- Halo/ring glow verified (outer glyph count increase).
- 4K Performance verified (~62 FPS under scroll+interaction).

Consumed: ARENA-222 from engineer-d at 2026-04-14T13:08:27Z
Verdict: FAIL ✗
- Finding: Large empty gap (60-130px) between void core and ring glow. Glow starts too late (130px+).
- Root Cause: ringGlow function (mouseFactor*(1-mouseFactor)) peaks too far (150px).

Consumed: ARENA-223 from engineer-a at 2026-04-14T13:08:27Z
Verdict: GO (advancing to Review/QA)
- Hall Redesign (Poetic Manuscript) implemented.
- Playfair Display typography and staggered layout verified.
- Bundle size reduced (icons/card-util removed).

Consumed: ARENA-224 from engineer-a at 2026-04-14T13:08:27Z
Verdict: GO (advancing to Review/QA)
- Void core edge smoothing (smoothstep 0.75-0.85) implemented.
- Hard skip logic refined.

Consumed: ARENA-227 from engineer-a at 2026-04-14T13:28:05Z
Verdict: GO (advancing to Review/QA)
- Ring glow tightened (Gaussian bump at mouseFactor 0.7) verified.
- Dark gap between void and glow eliminated.

Consumed: ARENA-225 from engineer-c at 2026-04-14T13:28:05Z
Verdict: CHANGES_REQUESTED
- Finding: Playfair Display font not imported in mainline (index.css or App.tsx).
- Action: Dispatching ARENA-230 to engineer-a for font import.
