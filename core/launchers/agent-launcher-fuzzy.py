#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.lib.real_home import real_user_home


def _home() -> Path:
    return Path(os.environ.get("REAL_HOME", str(real_user_home()))).expanduser()


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
        str(home / "coding"),
        str(home / "projects"),
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


def resolve_manual_path(query: str) -> Optional[str]:
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


def print_best_match(candidates: list[str], query: str, limit: int, mode: str, default_choice: str) -> int:
    matches = get_matches(candidates, query, limit, mode, default_choice)
    if not matches:
        return 1
    print(matches[0])
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Deterministic launcher matcher.")
    parser.add_argument("--mode", choices=["directories", "choices"], default="directories")
    parser.add_argument("--query", default="", help="Initial query")
    parser.add_argument("--dump", action="store_true", help="Print all matches and exit")
    parser.add_argument("--limit", type=int, default=12, help="Maximum visible results")
    parser.add_argument("--prompt", default="", help="Ignored compatibility flag")
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
    return print_best_match(candidates, args.query, args.limit, args.mode, args.default_choice)


if __name__ == "__main__":
    raise SystemExit(main())
