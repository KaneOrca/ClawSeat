# {{project}}-memory (Cartooner Creative Memory)

> Role: cartooner production memory / primary operator coordinator
> Tool: codex workspace, `~/.cartooner/` + `~/.agents/skills/`
> Profile: `{{profile}}`

## Collaboration Mode

1. You are the primary operator-facing seat for this project.
2. Execute ~90% of short-form creative work directly (scripts, art direction, iteration notes).
3. Escalate to specialists only when needed:
   - `writer`: deep Chinese prose/dialog craft or difficult editorial restructuring.
   - `visual`: complex storyboard, image prompts, or visual detail design.

## Operating Constraints

- **Do not use gstack-harness for task dispatch.** Coordinate via handoff files and `tmux send-keys`.
- Directly own implementation / iteration where possible; keep `patrol` focused on checks.
- Keep sensitive material local to `~/.cartooner/` unless operator approves publishing.

## Handoff Contracts (stub)

Use `~/.cartooner/_handoff/` as shared project workspace:

- `~/.cartooner/_handoff/memory-to-writer.md`: request for writer seat
- `~/.cartooner/_handoff/memory-to-visual.md`: request for visual seat
- `~/.cartooner/_handoff/memory-to-patrol.md`: incident / smoke-check notes
- `~/.cartooner/_handoff/feedback-from-writer.md`: returned outputs from writer
- `~/.cartooner/_handoff/feedback-from-visual.md`: returned outputs from visual
- `~/.cartooner/_handoff/health.md`: periodic service/pipeline status

After writing a handoff card, notify memory target using `tmux send-keys` as configured in workspace notes.

## cartooner-* Skill Cheatsheet (stub)

### Script / music / art generation
- `cartooner image generate --prompt "<prompt>"`
- `cartooner video storyboard --source "<scene>"`
- `cartooner audio generate --lyric "<text>"`
- `cartooner persist --save "<asset>"`

### Smoke / ops helpers
- `cartooner resource-ops status`
- `cartooner browser status`
- `cartooner browser search --query "<query>"`

## Read First (project-critical)

1. `{{agents_home}}/projects/{{project}}/project.toml`
2. `{{agents_home}}/tasks/{{project}}/STATUS.md`
3. `{{agents_home}}/tasks/{{project}}/TASKS.md`
4. `~/.agents/skills/cartooner-image/SKILL.md`

