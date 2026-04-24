# Workflows

This directory contains workflow definition files created by `cs-workflow` DESIGN mode.

Each file follows the format defined in `core/skills/cs-workflow/SKILL.md`.

## Naming convention

`<workflow_name>.md` — workflow definition  
`<workflow_name>-design_log.md` — design decision log

## Usage

**Design a new workflow** (via cs-workflow DESIGN mode):
```
Dispatch creative-planner with cs-workflow skill, mode=DESIGN,
user_brief=<brief>, workflow_name=<name>
```

**Execute an existing workflow** (via cs-workflow EXECUTE mode):
```
Dispatch creative-planner with cs-workflow skill, mode=EXECUTE,
workflow_name=<name>, project_params={brief_path: ..., output_dir: ...}
```
