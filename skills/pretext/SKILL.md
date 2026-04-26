# Pretext Skill Reference

`@chenglou/pretext` is the core text physics library for Arena. It provides pure-math text measurement and layout, bypassing the DOM to enable 60fps typographic interactions.

## Core Concepts

### 1. Preparation (Cold Path)
The `prepare()` or `prepareWithSegments()` functions perform one-time work: font measurement, segmentation, and rule application.
> [!CAUTION]
> **Performance Anti-pattern**: Do NOT call `prepare` inside a render loop or `requestAnimationFrame`. Always memoize or cache the prepared handle.

### 2. Layout (Hot Path)
The `layout()` or `layoutNextLine()` functions are arithmetic-only. They use cached widths from the preparation phase to compute line breaks and geometry instantly.

## API Patterns

### Text Wrapping (Obstacle Avoidance)
Used in **v2 (Manuscript)**.
1. Define rectangular/circular obstacles.
2. For each line at coordinate `y`, compute the "available intervals" (slots) by subtracting obstacle intercepts.
3. Use `layoutNextLine(prepared, cursor, slotWidth)` to fill each slot.

```ts
while (true) {
  const width = calculateAvailableWidth(y, obstacles);
  const line = layoutNextLine(prepared, cursor, width);
  if (!line) break;
  // Render line.text at (x, y)
  cursor = line.end;
  y += lineHeight;
}
```

### Resonant Fields (Chorus Wave)
Used in **v3 (Chorus)**.
1. Vary the `maxWidth` and/or `startX` of lines based on a wave function (e.g., `Math.sin(y * freq + phase)`).
2. Use `layoutNextLine` to flow text into the oscillating container.

### Gravity/Physics (Attraction)
Used in **v1 (Gravity)**.
1. Treat mouse or geometry as an "Orb".
2. Orbs create "holes" or "repulsion zones" in the text field by blocking intervals.

## Project Guidelines

- **Bilingual Support**: Always pass the correct `locale` to `setLocale()` if the language changes significantly, though `prepare` is generally robust.
- **Font Sync**: The `fontDef` string passed to Pretext MUST exactly match the CSS `font` property used for rendering to ensure pixel-perfect accuracy.
- **Canvas Rendering**: For complex physics, render to a High-DPI Canvas using `ctx.fillText(line.text, x, y)`.

## References
- [README.md](file:///Users/ywf/coding/arena-pretext-ui/skills/pretext/README.md)
- [EDITORIAL_REFERENCE.ts](file:///Users/ywf/coding/arena-pretext-ui/skills/pretext/EDITORIAL_REFERENCE.ts)
