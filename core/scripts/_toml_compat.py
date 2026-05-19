"""_toml_compat — vendored TOML compatibility shim.

Provides :func:`loads_safe` and :func:`load_safe` that work when neither
``tomllib`` (Python 3.11+) nor ``tomli`` (third-party) is installed. A
pure-Python regex fallback is used in that case, covering the simple
``key = "value"`` and ``key = 'value'`` patterns that the ClawSeat vendored
scripts actually read.

Import this module instead of importing ``tomllib`` / ``tomli`` directly so
the desktop Electron runtime does not crash when it ships a Python build
without these packages.

Usage::

    from _toml_compat import loads_safe, load_safe

    data = loads_safe(path.read_text(encoding="utf-8"))
    # or for binary files:
    with path.open("rb") as fh:
        data = load_safe(fh)
"""
from __future__ import annotations

import io
import re
from typing import IO, Any


def _toml_module() -> Any:
    """Return the first available TOML parser module or None."""
    try:
        import tomllib as _m  # type: ignore[import-not-found]
        return _m
    except ModuleNotFoundError:
        pass
    try:
        import tomli as _m  # type: ignore[import-not-found,no-redef]
        return _m
    except ModuleNotFoundError:
        pass
    return None


def _regex_loads(text: str) -> dict[str, Any]:
    """Minimal regex-based TOML parser for simple key = "value" documents.

    Only handles top-level string, integer, and boolean scalar assignments.
    Lists and tables are not supported — callers should only rely on this
    fallback for the specific keys they need (e.g. ``session``, ``engineer``).
    """
    result: dict[str, Any] = {}
    current_section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        # Section header [section]
        sec_m = re.match(r'^\[([^\[\]]+)\]\s*$', line)
        if sec_m:
            current_section = sec_m.group(1).strip()
            if current_section not in result:
                result[current_section] = {}
            continue
        # Key = "value" or key = 'value'
        kv_m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')$', line)
        if kv_m:
            k, v1, v2 = kv_m.group(1), kv_m.group(2), kv_m.group(3)
            v = v1 if v1 is not None else (v2 if v2 is not None else '')
            if current_section is None:
                result[k] = v
            else:
                result[current_section][k] = v  # type: ignore[index]
            continue
        # Key = integer
        int_m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(-?\d+)$', line)
        if int_m:
            k, v_int = int_m.group(1), int(int_m.group(2))
            if current_section is None:
                result[k] = v_int
            else:
                result[current_section][k] = v_int  # type: ignore[index]
            continue
        # Key = boolean
        bool_m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(true|false)$', line)
        if bool_m:
            k, v_bool = bool_m.group(1), bool_m.group(2) == 'true'
            if current_section is None:
                result[k] = v_bool
            else:
                result[current_section][k] = v_bool  # type: ignore[index]
    return result


def loads_safe(text: str) -> dict[str, Any]:
    """Parse a TOML string, falling back to a regex parser when tomllib/tomli unavailable."""
    mod = _toml_module()
    if mod is not None:
        try:
            return mod.loads(text)  # type: ignore[no-any-return]
        except Exception:
            return {}
    return _regex_loads(text)


def load_safe(fh: IO[bytes]) -> dict[str, Any]:
    """Parse a binary TOML file-like object, with fallback."""
    mod = _toml_module()
    if mod is not None:
        try:
            return mod.load(fh)  # type: ignore[no-any-return]
        except Exception:
            return {}
    try:
        text = fh.read().decode('utf-8', errors='replace')
    except Exception:
        return {}
    return _regex_loads(text)
