# Claude Code Install Driver

This page adapts the generic [Install Agent Prompt](../../INSTALL_AGENT_PROMPT.md)
to Claude Code tool behavior.

## Voice & Tone

Use the same voice contract as the generic prompt: concise, explicit, and
recommendation-driven. Keep `/en`, `/zh`, empty Enter defaults, `详`, and
Recommended★ prompts available throughout the session.

## Confirmation Pattern

Use Claude Code tools in this order:

1. **Read** `docs/INSTALL.md`, `docs/INSTALL_AGENT_PROMPT.md`, and the relevant
   install scripts before changing behavior.
2. **Bash** Step 0 detection with `bash scripts/install.sh --detect-only`.
3. **AskUserQuestion** for each confirmation. Use the rich UI instead of plain
   markdown when asking language, template, project name, summary, run, or
   failure-choice questions.
4. **Bash run_in_background** for the long `install.sh` run so narration and
   monitoring can continue.
5. **Monitor** the background command and summarize each state transition.
6. **TaskCreate** the 11-step progress checklist before the run starts.

Confirmation lines keep this shape:

```text
Recommended★: <choice>
Reason: <one sentence>
Confirm: [Enter=default / change / 详 / cancel]
```

AskUserQuestion reference JSON:

```json
{
  "question": "Choose the ClawSeat template.",
  "header": "Template",
  "options": [
    {"label": "Creative (Recommended)", "description": "Best first install default."},
    {"label": "Engineering", "description": "Adds reviewer for code review lanes."},
    {"label": "Solo", "description": "Minimal 3-seat all-OAuth setup."}
  ]
}
```

## Failure Pattern

When a Bash or Monitor step fails, classify the failure, then offer two or
three concrete fixes. Never kill unrelated tmux or iTerm sessions. If PTY
resources are exhausted, stop and escalate using the project protocol.

## detect_all JSON Reference

Read Step 0 output as JSON and keep it available for later decisions:
OAuth state, PTY state, branch state, existing projects, and timestamp.
