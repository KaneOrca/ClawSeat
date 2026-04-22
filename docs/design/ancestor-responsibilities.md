# Ancestor Seat — Responsibility Matrix (v0.1 draft)

> **Status**: Provisional. Binding after architect review.
> **Owner (draft author)**: TUI engineer.
> **Reviewer**: architect (v0.4 Phase 2 approval).
> **Supersedes**: nothing (first time we codify the ancestor role).
> **Amends**: koder's historical "owns all seat lifecycle operations" claim
> (see `~/.agents/engineers/koder/engineer.toml` `role_details`). Koder no
> longer owns lifecycle. Ancestor does.

## 1. Purpose

The `ancestor` seat is the project-level autonomous supervisor. It exists
for the entire lifespan of the project — created once at `install` time,
never retired, never promoted. Its job is to keep the project's seat
topology healthy (bootstrap → patrol → restart / reconfigure) and to
surface project-level observability events to operators (Feishu).

## 2. Role coordinates (how ancestor fits)

```
USER
  │
  ▼                                   (tenant layer)
[koder]  OpenClaw frontstage, owns user intake only.
  │      Routes every user input to planner; never touches seats.
  │
  ▼                                   (project layer)
[planner] ────────→ builder / reviewer / qa / designer
  │                   (specialists; dispatched tasks)
  │
[ancestor] ─────→  memory (via memory's API, never direct file writes)
  │
  └── watches every seat above; owns lifecycle for all of them.
```

## 3. Ancestor DOES (✅ full list)

### 3.1 Bootstrap phase (one-shot, runs once per project install)

| # | Duty | How |
|---|------|-----|
| B1 | Read `ancestor-bootstrap.md` brief | path: `~/.agents/tasks/<project>/patrol/handoffs/ancestor-bootstrap.md` |
| B2 | Verify-or-launch `machine.toml.services.memory` | `tmux has-session -t =machine-memory-claude`; if absent, ancestor launches it via `agent-launcher.sh --headless --session machine-memory-claude --tool <t> --auth <a>` using machine.toml.services.memory config; re-verify. Still down → Feishu-alert, continue (do NOT halt; see §6.3) |
| B3 | Verify OpenClaw tenant binding | read `~/.openclaw/workspace-<tenant>/WORKSPACE_CONTRACT.toml.project` matches `profile.project_name`; mismatch → Feishu-alert, halt |
| B4 | Launch every pending project seat | For each seat in `profile.seats` (excluding self): expand `sessions[]` (fan-out = `parallel_instances` entries, `<project>-<role>-<N>-<tool>`); per session `agent-launcher.sh --headless --session <name> --tool <t> --auth <a>` |
| B5 | Verify Feishu group binding | read `~/.agents/tasks/<project>/PROJECT_BINDING.toml.feishu_group_id`; present + non-empty = pass. Absent → halt Phase-A + stderr alert ("installer should have written this before spawning ancestor"). Ancestor does NOT prompt operator (would violate N1). |
| B6 | Smoke-dispatch `OC_DELEGATION_REPORT_V1` | verifies planner↔Feishu round-trip |
| B7 | Declare `phase=ready` + enter Phase-B | write `~/.agents/tasks/<project>/STATUS.md`; no operator-ack gate |

### 3.2 Steady-state patrol (recurring, `patrol.cadence_minutes` from profile)

| # | Duty | How |
|---|------|-----|
| P1 | Liveness check every project seat | `tmux has-session -t =<session>` per `profile.seats` |
| P2 | Restart dead seats | `agent-launcher.sh --headless --session <same>` with **current** `seat_overrides` — see §6.1 drift policy |
| P3 | Scan `~/.agents/tasks/<project>/patrol/handoffs/` for new events | diff against last-seen fingerprint |
| P4 | Forward whitelisted events to Feishu | whitelist from `observability.announce_event_types` in profile |
| P5 | Summarize state into `STATUS.md` | seats alive, queue depth, last event time, patrol uptime |
| P6 | Detect anomalies | `context_near_limit` / `blocked_on_modal` — log via memory seat, broadcast to Feishu |
| P7 | Record learning notes | call memory seat's public API; never write memory storage directly |

### 3.3 Seat lifecycle (accepted from koder; ancestor now owns)

| # | Duty | How |
|---|------|-----|
| L1 | Add seat (add a new role that wasn't in profile) | operator request → ancestor validates against v0.4 LEGAL_SEAT_ROLES → writes profile update via `profile_validator.write_validated` → launches tmux session |
| L2 | Remove seat | operator request → ancestor kills tmux session cleanly → removes from profile `seats[]` → `write_validated` |
| L3 | Reconfigure seat (change tool/auth/provider) | operator request → kill+restart with new overrides; preserves workspace state |
| L4 | Restart seat (recover from crash / drift) | see §6.1 |
| L5 | Launch machine service | machine-level singleton (memory) launch via `agent-launcher.sh --headless --session machine-<service>-<tool>`; executed only from B2 on fresh-machine path; subsequent ancestors on the same machine find it alive and skip |
| L6 | Spawn sibling project (one-shot) | receives `OC_DELEGATION_REPORT_V1 kind=clone_project_request` from own planner; clones own profile → new project's profile/binding/brief; launches new ancestor via `agent-launcher.sh --headless --session <new>-ancestor-<tool>`; after spawn, new project's lifecycle belongs entirely to the new ancestor. Does NOT mutate any other already-existing project. |

All lifecycle ops require an operator trigger (via koder intake → planner → explicit dispatch to ancestor, OR direct Feishu command targeting ancestor). Ancestor never initiates lifecycle mutations autonomously — only restart in the passive sense (P2).

## 4. Ancestor DOES NOT (❌ hard prohibitions)

| # | Forbidden | Why |
|---|-----------|-----|
| N1 | Receive user messages | Only koder talks to the human |
| N2 | Dispatch work to builder / reviewer / qa / designer | Planner's exclusive domain |
| N3 | Be "upgraded" to koder | Parallel roles, never interchangeable |
| N4 | Retire | Lives for the project's full lifetime |
| N5 | Write to memory's workspace files | Use memory seat's public API |
| N6 | Send `OC_DELEGATION_REPORT_V1` with dispatch semantics (`decision_hint=proceed` / `next_action=retry_current_lane`) | Only status-class payloads (`report_status=in_progress/done/blocked`) |
| N7 | Call `start_seat.py` | Legacy path (was koder's); now migrated to direct `agent-launcher.sh` invocation from ancestor |
| N8 | Modify `machine.toml` | Machine layer is outside project's authority |
| N9 | Auto-repair mis-bound OpenClaw tenants | Surface via Feishu; human must re-bind |

## 5. Communication channels

| Direction | Medium | Identity | Notes |
|-----------|--------|----------|-------|
| ancestor → operator (status, alerts) | Feishu group | uses **planner's** lark-cli OAuth identity; message must include `sender_seat: ancestor` field in envelope | per operator decision 2026-04-21 Q2=a |
| ancestor → memory | memory seat's API (via MCP or stdio-based call) | — | never direct file I/O |
| ancestor → other seats (restart etc.) | agent-launcher.sh + tmux | — | shell-level, no RPC |
| operator → ancestor (lifecycle trigger) | koder-routed command → planner → ancestor | — | mediated, never direct user-channel |

## 6. Edge-case policies

### 6.1 Config-drift recovery (Q1 decision, 2026-04-21)

When ancestor restarts a dead seat:

1. Read the **current** `profile.seat_overrides.<seat>`.
2. Compare to what the dead seat was last known to run (from `session.toml` or handoff log).
3. If identical → silent restart.
4. If different → restart with **current** overrides (the new config wins) **and** emit Feishu event:

   ```json
   {
     "event": "config-drift-recovery",
     "seat": "builder",
     "was": {"tool": "claude", "auth_mode": "oauth_token"},
     "now": {"tool": "codex", "auth_mode": "api"},
     "reason": "operator changed profile; seat crashed before pickup"
   }
   ```

   Rationale: profile edits are intentional; blocking on user confirmation
   would leave the project seat-less for hours while waiting. Emitting a
   loud event gives operators the audit trail they need.

### 6.2 Ancestor itself crashes

Ancestor crashing is an infra-level failure. Recovery path:

1. `tmux-continuum` / `tmux-resurrect` restarts the session automatically.
2. On boot, ancestor re-reads `ancestor-bootstrap.md` — if `STATUS.md` says
   `phase=ready` it enters Phase B directly (no rebootstrap).
3. Brief is idempotent: B-steps check "already done?" before re-executing.

### 6.3 Memory singleton unreachable during bootstrap

Ancestor does NOT block. It:
1. Alerts operator via Feishu.
2. Launches non-memory-dependent seats (planner, builder, reviewer, qa, designer).
3. Repeatedly re-checks memory every patrol cycle (P-phase).
4. Queued learning notes buffered locally until memory returns.

## 7. Boundaries with koder (updated)

Historically koder's `role_details` claimed "owns all seat lifecycle operations".
This claim is **revoked** as of v0.4 Phase 2:

- Koder stays a frontstage intake router only.
- Seat lifecycle moves entirely to ancestor.
- When a user asks koder to "add a builder-2", koder routes the request
  through planner to ancestor as any other task — it no longer executes
  `start_seat.py` itself.

**Architect action requested**: confirm the koder engineer.toml update
and (if applicable) the `core/skills/clawseat-koder-frontstage/SKILL.md`
edit to remove the lifecycle responsibility claim.

## 8. Open questions / deferred

None outstanding for v0.1. The review packet calls out two items that
need architect sign-off before implementation proceeds past provisional:

- K1: koder `role_details` edit (section 7 above)
- B1: bootstrap brief schema stability (see `ancestor-bootstrap-brief.md`)

---

**End of v0.1 matrix.**
