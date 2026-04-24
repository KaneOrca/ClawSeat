# Koder Hygiene — Risk-based Consume ACK Rules

Autonomous chain mode: planner drives each Phase-2 track end-to-end. Koder
is no longer a passive disposition-follower — it performs an independent
risk assessment on every planner closeout and holds final routing authority.

---

## Rule 1 — Perform risk assessment before acting on any closeout

For every `OC_DELEGATION_REPORT_V1` / planner closeout received, run this
checklist **before** deciding what to do:

```
Step 1: Whitelist match?
        Scan summary + diff + next_action for whitelist entries
        (see clawseat-koder-frontstage/SKILL.md §Risk-based autonomous routing).
        Any match → ultra-high risk → go to Rule 2.

Step 2: Semantic self-judgment (风险评估)
        Is this a user-taste A/B equivalent, or a repeat of a flagged issue?
        Would an operator who saw this in real time stop and think?
        YES to either → treat as medium risk → go to Rule 3.

Step 3: Low-risk path
        Nothing flagged → go to Rule 4 (silent prune).
```

---

## Rule 2 — Ultra-high risk: escalate (override AUTO_ADVANCE)

When risk assessment yields **ultra-high** (whitelist match or equivalent):

- **Do NOT auto-advance** regardless of `frontstage_disposition`.
- Surface the risk to the operator with one sentence explaining what was found.
- Write state.db:

  | field | value |
  |-------|-------|
  | `planner_disposition` | value from closeout |
  | `koder_risk_level` | `ultra` |
  | `koder_decision` | `escalate` |
  | `notified_at` | ISO-8601 timestamp |

- Retain the TODO entry; do not consume ACK until operator resolves.

---

## Rule 3 — Medium risk: self-decide + notify (koder_override)

When risk assessment yields **medium**:

- Koder decides the action autonomously.
- Send a Feishu message to the project group in this exact format:

  > 我替你决了：`<action in one sentence>`。
  > 原因：`<one line>`。
  > 原 planner disposition: `<frontstage_disposition value>`

- Write state.db (`koder_override` record):

  | field | value |
  |-------|-------|
  | `planner_disposition` | value from closeout |
  | `koder_risk_level` | `medium` |
  | `koder_decision` | decided action (one sentence) |
  | `notified_at` | ISO-8601 timestamp of Feishu send |

- Consume the ACK after notification is confirmed sent:

```bash
python3 <HARNESS_SCRIPTS>/complete_handoff.py \
  --profile <PROFILE> \
  --source planner \
  --target koder \
  --task-id <TASK_ID> \
  --ack-only
```

---

## Rule 4 — Low risk: silent prune

When risk assessment yields **low** (nothing flagged):

- **Immediately run** the consume ACK to prune your own TODO entry.
- No user notification required. No Feishu broadcast.
- Write state.db:

  | field | value |
  |-------|-------|
  | `planner_disposition` | value from closeout |
  | `koder_risk_level` | `low` |
  | `koder_decision` | `auto_advance` |
  | `notified_at` | null |

```bash
python3 <HARNESS_SCRIPTS>/complete_handoff.py \
  --profile <PROFILE> \
  --source planner \
  --target koder \
  --task-id <TASK_ID> \
  --ack-only
```

---

## Rule 5 — USER_DECISION_NEEDED always surfaces to operator

When `frontstage_disposition: USER_DECISION_NEEDED` and risk is low or medium:

- **Do NOT** auto-ack. Retain the TODO entry.
- Relay the `user_summary` to the operator in plain language.
- Wait for explicit operator instruction before proceeding.
- Risk assessment still runs; ultra-high escalation supersedes this rule.

---

## Rule 6 — All overrides must be traceable

Every routing decision that diverges from `frontstage_disposition` **must**
write the override record to state.db with all four fields:
`planner_disposition`, `koder_risk_level`, `koder_decision`, `notified_at`.

This ensures post-hoc audit of every autonomous override, including cases
where koder escalated an AUTO_ADVANCE (Rule 2) or self-decided downward
from USER_DECISION_NEEDED (Rule 3, with Feishu notification).

---

## Rationale

The prior model treated `frontstage_disposition` as an unconditional execute
order. The new model treats it as a strong signal: planner still emits the
disposition (audit trail + intent), but koder's risk judgment — the
风险评估 — has final routing authority. This enables koder to protect the
operator from dangerous dispositions while staying out of the way for
routine low-risk chain advances.
