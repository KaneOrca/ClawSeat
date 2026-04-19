"""Canonical I/O primitives for ClawSeat state files.

Every ClawSeat state file — bootstrap receipts, session records, TODO /
DELIVERY markdown, WORKSPACE_CONTRACT.toml, PENDING_FRONTSTAGE, current
project pointer — must be written atomically. A crash between "truncated"
and "fully written" would leave a half-file on disk, which downstream
readers then either fail to parse (abort) or, worse, parse as a truncated
dict and silently lose state.

All writes in this module go through ``os.replace`` on a sibling temp
file. On POSIX and Windows ``os.replace`` is atomic: at any instant of
time, a concurrent reader sees either the old full content or the new
full content — never a partial file.

This module must stay zero-dependency (stdlib only). It is imported very
early in the bootstrap path and cannot rely on anything in ``core.*``.
"""
from __future__ import annotations

import os
from pathlib import Path


__all__ = ["atomic_write_text", "ensure_dir", "write_text"]


def ensure_dir(path: Path) -> None:
    """Create ``path`` (incl. parents) if it does not exist yet."""
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    mode: int | None = None,
) -> None:
    """Atomically write ``text`` to ``path``.

    Writes to a sibling temp file first, then ``os.replace`` s it over
    the target. If the process dies between open and replace, callers
    observe the previous contents (or no file at all). They never see a
    truncated or partially written target.

    The parent directory of ``path`` is created if missing.

    ``mode`` (if given) is applied to the temp file *before* the
    replace, so the final file has the requested permissions as soon as
    it becomes visible.
    """
    ensure_dir(path.parent)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding=encoding)
        if mode is not None:
            tmp.chmod(mode)
        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup. Don't mask the original exception.
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


def write_text(path: Path, text: str, mode: int | None = None) -> None:
    """Back-compat convenience wrapper matching the common 3-arg shape.

    Prefer :func:`atomic_write_text` for new code.
    """
    atomic_write_text(path, text, mode=mode)
