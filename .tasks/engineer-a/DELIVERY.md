task_id: ARENA-230
owner: engineer-a
target: engineer-b
status: done
date: 2026-04-14

# Delivery: ARENA-230 — Playfair Display + IBM Plex Mono font loading

## Summary

Added Google Fonts imports for Playfair Display (regular, bold, italic, bold-italic) and IBM Plex Mono (400, 500, 700) to ensure the V14 manuscript typography renders in production.

## Changes

### `src/index.css`

Merged new fonts into the existing Google Fonts import:
```css
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Playfair+Display:ital,wght@0,400;0,700;1,400;1,700&family=IBM+Plex+Mono:wght@400;500;700&display=swap');
```

**Playfair Display** variants loaded:
- `400` — regular (body text, descriptions)
- `700` — bold (emphasis)
- `400 italic` — primary title weight in ChallengeCard/ChallengeGrid
- `700 italic` — bold emphasis

**IBM Plex Mono** variants loaded:
- `400` — meta labels, reward text
- `500` — medium weight
- `700` — bold mono accents

Both fonts use `display=swap` — text renders immediately with fallback fonts, swaps to web fonts when loaded. No FOIT (flash of invisible text).

**Consumers:** ChallengeCard (`serifTitleStyle`, `monoMetaStyle`, `descStyle`, `rewardStyle`), ChallengeGrid (`headerTitleStyle`, `headerLabelStyle`, `footerStyle`).

## Verification

- `npm run build` passes (tsc + vite, 2168 modules, 0 errors).
- Bundle: 447.98 KB. CSS: 4.71 KB (+0.1 KB for import URL).
