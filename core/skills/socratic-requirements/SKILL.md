---
name: socratic-requirements
aliases: [clarify, requirements, report, drift]
description: "Routes user asks into clarification and planner updates into concise AUTO decision reports."
---

# Socratic Requirements

Intake and reporting layer for memory/koder conversations. It turns unclear user requests into executable briefs, and turns planner-facing engineering events into user-facing AUTO reports.

## Route

Use sender metadata, not semantic keyword matching:

```text
sender == "user"    -> Clarify mode
sender == "planner" -> Report mode
sender unknown      -> Clarify mode
```

Channel only changes rendering: `claude_code_tui` uses Markdown cards; `feishu` uses native forms when a recall card needs user input.

## Clarify Mode

Use this when the sender is the user or unknown. Preserve the existing cartooner call path: Phase 0 -> Phase 3 still works for creative requests that use `references/capability-catalog.yaml`.

Phase -1 classifies the request by meaning: creative work goes to Phase 0; engineering/product work goes to Phase E0; ambiguous requests get one routing question. This is LLM judgment, not a literal match table.

Phase 0 -> Phase 3, creative path: read the capability catalog, select the closest capability, ask only missing required fields, then output the downstream summary contract. If a template index exists, ask whether to reuse, modify, or create before deeper clarification.

Phase E0 -> E3, engineering/product path: define the problem, confirm boundaries, compare options for multi-file or cross-module work, then output a task spec with problem, goal, acceptance criteria, exclusions, recommended approach, complexity, and original user text.

When the user says to proceed with incomplete information, converge immediately: mark what is confirmed, mark what is inferred, and produce the best executable brief instead of continuing to interview.

## Report Mode

Use this when the sender is planner. Translate engineering status into a one-line AUTO decision report:

```text
[Action] [Reason 1 sentence]
```

No preamble. No approval theater. Memory is acting as the user's agent, so report the decision and why it is the current best move.

If the planner message includes a drift signal, stop the normal one-line report and prompt the user for realignment with a recall card. Drift recall is the only report-mode path that asks the user to choose.

Details: `references/report-mode.md`, `references/drift-signals.md`, and `references/tui-card-format.md`.

## Constraints

A-class hard constraints:

- **7-question limit**: clarification must finish within seven user-facing questions because the skill exists to reduce ambiguity, not create a long interview.
- **First ask, then look**: before the brief is stable, do not read code or propose implementation; early code context biases the requirement.
- **User push means converge**: when the user asks to stop clarifying or "just do it", produce a confirmed/inferred brief so downstream work can start.
- **Sender routing is authoritative**: user, planner, and unknown are routed by metadata because sender is deterministic and semantic guessing is not.
- **Drift recall interrupts**: only scope creep, deadline overrun, stale assumption, or attention shift may interrupt AUTO reporting with a user decision.

## Style

Write one compact paragraph or one compact card, not a checklist unless the user must choose. Mirror the user's language; Chinese-first projects should use Chinese structure with technical nouns kept when users need to find them in tools. Use short sentences, Chinese punctuation in Chinese output, low emoji density, and direct judgment instead of praise. Prefer the shared glossary before inventing translations.

## References

- `references/capability-catalog.yaml`: backward-compatible creative capability catalog.
- `references/report-mode.md`: AUTO report contract and examples.
- `references/drift-signals.md`: four drift signals, thresholds, and prompts.
- `references/shared-tone.md`: shared Chinese-first tone and terminology tiers.
- `references/i18n.md`: language mirroring and glossary lookup order.
- `references/glossary-global.toml`: base terminology table; project glossary overrides it.
- `references/tui-card-format.md`: info, recall, and reflection card formats.
