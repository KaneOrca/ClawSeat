---
name: cartooner-harness
description: AIGC creative chain orchestration protocol for Cartooner-bound clawseat-creative projects. Use when bootstrapping a creative team roster (memory + writer + builder-image + builder-av + patrol), spawning generation lanes, depositing assets, running pick_winner tournaments where user is the sole aesthetic judge, iterating on user feedback routed to L1 / L2 / L3 layers, sharing style_bible / character_dna across lanes, switching automation modes, ingesting YouTube reference for cinematic shot decisions, or rendering the asset-tree console. Built on three protocol-level hard rules: (1) no-image-policy — only user views asset content in main threads; LLM seats use isolated subagents for any vision input; (2) Vision Steward — memory is a process-automation engine, never an aesthetic judge; (3) Producer-centric — user is the Producer with final authority and may bypass memory to direct any seat. Distinct from gstack-harness (engineering protocol). The two protocols share runtime infrastructure (sandbox HOME / launcher) but are otherwise parallel layers.
---

# Cartooner Harness

`cartooner-harness` is the runtime orchestration core for ClawSeat creative
chains bound to cartooner skills.

It is **parallel** to `gstack-harness`, not built on top of it. The
engineering chain's `task → dispatch → handoff → ack` model breaks down for
creative work because:

- creative output is **asset-centric** (image / video / audio), not commit-centric
- creative review is **multi-candidate director-pick**, not boolean reviewer-verdict
- creative iteration is **continuous user-shaped exploration**, not spec-then-build
- creative coherence is **shared style + character DNA**, not file-disjoint

cartooner-harness exposes a different vocabulary: **lane / deposit / pick /
iterate** primitives built around the AIGC reality that user is the
unique aesthetic judge and LLM seats should never view generated assets.

## Three Protocol-Level Hard Rules

### 1. No-Image Policy (see [`references/no-image-policy.md`](references/no-image-policy.md))

| Role | Permitted to view image / video / audio content? |
|---|---|
| `user` | Unlimited |
| `builder-image` / `builder-av` | Only inside isolated subagents (root-cause / reference-learning), never in main thread |
| `memory`, `writer`, `patrol` | Never |

This rule is non-negotiable. Token / cache / context economics break the
protocol if violated.

### 2. Vision Steward (memory ≠ aesthetic judge)

`memory` is a **process-automation engine**, not a creative decider:

- maintains state (`PROJECT_INDEX.json`, `generation_log.jsonl`)
- coordinates lanes / phases / cross-modal handoffs
- runs metadata-level compliance checks (no visual judgments)
- escalates **all** aesthetic decisions to user
- in auto mode: default `pick_strategy = escalate-always`; only model-provided
  numeric scores (when available) may drive `model-metadata-rank` strategy

### 3. Producer-Centric (user-direct allowed for all seats)

`user` is the Producer. May directly address any seat (including patrol,
read-only). Any seat receiving user-direct must call `report_to_memory.py`
fail-closed before continuing.

## Mental Model: AIGC Creator's Studio (not film set)

Traditional film roles are used **only as analogies for boundary clarity**,
not as identity definitions. AIGC has its own native role structure:

| AIGC native role | ClawSeat seat | Film analogy (for intuition only) |
|---|---|---|
| **Creator** | `user` | Producer + Director |
| **Vision Steward** | `memory` | Line Producer + DIT + Script Supervisor |
| **Story Specialist** | `writer` | Screenwriter |
| **Image Specialist** | `builder-image` | DP + Production Designer |
| **AV Cinematographer** | `builder-av` | DP for video + Composer + Editor + Storyboard Artist |
| **Asset Guardian** | `patrol` | Data Wrangler |

`user` is the only seat that creates vision and judges aesthetics. Every
other seat executes within constraints user has anchored in `vision_spec.md`,
`style_bible.md`, `character_dna.json`.

## The Seven Creative-Direction Responsibilities

In AIGC workflow, "directing" decomposes into seven responsibilities. Most
cannot be delegated to LLM seats; this drives the protocol's escalation
defaults.

| # | Responsibility | Owner | Auto mode? |
|---|---|---|---|
| 1 | **Brief anchoring** (compress vague intent into actionable spec) | user → memory (memory records) | No — always user |
| 2 | **Style convergence** (calibration loops to lock visual / tonal direction) | user picks; memory runs the loop | Loop runs auto, lock requires user |
| 3 | **Pick & Reject** (curate among candidates) | user (default); memory may auto-pick only with explicit `model-metadata-rank` strategy | Mostly user; rare auto |
| 4 | **Iteration direction** (route feedback to L1/L2/L3) | user articulates intent; memory routes layer; builder-* executes adjustment | No — always needs user feedback |
| 5 | **Cross-modal integration** (image → video, video + music) | memory coordinates; builder-* execute per shot_list join keys | Yes — rule-driven |
| 6 | **Vision guard** (consistency across lanes / phases / modalities) | memory does metadata compliance; visual coherence is user's verification | Metadata yes; visual no |
| 7 | **Stop criterion** (when is it good enough?) | user only | No — always user |

## The 3-Layer Prompt Model

(See [`references/3-layer-prompt-model.md`](references/3-layer-prompt-model.md))

Creative prompt engineering is layered; each seat owns one layer:

```
L1 — Creative Intent
   ┌─────────────────────────────────────────────┐
   │ "30s 红苹果广告, 国风暗黑 mood, 抖音 25-35 女性" │
   │ Owner: user ↔ memory                          │
   │ Files: brief.md, vision_spec.md, style_bible.md│
   └─────────────────────────────────────────────┘
              ↓
L2 — Narrative + Shot List (split into two artifacts)
   ┌─────────────────────────────────────────────┐
   │ narrative_outline.md (literary)               │
   │   "苹果在山间露珠中诞生..."                    │
   │   Owner: writer                                │
   ├─────────────────────────────────────────────┤
   │ shot_list.toml (structured cinematic metadata)│
   │   shot-1: close-up, 5s, slow zoom, 宁静神秘    │
   │   Owner: builder-av (uses cartooner-seedance- │
   │           cookbook + reference-learning sub-  │
   │           agent for YouTube-grounded decisions)│
   └─────────────────────────────────────────────┘
              ↓
L3 — Model-Specific Prompts (per shot, per modality)
   ┌─────────────────────────────────────────────┐
   │ Image: nb2 / nbp / gpt-image-2 syntax         │
   │   Owner: builder-image                         │
   ├─────────────────────────────────────────────┤
   │ Video: Seedance 2.0 13-mode syntax            │
   │   Owner: builder-av                            │
   ├─────────────────────────────────────────────┤
   │ Audio: MiniMax music / TTS syntax             │
   │   Owner: builder-av                            │
   └─────────────────────────────────────────────┘
              ↓
            Asset
```

**Critical separation**: `writer` writes pure narrative; `builder-av` decomposes
narrative into structured shot list (because shot decisions require
cinematographer expertise — Seedance modes, camera vocabulary, reference
learning). builder-image and builder-av both consume `shot_list.toml`.

## Seat Roster

(See [`references/aigc-roles.md`](references/aigc-roles.md) for full responsibility breakdowns)

| Seat | Tool / provider | Core responsibility |
|---|---|---|
| **memory** | **claude / minimax-api** | Vision Steward — state, coordination, escalation; never views assets. MiniMax chosen for high-frequency long-session work without OAuth quota pressure. |
| **writer** | claude / oauth | Story Specialist — narrative_outline.md only; pure literary; never camera/shot decisions |
| **builder-image** | codex / oauth | Image Specialist — translates shot_list to image prompts; runs cartooner-image / -storyboard / -design |
| **builder-av** | **gemini / oauth** ⭐ | AV Cinematographer — owns shot_list authoring (with YouTube reference-learning) AND av generation |
| **patrol** | claude / minimax-api | Asset Guardian — read-only file metadata checks; SLA monitoring |

`builder-av` uses Gemini specifically for its YouTube ingestion capability
in reference-learning subagents. No other LLM provider currently supports
this.

## Skill Authorization Matrix

cartooner-harness mirrors all skills under `~/.agents/skills/` into each
seat's tool home (sandbox-level). Each seat is **authorized** to invoke
only the skills listed below; invoking unauthorized skills is a protocol
violation that `patrol` audits via `generation_log.jsonl`.

| Seat | Authorized skills | Forbidden examples |
|---|---|---|
| **memory** | `cartooner-harness`, `cartooner` (router), `cartooner-resource-ops` | Any image/video/audio skill (no-image-policy); `cartooner-script-development` (writer's domain); `viral-copywriter`; any L3 prompt skill |
| **writer** | `cartooner-harness`, `cartooner-script-development`, `viral-copywriter` | Any `cartooner-image / -video / -audio` skill (text-only seat); any model-prompt skill (no L3 work); no PROJECT_INDEX writes |
| **builder-image** | `cartooner-harness`, `cartooner-image`, `cartooner-storyboard`, `cartooner-design`, `nano-banana`, `gpt-image-2` | `cartooner-prompt` (video-side, builder-av's domain); `cartooner-video / -audio` (av); `cartooner-script-development` (writer's) |
| **builder-av** | `cartooner-harness`, `cartooner-video`, `cartooner-audio`, `cartooner-prompt`, `cartooner-seedance-cookbook` | `cartooner-image / -storyboard / -design` (image lane); `cartooner-script-development` (writer's) |
| **patrol** | `cartooner-harness`, `cartooner-resource-ops` | **Any generation skill** (read-only seat); never deposit any asset; never `pick_winner.py` (no decision authority) |

### Why these boundaries matter

- **Specialization**: each seat loads only the references / vocabulary it
  needs. Cross-domain invocations leak L3 prompt knowledge into the wrong
  context (e.g., memory thinking about Seedance vocabulary).
- **No-image-policy enforcement**: memory / writer / patrol never invoking
  image / video / audio skills means they never receive vision input,
  preserving cache and baseline size.
- **Protocol clarity**: when `patrol` sees `memory invoked cartooner-image`
  in `generation_log.jsonl`, that is a violation to be alerted, not a
  feature to be tolerated.

### Soft enforcement (v1 strategy)

cartooner-harness v1 uses **soft enforcement**:

1. This authorization matrix is embedded into each seat's `AGENTS.md` via
   the cartooner-harness/SKILL.md role contract render. The seat sees its
   own authorized list and self-restrains.
2. `patrol_pipeline_sla.py --audit-skill-authorization` scans
   `generation_log.jsonl` for any `{seat, skill_invoked}` pair where
   `skill_invoked ∉ authorized(seat)`. Violations alert memory; memory
   escalates to user (`seat_authorization_violation` is a default
   `escalate_on` trigger).

Hard physical isolation (per-seat sandbox skill mirror) is **future work**
documented in `references/skill-isolation-roadmap.md` (not v1). The current
mirror semantics ship the same `~/.agents/skills/*` to every seat; v1
relies on the protocol contract + audit, not filesystem-level isolation.

## Persistence Layout (replaces ~/.cartooner/_handoff/)

```
~/.cartooner/projects/<project-id>/
├── PROJECT_INDEX.json              # asset tree index
├── brief.md                        # original user request (L1)
├── vision_spec.md                  # auto-mode handoff: compliance + escalation rules
├── style_bible.md                  # visual / tonal style for crew (L1)
├── character_dna.json              # character three-views / expressions / props
├── narrative_outline.md            # literary script (L2, writer-owned)
├── shot_list.toml                  # cinematic metadata (L2, builder-av-owned)
├── automation.toml                 # mode + escalation thresholds
├── lanes/
│   └── <lane-id>.toml              # spawn state, prompt, model, params
├── assets/
│   ├── images/<asset-id>.png       # builder-image deposits
│   ├── videos/<asset-id>.mp4       # builder-av deposits
│   └── audios/<asset-id>.wav       # builder-av deposits
├── tournaments/
│   └── <round-id>.toml             # candidate set + pick history
├── references_learned/
│   └── <subagent-id>.md            # reference-learning subagent text reports (e.g., YouTube shot analyses)
└── generation_log.jsonl            # append-only history
```

`~/.cartooner/_handoff/` is removed. cartooner-harness is a clean break.

## Protocol Primitives (10 scripts)

| Script | Caller | Effect |
|---|---|---|
| `spawn_lane.py` | memory (or seat self-dispatch) | Open N concurrent generation lanes on a target seat |
| `deposit_asset.py` | builder-* | Persist a generated asset with model_metadata + file_metadata only (no LLM self-eval) |
| `pick_winner.py` | memory | Expose N candidates to user (or auto-pick when configured); record pick |
| `iterate_prompt.py` | memory | Route user feedback to L1 / L2 / L3 and re-spawn |
| `share_style_bible.py` | memory | Push style_bible.md / character_dna.json metadata to lanes |
| `render_asset_tree.py` | any seat | CLI view: asset tree + active lanes + tournament status |
| `patrol_pipeline_sla.py` | patrol | Probe pipeline + verify PROJECT_INDEX.json; alert on degradation |
| `report_to_memory.py` | any seat (mandatory after user-direct) | Notify memory of any user-direct request fail-closed |
| `set_automation_mode.py` | user | Toggle manual / auto, configure pick_strategy + escalate_on |
| `spawn_subagent.py` | builder-image / builder-av | Spawn isolated subagent (root-cause / reference-learning); enforce no-image-policy boundary |

`spawn_subagent.py` is the **only** sanctioned mechanism for any seat
other than user to view asset content or external reference media. Subagent
context is discarded on return; main thread receives text reports only.

## UI Layer (separate from protocol)

The protocol scripts are **pure backend**: they manage state (PROJECT_INDEX,
lane TOMLs, generation_log, tournaments, iterations) but never prompt the
user directly. The UI for collecting user input is the **caller seat's**
responsibility, and varies by seat's underlying tool:

| Seat (tool) | UI mechanism for user prompts | Example |
|---|---|---|
| **memory (Claude Code)** | Native `AskUserQuestion` tool — structured options form | `pick_winner` candidate selection; `iterate_prompt` layer confirmation; `escalate_to_producer` resume / abort |
| **builder-image (Codex CLI)** | tmux pane direct chat — user types in seat's pane | user-direct: "再来 4 张更暗的" → builder-image acts then `report_to_memory.py` |
| **builder-av (Gemini CLI)** | tmux pane direct chat | user-direct: "ingest @youtube/wkw for shot rhythm" |
| **writer (Claude Code)** | Native `AskUserQuestion` (rare; usually memory mediates) | clarifying questions during narrative drafting |
| **patrol (Claude Code)** | None — read-only seat; queries answered in pane responses, no AskUserQuestion needed | "what's pipeline SLA?" → patrol prints status to pane |

**Caller flow (manual-mode pick_winner)**:

```
memory (Claude Code, manual mode)
   ↓ enumerate candidates from PROJECT_INDEX.assets where shot_id == X
   ↓ AskUserQuestion(
       question="Pick winner for shot-1:",
       options=[<candidate metadata + paths>, "Reject all"]
     )
   ↓ user selects in Claude Code UI
   ↓ if user picked one:
   ↓   subprocess pick_winner.py --picked <id> --strategy manual
   ↓ else if user "Reject all":
   ↓   subprocess pick_winner.py --reject-all
   ↓   AskUserQuestion(question="What's wrong?") → user types feedback
   ↓   subprocess iterate_prompt.py --layer L3 --feedback "<text>" --parent-lane <id>
```

**Caller flow (auto-mode pick_winner)**:

```
memory (Claude Code, auto mode + model-metadata-rank strategy)
   ↓ enumerate candidates
   ↓ subprocess pick_winner.py --strategy model-metadata-rank --min-score 0.75
   ↓ if exits 0:    proceed to next phase
   ↓ if exits non-zero (no qualifying winner):
   ↓   subprocess escalate_to_producer.py --trigger tournament_ready_no_auto_pick_strategy
```

**Why this split matters**:

- **Cross-tool portability**: protocol scripts work the same for memory
  (Claude Code) and builder-* (Codex / Gemini); only the UI layer varies
- **Testability**: pure-backend scripts are subprocess-testable without
  mocking LLM tool calls
- **Auto/manual symmetry**: same `pick_winner.py` accepts both manual
  picks (`--picked <id>` from AskUserQuestion result) and auto picks
  (`--strategy model-metadata-rank` reads from index, no UI)
- **Audit consistency**: every pick / iterate / escalate writes the same
  generation_log shape, regardless of UI origin

## User Direct Channel

(See [`references/user-direct-contract.md`](references/user-direct-contract.md))

| Seat | Mutate | Query | Notes |
|---|---|---|---|
| memory | ✅ | ✅ | Default channel |
| writer | ✅ | ✅ | Rewrite scenes / dialogue |
| builder-image | ✅ | ✅ | Re-spawn lanes / override prompts |
| builder-av | ✅ | ✅ | Re-spawn lanes / re-author shot_list / ingest reference YouTube |
| patrol | ❌ | ✅ | Read-only queries (status / SLA / integrity) |

Mandatory contract: any seat receiving user-direct must call
`report_to_memory.py` fail-closed before / during execution.

Conflict resolution: Producer always wins. New user-direct requests may
supersede in-flight memory dispatches via `report_to_memory.py --supersedes`.

## Automation Mode

(See [`references/automation-mode.md`](references/automation-mode.md))

`memory` operates in two modes via `set_automation_mode.py`:

### Manual mode (default)

User is active Director + Producer. Memory coordinates state, never picks
or iterates without user. All `pick_winner` calls block on user input.

### Auto mode (process-automation engine)

User delegates **process automation only**, not creative judgment. Memory
may:
- spawn lanes per `vision_spec.md` plan
- transition lane states (`spawned → generating → deposited`)
- detect lane completion (api_status + file checks)
- aggregate candidates into tournaments
- call `auto_pick.py` only if `pick_strategy = "model-metadata-rank"` and
  model provides aesthetic_score

Memory **must escalate** on:
- `lane_failure` (API error / deposit fail)
- `sla_breach` (patrol-detected)
- `phase_transition` (script → image → video → audio → integration)
- `budget_exhausted`
- `tournament_ready_no_auto_pick_strategy` (default)
- `user_direct_received` (auto-flip back to manual)

All auto decisions are logged with full reasoning + alternatives for undo.

## Use this skill when

- Bootstrapping a `clawseat-creative` project
- Spawning concurrent generation lanes for image / video / audio
- Running pick tournaments where user is sole aesthetic judge
- Iterating on user feedback through L1 / L2 / L3 routing
- Authoring shot_list.toml with cinematic decisions (builder-av)
- Ingesting YouTube reference media for shot inspiration (builder-av reference-learning subagent)
- Auditing an auto-mode session before accepting deliverables

## Do NOT use this skill for

- Engineering tasks (code, tests, CI, PRs) — use `gstack-harness`
- Single-shot one-off generation without project context — use `cartooner` router directly
- Aesthetic judgment by LLM (this protocol explicitly forbids it)
- Cross-project resource management — use `cartooner-resource-ops`

## References

- [`references/no-image-policy.md`](references/no-image-policy.md) — Hard rule on asset viewing
- [`references/aigc-roles.md`](references/aigc-roles.md) — Full seat responsibility breakdowns
- [`references/3-layer-prompt-model.md`](references/3-layer-prompt-model.md) — L1 / L2 / L3 split + iterate routing
- [`references/lane-model.md`](references/lane-model.md) — lane state machine + payload
- [`references/shot-list-schema.md`](references/shot-list-schema.md) — shot_list.toml format
- [`references/style-bible-schema.md`](references/style-bible-schema.md) — style_bible.md format
- [`references/character-dna-schema.md`](references/character-dna-schema.md) — character_dna.json format
- [`references/asset-deposit-schema.md`](references/asset-deposit-schema.md) — deposit_asset payload
- [`references/generation-log-schema.md`](references/generation-log-schema.md) — append-only log format
- [`references/tournament-protocol.md`](references/tournament-protocol.md) — pick_winner candidate sets
- [`references/iteration-protocol.md`](references/iteration-protocol.md) — feedback layer routing
- [`references/automation-mode.md`](references/automation-mode.md) — manual vs auto, escalation, audit/undo
- [`references/user-direct-contract.md`](references/user-direct-contract.md) — Producer intervention rules
- [`references/subagent-protocol.md`](references/subagent-protocol.md) — root-cause + reference-learning subagent contracts
- [`references/pipeline-sla.md`](references/pipeline-sla.md) — pipeline health metrics
