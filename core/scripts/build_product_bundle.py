#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
MANIFEST_PATH = REPO_ROOT / "manifest.toml"
DEFAULT_OUTPUT = Path("/tmp/clawseat-product-bundle")
EXCLUDE_DIR_NAMES = {".git", ".tasks", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a publishable single-repo ClawSeat product bundle."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Target directory for the exported bundle. Defaults to /tmp/clawseat-product-bundle.",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also export manifest optional modules such as consumer adapters and extra docs.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the output directory before building.",
    )
    return parser.parse_args()


def load_manifest() -> dict:
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)


def selected_entries(manifest: dict, *, include_optional: bool) -> list[Path]:
    modules = manifest.get("modules", {})
    ordered_sections = ["root", "core", "adapters", "shells", "profiles", "docs"]
    if include_optional:
        ordered_sections.append("optional")

    seen: set[Path] = set()
    entries: list[Path] = []
    for section in ordered_sections:
        for raw in modules.get(section, []):
            path = REPO_ROOT / raw
            if path in seen:
                continue
            seen.add(path)
            entries.append(path)
    return entries


def should_skip(path: Path) -> bool:
    if path.name in EXCLUDE_DIR_NAMES:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def ignore_filtered(_dir: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        candidate = Path(name)
        if should_skip(candidate):
            ignored.add(name)
    return ignored


def copy_entry(source: Path, destination_root: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"manifest entry not found: {source}")

    relative = source.relative_to(REPO_ROOT)
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=ignore_filtered,
        )
        return

    if should_skip(source):
        return
    shutil.copy2(source, destination)


def build_bundle(output_root: Path, *, include_optional: bool, clean: bool) -> list[Path]:
    manifest = load_manifest()
    entries = selected_entries(manifest, include_optional=include_optional)

    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for entry in entries:
        copy_entry(entry, output_root)
        copied.append(entry.relative_to(REPO_ROOT))
    return copied


def main() -> int:
    args = parse_args()
    output_root = Path(args.output).expanduser().resolve()
    copied = build_bundle(
        output_root,
        include_optional=args.include_optional,
        clean=args.clean,
    )

    print(f"bundle_root: {output_root}")
    print(f"entries: {len(copied)}")
    for entry in copied:
        print(f"  - {entry}")
    if args.include_optional:
        print("mode: complete_plus_optional")
    else:
        print("mode: complete_minimal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
