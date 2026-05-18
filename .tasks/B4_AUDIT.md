## B4 Mobile Audit — <768px

| file:line | pattern | safe at 768px? | proposed fix |
|---|---|---|---|
| `src/layouts/MainLayout.tsx:83` | root `minHeight: '100vh'` | yes | Nothing needed; page root can span viewport height. |
| `src/layouts/MainLayout.tsx:91` | fixed background plane, `zIndex: 0` | yes | Nothing needed; `pointerEvents` are absent here but children are decorative and below content. |
| `src/layouts/MainLayout.tsx:98` | fixed physics plane, `zIndex: 1`, `pointerEvents: 'none'` | yes | Nothing needed. |
| `src/layouts/MainLayout.tsx:116` | fixed interaction plane, `zIndex: 1`, `pointerEvents: 'none'` | yes | Nothing needed. |
| `src/layouts/MainLayout.tsx:122-125` | v2 content horizontal padding `4rem` | moderate | CSS media query; reduce v2 page padding to `1rem` under 768px. |
| `src/layouts/MainLayout.tsx:151` | fixed loading chip at `bottom/right: 3rem`, `zIndex: 100` | moderate | CSS media query; move to centered bottom or clamp offsets. |
| `src/layouts/MainLayout.tsx:178` | footer `marginTop: '10rem'`, `padding: '4rem 0'` | cosmetic | CSS media query; reduce large vertical whitespace on mobile. |
| `src/layouts/MainLayout.tsx:191` | fixed overlay plane, `zIndex: 10`, `pointerEvents: 'none'` | yes | Nothing needed. |
| `src/layouts/MainLayout.tsx:204` | toast fixed bottom/center, `zIndex: 1000` | moderate | CSS media query; constrain toast width and reduce letter spacing so text does not overflow. |
| `src/views/Hall/HallView.tsx:20` | loading wrapper `height: '60vh'` | yes | Nothing needed; centered loading state. |
| `src/views/Hall/HallView.tsx:42` | `fontSize: clamp(2rem, 4vw, 3.5rem)` | yes | Nothing needed; clamp provides lower bound. |
| `src/views/Hall/HallView.tsx:79` | profile island `marginBottom: '4rem'` | cosmetic | CSS media query; reduce to `2rem` on mobile. |
| `src/views/Home/v3/HomeViewV3.tsx:63` | root `minHeight: '100vh'` | yes | Nothing needed. |
| `src/views/Home/v3/HomeViewV3.tsx:68-73` | absolute `vh/vw` hero atom positions | yes | Already handled by local `@media (max-width: 768px)` that resets positioning to static. |
| `src/views/Home/v3/HomeViewV3.tsx:87` | `fontSize: clamp(3rem, 12vw, 7rem)` | yes | Nothing needed; mobile lower bound is controlled. |
| `src/variants/v2/views/HomeView.tsx:31` | page padding `4rem` | moderate | CSS media query; reduce to `1rem` on mobile. |
| `src/variants/v2/views/HomeView.tsx:49-54` | marginalia absolute `left: 800`, width `350` | critical | CSS media query / relative positioning; stack marginalia blocks in normal flow under 768px. |
| `src/variants/v2/views/HomeView.tsx:65-70` | marginalia absolute `left: 50`, `top: 450`, width `300` | moderate | CSS media query / relative positioning; stack below hero in normal flow. |
| `src/variants/v2/views/HomeView.tsx:80-84` | hero `marginTop: 20vh`, `maxWidth: 600px`, `marginLeft: 15vw` | moderate | CSS media query; remove left offset and reduce top spacing under 768px. |
| `src/views/ChallengeDetail/v3/ChallengeDetailV3.tsx:93-95` | root `minHeight: 100vh`, `padding: '4rem 2rem'` | moderate | CSS media query; reduce padding to `2rem 1rem`. |
| `src/views/ChallengeDetail/v3/ChallengeDetailV3.tsx:120` | title `clamp(2.5rem, 5vw, 4rem)` | yes | Nothing needed. |
| `src/views/ChallengeDetail/v3/ChallengeDetailV3.tsx:130-131` | textarea `maxWidth: 800px`, `height: 25vh` | yes | Mostly safe; consider `minHeight` for very short mobile screens. |
| `src/views/ChallengeDetail/v3/ChallengeDetailV3.tsx:255` | diag atom `marginRight: '4rem'` | cosmetic | CSS media query; stack diagnostics or reduce right margin. |
| `src/views/ChallengeDetail/v2/ChallengeDetailV2.tsx:13-18` | padding `4rem`, grid `3fr 1fr`, gap `4rem`, maxWidth `900px` | critical | CSS media query; reduce padding and switch grid to one column. |
| `src/views/Watch/v3/WatchViewV3.tsx:192-194` | root `minHeight: 100vh`, `padding: '4rem 2rem'` | moderate | CSS media query; reduce padding to `2rem 1rem`. |
| `src/views/Watch/v3/WatchViewV3.tsx:243` | header `marginBottom: '3rem'` | cosmetic | CSS media query; reduce spacing on narrow screens. |
| `src/views/Watch/v2/WatchViewV2.tsx:10-12` | padding `4rem`, maxWidth `1000px`, title `3rem`, marginBottom `4rem` | moderate | CSS media query; reduce padding/title and keep max width fluid. |
| `src/views/Community/CommunityView.tsx:69` | header `marginBottom: '6rem'` | cosmetic | CSS media query; reduce vertical spacing. |
| `src/views/Community/CommunityView.tsx:75` | `fontSize: clamp(3rem, 8vw, 5rem)` | yes | Nothing needed. |
| `src/views/Community/CommunityView.tsx:98-112` | social plane margin, chat `minHeight: 60vh`, gap `3rem`, marginBottom `4rem` | moderate | CSS media query; reduce gaps and min height for small screens. |
| `src/views/Community/CommunityView.tsx:141` | message `maxWidth: 800px` | yes | Nothing needed; max width does not force overflow. |
| `src/views/Community/CommunityView.tsx:162` | input padding `1.5rem 5rem 1.5rem 0` | moderate | CSS media query; reduce right padding or reserve button with flex layout. |
| `src/views/Community/CommunityView.tsx:174` | absolute send button `right: 32px`, `top: 50%`, `zIndex: 20` | moderate | Relative/flex positioning; absolute button can overlap long input text and small tap areas. |
| `src/components/Navigation.tsx:108` | nav `zIndex: 10` | yes | Nothing needed; nav is above content and normal flow. |
| `src/components/TextVariantSwitcher.tsx:24` | fixed switcher `zIndex: 2000` | moderate | CSS media query; ensure it does not cover nav/footer tap targets on narrow screens. |
| `src/components/SettingsShell.tsx:36-51` | fixed modal overlay, maxWidth `500px`, padding `4rem`, z-index `100/101` | moderate | CSS media query; use `width: calc(100vw - 2rem)` and padding `2rem 1rem`. |
| `src/components/AuroraEngine.tsx:79-81` | decorative canvas `100vw/100vh`, `zIndex: -2` | yes | Nothing needed; background only. |
| `src/components/text-physics/BitmaskPhysic.tsx:341` | full-bleed absolute canvas | yes | Nothing needed; pointer-events none and fills parent. |
| `src/components/text-physics/LabyrinthPhysic.tsx:276` | full-bleed absolute canvas | yes | Nothing needed; pointer-events none and fills parent. |
| `src/components/text-physics/ManuscriptPhysic.tsx:69` | canvas `height: 100vh` | yes | Nothing needed; physics background. |
| `src/components/text-physics/ChorusPhysic.tsx:135` | canvas `height: 100vh` | yes | Nothing needed; dead/no consumer per B2 notes, but safe as background. |
| `src/components/ChallengeGrid.tsx:18` | section `padding: '6rem 0'` | cosmetic | CSS media query; reduce vertical padding. |
| `src/components/ChallengeGrid.tsx:32` | heading `clamp(2.5rem, 5vw, 4rem)` | yes | Nothing needed. |
| `src/components/ChallengeGrid.tsx:46-50` | scatter/footer margins `4rem/8rem` | cosmetic | CSS media query; reduce vertical rhythm on mobile. |
| `src/components/ChallengeGrid.tsx:56` | footer `maxWidth: 500px` | yes | Nothing needed. |
| `src/components/ChallengeCard.tsx:25` | card `maxWidth: 380px` | yes | Nothing needed; max width only. |
| `src/components/ChallengeCard.tsx:53` | description `maxWidth: 320px` | yes | Nothing needed; max width only. |
| `src/components/PretextLeaderboard.tsx:48` | `minHeight: 400px` | moderate | CSS media query; lower min-height or use `min(400px, 60vh)`. |
| `src/components/PretextLeaderboard.tsx:64` | loading `height: 300px` | cosmetic | CSS media query; reduce on mobile. |
| `src/components/PretextLeaderboard.tsx:88` | absolute progress/fill element | yes | Nothing needed; contained decorative element. |
| `src/components/PretextEditorial.tsx:94` | absolute editorial overlay element | moderate | CSS media query; verify it does not overlap long text, switch to relative if visible on mobile. |
| `src/components/HeroSection.tsx:23-25` | `minHeight: 100vh`, large padding `10rem 0`, zIndex `10` | moderate | CSS media query; reduce hero padding. |
| `src/components/HeroSection.tsx:38` | hero `clamp(5rem, 12vw, 10rem)` | moderate | Clamp lower bound is too large for 320px widths; reduce lower bound. |
| `src/components/HeroSection.tsx:42-63` | margins `5rem/6rem`, CTA padding `1.75rem 5rem` | moderate | CSS media query; reduce spacing and horizontal CTA padding. |
| `src/components/HeroSection.tsx:94-95` | card padding `4rem`, marginBottom `3rem` | moderate | CSS media query; reduce card padding. |
| `src/components/HeroSection.tsx:132` | decorative absolute blob-ish element, width `300px`, offscreen offsets | moderate | Remove or hide on mobile; avoid offscreen overflow/decorative overlap. |
| `src/components/HeroSection.tsx:163` | absolute decorative element | moderate | Hide or constrain on mobile. |
| `src/components/ChallengeDetailShell.tsx:51-56` | detail shell `minHeight: 100vh`, padding `4rem 0`, marginBottom `4rem` | cosmetic | CSS media query; reduce spacing. |
| `src/components/ChallengeDetailShell.tsx:97` | title `clamp(4rem, 8vw, 6rem)` | moderate | Lower clamp minimum for narrow screens. |
| `src/components/ChallengeDetailShell.tsx:101-169` | repeated margins `4rem-6rem` | cosmetic | CSS media query; reduce vertical rhythm. |
| `src/components/ChallengeDetailShell.tsx:192-198` | locked-state padding `4rem 0`, zIndex `2` | cosmetic | CSS media query; reduce padding. |
| `src/components/ChallengeDetailShell.tsx:253` | absolute decorative radial layer | yes | Nothing needed if pointer-events none/behind content; verify if enabled. |
| `src/components/CommunityShell.tsx:32` | marginBottom `4rem` | cosmetic | CSS media query; reduce spacing. |
| `src/components/CommunityShell.tsx:46` | `clamp(2rem, 5vw, 4rem)` | yes | Nothing needed. |
| `src/components/CommunityShell.tsx:72` | text `maxWidth: 800px`, marginBottom `2.5rem` | yes | Nothing needed; max width only. |
| `src/components/MagicCursor.tsx:36` | cursor `zIndex: 100` | yes | Nothing needed if hidden/disabled on touch; otherwise disable custom cursor on coarse pointers. |
| `src/components/MagneticSurface.tsx:77` | hover zIndex `10` | yes | Nothing needed; local interaction layer. |

## Summary

28 issues found: 2 critical, 16 moderate, 10 cosmetic.

- Critical: v2 home absolute marginalia overflows narrow screens; v2 challenge detail uses a two-column grid and 4rem padding.
- Moderate: large mobile-visible padding/spacing, fixed overlays/toasts, absolute controls, and legacy hero/decorative elements need mobile media rules.
- Cosmetic: vertical rhythm is often too airy on mobile but does not hide core content.

