# Phase 7 Retirement — Environment Validation Complete

**Retired**: 2026-04-18
**Retiring author**: 始祖 CC (bash / reviewer role)
**Co-signer**: 张根铭 (user, final approval)

---

## Retirement criteria (all met)

### 1. Multi-seat harness attached and stable

- 6 seats running: `memory`, `koder`, `planner`, `builder-1`, `reviewer-1`, `qa-1`
- Plus `designer-1` (gemini) provisioned and addressable
- Runtime matrix verified: claude+oauth / claude+api+minimax / codex+oauth / gemini+oauth
- Per-tool TUI idle-marker invariants locked in `tests/test_onboarding_markers.py`

### 2. Non-trivial task chain end-to-end

| Chain | Bundles | Outcome | Peak complexity |
|---|---|---|---|
| **M1 memory-seat v3** | b1a + b1b + fix1 + fix2 + rev3 + qa + qa-live | APPROVED ✅ | **7-round CHANGES_REQUESTED iteration** |
| **M2 project scanner** | bundle-A + bundle-B + fix1 + qa | APPROVED ✅ | 3-round iteration, 199 new tests |
| **followup-rawtmux-fix** | single | APPROVED ✅ | cross-role template.toml hardening |
| **followup-sendverify-race** | bundle + remediation + r2 + qa | APPROVED ✅ | superseded by simplify |
| **sendverify-simplify** | bundle + r1 + r2 + qa | APPROVED ✅ | fire-and-forget architectural shift |
| **followup-bootstrap-sync** | single + fix1 + qa | APPROVED ✅ | refresh-workspace primitive |
| **koder guard** (in-place) | bash patch | LANDED ✅ | commit 48b799d |
| **followup-planner-announce** (v1) | bundle + qa | CLOSED (gate dead, superseded) | env-var gate reveal |
| **followup-planner-announce-v2** | bundle + fixes + qa | APPROVED ✅ | config-first pattern |
| **followup-planner-announce-v2-fix-e2e** | single | APPROVED ✅ | reverse-assertion correction |
| **followup-batch4-p2** (#10 + #11) | bundle + qa | APPROVED ✅ | AGENTS.md de-bloat |
| **followup-p1-gating** (#7 + #15 + #23) | bundle + qa | APPROVED ✅ | three-in-one refactor |

Total: **12+ chains** closed with proper OC_DELEGATION_REPORT_V1 Feishu closeout.

### 3. Protocol invariants verified live

- ✅ Feishu `OC_DELEGATION_REPORT_V1` path: planner → koder closeout confirmed delivered
- ✅ Feishu announce path: dispatch / completion events broadcast (real messages received by user)
- ✅ Guard 48b799d: non-planner → koder dispatch rejected with clear error
- ✅ `USER_DECISION_NEEDED` gate: multiple live user-decision events (B scheme, A scheme, option A)
- ✅ Auto-chain reply_to pattern (planner → builder → reviewer): works but #13 to tighten
- ✅ Consumed ACK + durable receipt + dispatch chain: traceable on disk

### 4. Quality gates

- **pytest 553/553 passed** at retirement HEAD `a7f326d`
- **origin/main synced** to `a7f326d` (no pending unpushed commits)
- **28 systemic followups captured** in `design/followups-after-m1.md`
  (11 already closed, 17 open for Phase 8 batches)
- **SPEC correction logs** appended to M1 SPEC §10 and M2 SPEC §9

---

## What Phase 7 actually proved

1. **ClawSeat harness can execute production-quality chains under real user oversight**, not just smoke loops.
2. **Spec drift is the dominant risk**, not code bugs. M1 §4, M2 §5.3, #24 gate, #22 closeout all trace to the same pattern: specs written without grepping the real codebase or runtime state first.
3. **Fail-safe fallbacks need explicit success paths**, otherwise they invite misdiagnosis (#24 lark-cli "problem" was actually success; E2E assertion inverted).
4. **Observability is load-bearing infrastructure**, not nice-to-have. Every bug we caught in Phase 7 was visible only because we had bash + tmux capture + receipts. Once Feishu announce lands cleanly (v2-fix), Phase 8 will debug itself.
5. **Chain discipline holds up under stress**. 7-round M1 bundle-A fix cycle did not produce scope creep, role confusion, or lost receipts. The SSOT pattern (`design/*.md` as authoritative + planner as orchestrator + guard at critical closeout points) scales.

---

## Open items punted to Phase 8

From `design/followups-after-m1.md`, the following stay open:

**P0** (Phase 8 Batch 2 candidates):
- #9 `engineer_create` update profile.seats atomically (originally batch 1, superseded by different issues each round)
- #16 `dispatch_task.py` idempotent guard (duplicate queue entries from koder retry)
- #17 koder retry discipline (notify vs dispatch disambiguation)

**P1**:
- #12 koder-never-bypass-planner template rule
- #13 specialist reply_to field honor
- #14 planner surprised_ack detection
- #18 eng-review AUTO_ADVANCE `phase=plan` vs `phase=impl` semantics
- #21 specialist transport-failed explicit no-fallback path
- #28 pytest-green is closeout prerequisite

**P2**:
- #25 seat branch discipline (feature branch drift)

**Milestones**:
- M3 refresh handler
- M4 research lane
- M5 events.log write hooks
- M6 koder heartbeat extension

---

## Phase 8 kickoff criteria

Before Phase 8 starts, recommend:
1. Batch 2 P0 landing (9/16/17) — removes all remaining silent failure modes
2. Batch 3 P1 verdict-language polish (12/13/14/18/21/28)
3. Then M3 SPEC + dispatch

---

## Signatures

- **始祖 CC** (bash reviewer role, writer of M1/M2 SPECs, #24/#26/#22 reviewer, retirement author): **retired**
- **张根铭** (user, final decision authority, Feishu-gate actor): **retired** (per message 2026-04-18 "按你推荐")

Phase 7 closed. Phase 8 ready on demand.
