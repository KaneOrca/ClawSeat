#!/usr/bin/env python3

import argparse
import curses
import os
import sys
from pathlib import Path


def _home() -> Path:
    return Path(
        os.environ.get("REAL_HOME", os.environ.get("HOME", str(Path.home())))
    ).expanduser()


def _roots_from_env_or_defaults() -> list[tuple[Path, int]]:
    """Parse `CLAWSEAT_LAUNCHER_ROOTS=PATH:weight,PATH:weight,...` or fall back."""
    raw = os.environ.get("CLAWSEAT_LAUNCHER_ROOTS", "")
    if raw.strip():
        specs: list[tuple[Path, int]] = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ":" in chunk:
                p, _, w = chunk.rpartition(":")
                try:
                    specs.append((Path(p).expanduser(), int(w)))
                    continue
                except ValueError:
                    pass
            specs.append((Path(chunk).expanduser(), 3))
        if specs:
            return specs
    home = _home()
    return [
        (home / "coding", 5),
        (home / "Desktop" / "work", 4),
        (home / "Desktop", 3),
        (home / "Documents", 3),
    ]


def _favorites_from_env_or_defaults() -> list[str]:
    raw = os.environ.get("CLAWSEAT_LAUNCHER_FAVORITES", "")
    if raw.strip():
        return [p.strip() for p in raw.split(",") if p.strip()]
    home = _home()
    return [
        str(home / "coding" / "cartooner"),
        str(home / "coding" / "openclaw"),
        str(home / "Desktop" / "work"),
        str(home / "Desktop"),
        str(home / "Documents"),
        str(home),
    ]


ROOT_SPECS = _roots_from_env_or_defaults()
FAVORITES = _favorites_from_env_or_defaults()

IGNORED = {
    ".git",
    ".agent",
    ".trae",
    "node_modules",
    ".pnpm-store",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".codex",
    ".agents",
    ".claude_runtime",
    ".openclaw-config",
    ".backups",
    ".worktrees",
    "Library",
    ".Trash",
    "backup",
    "ClawSeat.bak",
}


def collect_candidates() -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []

    def add_path(path: Path) -> None:
        try:
            resolved = str(path.resolve())
        except OSError:
            return
        if resolved not in seen and Path(resolved).is_dir():
            seen.add(resolved)
            candidates.append(resolved)

    add_path(_home())
    for favorite in FAVORITES:
        add_path(Path(favorite))

    for root, max_depth in ROOT_SPECS:
        if not root.exists():
            continue
        add_path(root)
        for current_root, dirnames, _ in os.walk(root):
            current = Path(current_root)
            try:
                rel = current.relative_to(root)
                depth = len(rel.parts)
            except ValueError:
                depth = 0
            dirnames[:] = [d for d in dirnames if d not in IGNORED]
            if depth >= max_depth:
                dirnames[:] = []
            add_path(current)

    return candidates


def subsequence_metrics(text: str, query: str):
    positions = []
    start = 0
    for char in query:
        pos = text.find(char, start)
        if pos == -1:
            return None
        positions.append(pos)
        start = pos + 1
    span = positions[-1] - positions[0] + 1
    gap = span - len(query)
    return gap, positions[0]


def score_empty(path: str):
    favorite_index = {value: idx for idx, value in enumerate(FAVORITES)}
    depth = path.count(os.sep)
    if path in favorite_index:
        return (0, favorite_index[path], depth, len(path), path.lower())
    return (1, depth, len(path), path.lower())


def score_choice_empty(choice: str, default_choice: str):
    lowered = choice.lower()
    default_lowered = default_choice.lower()
    preferred = 0 if lowered == default_lowered else 1
    return (preferred, len(choice), lowered)


def resolve_manual_path(query: str) -> str | None:
    if not query:
        return None
    expanded = Path(query).expanduser()
    if expanded.is_dir():
        try:
            return str(expanded.resolve())
        except OSError:
            return str(expanded)
    return None


def score_query(path: str, query: str):
    lowered_query = query.lower()
    lowered_path = path.lower()
    name = os.path.basename(lowered_path)
    depth = path.count(os.sep)
    path_query = "/" in query or query.startswith("~")

    if name == lowered_query:
        return (0, 0, 0, depth, len(name), lowered_path)
    if name.startswith(lowered_query):
        return (1, 0, 0, depth, len(name), lowered_path)
    if lowered_query in name:
        return (2, name.index(lowered_query), 0, depth, len(name), lowered_path)

    name_subseq = subsequence_metrics(name, lowered_query)
    if name_subseq is not None:
        gap, start = name_subseq
        return (3, gap, start, depth, len(name), lowered_path)

    if path_query and lowered_query in lowered_path:
        return (4, lowered_path.index(lowered_query), 0, depth, len(name), lowered_path)

    path_subseq = subsequence_metrics(lowered_path, lowered_query) if path_query else None
    if path_subseq is not None:
        gap, start = path_subseq
        return (5, gap, start, depth, len(name), lowered_path)

    return None


def score_choice_query(choice: str, query: str):
    lowered_query = query.lower()
    lowered_choice = choice.lower()
    if lowered_choice == lowered_query:
        return (0, 0, len(choice), lowered_choice)
    if lowered_choice.startswith(lowered_query):
        return (1, 0, len(choice), lowered_choice)
    if lowered_query in lowered_choice:
        return (2, lowered_choice.index(lowered_query), len(choice), lowered_choice)
    choice_subseq = subsequence_metrics(lowered_choice, lowered_query)
    if choice_subseq is not None:
        gap, start = choice_subseq
        return (3, gap, start, len(choice), lowered_choice)
    return None


def get_directory_matches(candidates: list[str], query: str, limit: int) -> list[str]:
    query = query.strip()
    if not query:
        return sorted(candidates, key=score_empty)[:limit]

    manual = resolve_manual_path(query)
    scored = []
    if manual is not None:
        scored.append(((0, -1, -1, 0, len(manual), manual.lower()), manual))

    seen = {manual} if manual else set()
    for candidate in candidates:
        if candidate in seen:
            continue
        score = score_query(candidate, query)
        if score is not None:
            scored.append((score, candidate))
    scored.sort(key=lambda item: item[0])
    return [candidate for _, candidate in scored[:limit]]


def get_choice_matches(candidates: list[str], query: str, limit: int, default_choice: str) -> list[str]:
    query = query.strip()
    if not query:
        return sorted(candidates, key=lambda item: score_choice_empty(item, default_choice))[:limit]

    scored = []
    for candidate in candidates:
        score = score_choice_query(candidate, query)
        if score is not None:
            scored.append((score, candidate))
    scored.sort(key=lambda item: item[0])
    return [candidate for _, candidate in scored[:limit]]


def get_matches(candidates: list[str], query: str, limit: int, mode: str, default_choice: str) -> list[str]:
    if mode == "choices":
        return get_choice_matches(candidates, query, limit, default_choice)
    return get_directory_matches(candidates, query, limit)


def dump_matches(candidates: list[str], query: str, limit: int, mode: str, default_choice: str) -> int:
    for candidate in get_matches(candidates, query, limit, mode, default_choice):
        print(candidate)
    return 0


def load_choices(path: str) -> list[str]:
    loaded = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.rstrip("\n")
            if value:
                loaded.append(value)
    return loaded


def run_curses_picker(
    candidates: list[str],
    initial_query: str,
    limit: int,
    mode: str,
    prompt: str,
    default_choice: str,
) -> int:
    selection_holder = {"path": None}

    def main(stdscr):
        query = initial_query
        selected_index = 0
        scroll_offset = 0

        curses.curs_set(1)
        stdscr.keypad(True)
        curses.use_default_colors()

        if default_choice and not query:
            try:
                selected_index = candidates.index(default_choice)
            except ValueError:
                selected_index = 0

        while True:
            height, width = stdscr.getmaxyx()
            result_limit = max(8, min(limit, height - 7))
            matches = get_matches(candidates, query, result_limit, mode, default_choice)
            if matches:
                selected_index = max(0, min(selected_index, len(matches) - 1))
            else:
                selected_index = 0
            if selected_index < scroll_offset:
                scroll_offset = selected_index
            if selected_index >= scroll_offset + max(1, height - 6):
                scroll_offset = selected_index - (height - 6) + 1

            stdscr.erase()
            title = "Directory Picker (fzf-like)" if mode == "directories" else "Option Picker (fzf-like)"
            stdscr.addnstr(0, 0, title, width - 1, curses.A_BOLD)
            stdscr.addnstr(
                1,
                0,
                prompt or "Type to filter. Enter confirm. Up/Down select. Ctrl-U clear. Esc cancel.",
                width - 1,
            )
            stdscr.addnstr(2, 0, f"Query: {query}", width - 1)

            visible_rows = max(1, height - 6)
            if not matches:
                empty_text = (
                    "No matches. Try another keyword or paste an absolute path."
                    if mode == "directories"
                    else "No matches. Keep typing to narrow the choices."
                )
                stdscr.addnstr(4, 0, empty_text, width - 1)
            else:
                visible = matches[scroll_offset : scroll_offset + visible_rows]
                for idx, candidate in enumerate(visible, start=0):
                    row = 4 + idx
                    actual_index = scroll_offset + idx
                    prefix = "> " if actual_index == selected_index else "  "
                    text = f"{prefix}{candidate}"
                    attrs = curses.A_REVERSE if actual_index == selected_index else curses.A_NORMAL
                    stdscr.addnstr(row, 0, text, width - 1, attrs)

                current = matches[selected_index]
                footer = f"Selected: {current}"
                stdscr.addnstr(height - 1, 0, footer, width - 1, curses.A_DIM)

            cursor_x = min(width - 1, len("Query: ") + len(query))
            stdscr.move(2, cursor_x)
            stdscr.refresh()

            key = stdscr.get_wch()
            if key in ("\n", "\r", curses.KEY_ENTER):
                if matches:
                    selection_holder["path"] = matches[selected_index]
                    return
                continue
            if key in ("\x1b",):
                raise KeyboardInterrupt
            if key in (curses.KEY_UP,):
                if matches:
                    selected_index = max(0, selected_index - 1)
                continue
            if key in (curses.KEY_DOWN,):
                if matches:
                    selected_index = min(len(matches) - 1, selected_index + 1)
                continue
            if key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                query = query[:-1]
                selected_index = 0
                scroll_offset = 0
                continue
            if key == "\x15":
                query = ""
                selected_index = 0
                scroll_offset = 0
                continue
            if isinstance(key, str) and key.isprintable():
                query += key
                selected_index = 0
                scroll_offset = 0
                continue

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        return 130

    if selection_holder["path"]:
        print(selection_holder["path"])
        return 0
    return 130


def parse_args():
    parser = argparse.ArgumentParser(description="Interactive fzf-like picker.")
    parser.add_argument("--mode", choices=["directories", "choices"], default="directories")
    parser.add_argument("--query", default="", help="Initial query")
    parser.add_argument("--dump", action="store_true", help="Print matches and exit")
    parser.add_argument("--limit", type=int, default=12, help="Maximum visible results")
    parser.add_argument("--prompt", default="", help="Prompt shown above the search box")
    parser.add_argument("--default-choice", default="", help="Preferred selection when query is empty")
    parser.add_argument("--choices-file", default="", help="Newline-delimited options file for choice mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "choices":
        if not args.choices_file:
            raise SystemExit("choice mode requires --choices-file")
        candidates = load_choices(args.choices_file)
    else:
        candidates = collect_candidates()
    if args.dump:
        return dump_matches(candidates, args.query, args.limit, args.mode, args.default_choice)
    return run_curses_picker(
        candidates,
        args.query,
        args.limit,
        args.mode,
        args.prompt,
        args.default_choice,
    )


if __name__ == "__main__":
    raise SystemExit(main())
