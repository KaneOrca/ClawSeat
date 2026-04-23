# TASK: Round-2 fixes — wait-for-seat fallback + Codex launcher YOLO parity

**Assigned to**: codex-xcode (tmux `codex-xcode-api-clawseat-20260423-204444`)
**Dispatched by**: planner Claude Code
**Scope**: 2 fixes. Both stay on experimental branch at `/Users/ywf/ClawSeat`.

## Context

Round-1 regression fix review feedback from codex-chatgpt:
> "The remaining regression is in the stricter wait-for-seat.sh contract, **not** in the resolver rollback."

Your round-1 conflated two independent issues. The resolver alias removal (HIGH) was correct. But you also **deleted the suffix fallback entirely** from wait-for-seat.sh, which was a separate issue (MEDIUM) requiring a narrower fix. Planner (me) confirmed that with the alias bridge gone from the resolver, restoring the fallback does **not** re-introduce ambiguity, so it's safe to add back as a last-resort with visibility guardrails.

Separately, during the full-chain install test, the user observed that the ancestor Claude Code launches Codex-backed seats **without full-access mode**, while Claude-backed seats correctly get `--dangerously-skip-permissions`. This is a tool-parity bug.

## Fix 1 — Restore wait-for-seat.sh fallback with guardrails

**File**: `/Users/ywf/ClawSeat/scripts/wait-for-seat.sh`

**Current (after round-1)**: Resolves via `agentctl session-name`. If that fails or canonical session absent → wait forever.

**Required**:
1. Keep `agentctl session-name <seat> --project <project>` as the **primary** resolution path (don't revert)
2. If primary fails N consecutive polls (recommend N=10 polls × 2s = 20s), attempt a **last-resort** fallback:
   ```bash
   for suffix in claude codex gemini; do
     candidate="${PROJECT}-${SEAT}-${suffix}"
     if tmux has-session -t "=$candidate" 2>/dev/null; then
       echo "WARN: agentctl resolution failed after N attempts; falling back to '$candidate'" >&2
       exec tmux attach -t "=$candidate"
     fi
   done
   ```
3. If fallback also finds nothing, keep waiting on primary but emit a stderr warn every M polls (e.g., every 30s) so degradation is visible
4. **Only scan the three fixed suffixes** (`claude` / `codex` / `gemini`) — do NOT do fuzzy/prefix matching (that's what re-introduces ambiguity)

**Why these three guardrails matter**:
- Primary retry budget avoids flaky fallback when agentctl is just slow
- Fixed-suffix list (not prefix scan) prevents the `foo-bar-designer` ambiguity from reappearing
- Stderr WARN makes degradation visible so operators can diagnose agentctl issues

## Fix 2 — Codex launcher YOLO parity

**File**: `/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh`

**Current**: Codex exec lines at 764, 826, 828, 830 lack any YOLO/bypass-sandbox flag. Reference Claude parity at lines 642, 745 using `--dangerously-skip-permissions`.

**Codex CLI 0.123 equivalent flag**: `--dangerously-bypass-approvals-and-sandbox`

(Confirmed via `codex --help` — it's the documented flag that skips both approvals AND sandbox, matching Claude's `--dangerously-skip-permissions` intent. Alternatives `--full-auto` and `-a never` have different semantics and sandbox still applies.)

**Required**:
1. Add `--dangerously-bypass-approvals-and-sandbox` to all 4 `exec codex` call sites in `agent-launcher.sh`:
   - Line 764 (chatgpt login path)
   - Line 826 (custom model + base url)
   - Line 828 (custom model_provider only)
   - Line 830 (default fallback)
2. Keep positional args intact (`-C "$workdir"`, `-c model_provider=...`, `-m MODEL`)
3. The flag should come right after `codex` subcommand as top-level option, before `-C`:
   - Recommended order: `exec codex --dangerously-bypass-approvals-and-sandbox -C "$workdir" [other flags]`
   - (Or keep `-C` first if that's the existing style — either works, just be consistent)

## Tests

1. **wait-for-seat.sh fallback test** (new or extend `test_install_lazy_panes.py`):
   - Scenario: stub tmux with only suffixed session `<proj>-<seat>-claude` alive, stub agentctl returning empty. Pane should fall back to suffix scan within budget and attach (with stderr WARN captured).
   - Scenario: stub agentctl returning canonical `<proj>-<seat>-claude` AND that session exists. Pane should attach directly via primary path, no WARN.
   - Scenario: neither primary resolves nor suffix scan finds anything. Pane should stay waiting, with stderr WARN emitted every M polls.

2. **Codex YOLO flag test** (new `tests/test_launcher_codex_yolo.py` or extend existing launcher test):
   - Grep `agent-launcher.sh` source: verify all 4 codex exec lines include `--dangerously-bypass-approvals-and-sandbox`
   - Smoke: run launcher with `--dry-run` for codex tool and verify flag appears in printed/logged command

3. All previously-passing tests still pass (33 from round 1).

## Deliverable

1. Patches to `wait-for-seat.sh` + `agent-launcher.sh` + new tests
2. Delivery report to `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND2-FALLBACK-AND-YOLO.md`
3. Send summary via `send-and-verify.sh` to `agent-launcher-codex-chatgpt-20260423-230652` for review
4. echo `ROUND2_DONE` when complete

## Constraints

- No need to rerun `bash scripts/install.sh` — install state is mid-Phase-A with user driving
- Don't touch Claude `--dangerously-skip-permissions` flag (it's correct already)
- Don't touch the resolver alias removal (round 1 was correct on that)
- If you disagree with any guardrail, document the objection in DELIVERY and implement the one you believe is correct — I'll adjudicate in review
