"""Shared helpers for ClawSeat brief acceptance criteria.

The queue layer needs a cheap readiness gate before waking or claiming a brief,
and the acceptance executor needs to avoid treating reviewer/operator prose as a
shell command. This module keeps those two checks aligned.
"""

from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


_PLACEHOLDER_RE = re.compile(
    r"^\s*(TODO\b|TBD\b|FIXME\b|<待|待\s|replace\s+with\b)",
    re.IGNORECASE,
)

# cf015: non-portable pipe-negation — `| ! cmd` is not valid POSIX sh or bash
# syntax when used as a pipeline segment. `| ! rg X` should be `| rg -v X`.
_PIPE_NEGATION_RE = re.compile(r"\|\s*!")

# cf015: bare `git diff --name-only` without an explicit range (base..head or
# base...head). Without a range this scans uncommitted working-tree state and
# produces false positives on dirty branches.
# A safe form must contain `..` between two refs on the same logical command
# token, e.g. `origin/main..HEAD` or `origin/main...HEAD`.
_BARE_GIT_DIFF_NAME_ONLY_RE = re.compile(
    r"\bgit\s+diff\b(?:[^|;&\n])*?--name-only"
)
_GIT_DIFF_RANGE_RE = re.compile(r"\.\.")

_SHELL_BUILTINS = {
    "!",
    ".",
    ":",
    "[",
    "[[",
    "cd",
    "echo",
    "eval",
    "exec",
    "exit",
    "export",
    "false",
    "printf",
    "pwd",
    "read",
    "set",
    "source",
    "test",
    "time",
    "true",
    "unset",
}


def load_brief_frontmatter(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        end = text.find("\n---", 4)
    if end == -1:
        raise ValueError(f"{path}: unterminated frontmatter")
    data = yaml.safe_load(text[4:end])
    if not isinstance(data, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return data


def load_brief_frontmatter_text(brief_text: str, source_name: str = "<brief>") -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required")
    if not brief_text.startswith("---\n"):
        raise ValueError(f"{source_name}: missing YAML frontmatter")
    end = brief_text.find("\n---\n", 4)
    if end == -1:
        end = brief_text.find("\n---", 4)
    if end == -1:
        raise ValueError(f"{source_name}: unterminated frontmatter")
    data = yaml.safe_load(brief_text[4:end])
    if not isinstance(data, dict):
        raise ValueError(f"{source_name}: frontmatter is not a mapping")
    return data


def is_placeholder_text(value: Any) -> bool:
    return bool(_PLACEHOLDER_RE.search(str(value or "").strip()))


def criterion_command_and_text(criterion: Any) -> tuple[str, str]:
    """Normalize one acceptance criterion to display text and shell command.

    A mapping with an explicit `command` is the only structured form that
    contributes a shell command. A mapping with only `criterion` is narrative
    text and should not be executed as shell.
    """
    if isinstance(criterion, str):
        value = criterion.strip()
        return value, value
    if isinstance(criterion, dict):
        command = str(criterion.get("command") or "").strip()
        text = str(
            criterion.get("description")
            or criterion.get("criterion")
            or command
        ).strip()
        return text, command
    raise ValueError(f"unrecognized criterion shape: {criterion!r}")


def is_shell_runnable_command(command: str) -> bool:
    command = str(command or "").strip()
    if not command or is_placeholder_text(command):
        return False
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    if not tokens:
        return False

    idx = 0
    while idx < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", tokens[idx]):
        idx += 1
    if idx >= len(tokens):
        return False

    executable = tokens[idx]
    if executable in _SHELL_BUILTINS:
        return True
    if executable.startswith(("./", "../", "/")):
        return True
    return shutil.which(executable) is not None


def criterion_is_shell_runnable(criterion: Any) -> bool:
    _, command = criterion_command_and_text(criterion)
    return is_shell_runnable_command(command)


def has_invalid_pipe_negation(command: str) -> bool:
    """Return True if command contains a non-portable `| !` pipe-negation segment.

    `| ! cmd` is invalid in POSIX sh and bash when used as a pipeline segment.
    The portable equivalent is `| cmd -v` (rg/grep invert-match flag).
    """
    return bool(_PIPE_NEGATION_RE.search(command or ""))


def normalize_pipe_negation(command: str) -> str:
    """Replace non-portable `| ! rg X` / `| ! grep X` with portable invert-match form.

    Transforms `| ! rg` → `| rg -v` and `| ! grep` → `| grep -v`.
    Other `| !` forms are left intact (they will still fail at execution).
    """
    # Replace `| ! rg` → `| rg -v`
    command = re.sub(r"\|\s*!\s*rg\b", "| rg -v", command)
    # Replace `| ! grep` → `| grep -v`
    command = re.sub(r"\|\s*!\s*grep\b", "| grep -v", command)
    return command


def has_bare_git_diff_name_only(command: str) -> bool:
    """Return True if command uses `git diff --name-only` without an explicit range.

    A bare `git diff --name-only` (no base..head range) compares the working
    tree against the index, picking up unrelated dirty-worktree state. Safe
    forms must include a `..` or `...` range, e.g. `origin/main...HEAD`.
    """
    for segment in re.split(r"[|;&]", command or ""):
        m = _BARE_GIT_DIFF_NAME_ONLY_RE.search(segment)
        if m and not _GIT_DIFF_RANGE_RE.search(segment):
            return True
    return False


# cf017: canonical portable scope-guard command for forbidden-file checks.
# Memory/planner should use this template (with FORBIDDEN_PATHS substituted) when
# generating the "no forbidden files touched" mechanical acceptance criterion.
# It uses an explicit base..head range (not a bare working-tree diff) and Python
# filtering (not shell pipe-negation), so it is POSIX-portable and shell-safe.
SCOPE_GUARD_PORTABLE_TEMPLATE = (
    "cd {repo_root} && "
    "git diff --name-only origin/main...HEAD | "
    r'python3 -c "import sys; bad=[p.strip() for p in sys.stdin if p.strip() and'
    r' any(p.strip().endswith(f) or (k in p.strip()) for f,k in'
    r" {forbidden_spec})];"
    r' print(\"\n\".join(bad)); raise SystemExit(1 if bad else 0)"'
)


def brief_acceptance_ready(brief: dict[str, Any]) -> tuple[bool, str]:
    acceptance = brief.get("acceptance_criteria")
    if not isinstance(acceptance, dict):
        return False, "brief.acceptance_criteria missing"

    mechanical = acceptance.get("mechanical")
    if not isinstance(mechanical, list) or not mechanical:
        return False, "brief.acceptance_criteria.mechanical empty"

    for route in ("mechanical", "reviewer", "operator"):
        items = acceptance.get(route) or []
        if not isinstance(items, list):
            return False, f"brief.acceptance_criteria.{route} must be a list"
        for item in items:
            try:
                text, command = criterion_command_and_text(item)
            except ValueError as exc:
                return False, str(exc)
            if is_placeholder_text(text) or is_placeholder_text(command):
                return False, f"brief.acceptance_criteria.{route} contains placeholder text"

    if not any(criterion_is_shell_runnable(item) for item in mechanical):
        return False, "brief.acceptance_criteria.mechanical has no shell-runnable command"

    # cf015: reject non-portable pipe-negation and bare git diff --name-only
    for item in mechanical:
        try:
            _, command = criterion_command_and_text(item)
        except ValueError:
            continue
        if not command:
            continue
        if has_invalid_pipe_negation(command):
            return False, (
                "brief.acceptance_criteria.mechanical contains non-portable pipe-negation "
                f"('| !'): {command!r}. Use '| rg -v' or '| grep -v' instead."
            )
        if has_bare_git_diff_name_only(command):
            return False, (
                "brief.acceptance_criteria.mechanical contains bare 'git diff --name-only' "
                f"without an explicit range: {command!r}. "
                "Use an explicit base..head range, e.g. 'git diff origin/main...HEAD --name-only'."
            )

    return True, "ok"
