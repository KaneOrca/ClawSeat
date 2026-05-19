"""_toml_compat — vendored TOML compatibility shim.

Provides :func:`loads_safe` and :func:`load_safe` that work when neither
``tomllib`` (Python 3.11+) nor ``tomli`` (third-party) is installed. A small
pure-Python fallback is used in that case, covering the scalar, array, section,
and inline-table shapes that ClawSeat runtime scripts read from project/profile
TOML files.

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

import ast
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


def _strip_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if quote:
            if quote == '"' and char == "\\" and not escaped:
                escaped = True
                continue
            if char == quote and not escaped:
                quote = None
            escaped = False
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "#":
            return line[:index]
    return line


def _balanced(value: str) -> bool:
    quote: str | None = None
    escaped = False
    square = 0
    curly = 0
    for char in value:
        if quote:
            if quote == '"' and char == "\\" and not escaped:
                escaped = True
                continue
            if char == quote and not escaped:
                quote = None
            escaped = False
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}":
            curly -= 1
    return quote is None and square == 0 and curly == 0


def _split_top_level(text: str, delimiter: str = ",") -> list[str]:
    parts: list[str] = []
    quote: str | None = None
    escaped = False
    square = 0
    curly = 0
    start = 0
    for index, char in enumerate(text):
        if quote:
            if quote == '"' and char == "\\" and not escaped:
                escaped = True
                continue
            if char == quote and not escaped:
                quote = None
            escaped = False
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}":
            curly -= 1
        elif char == delimiter and square == 0 and curly == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, str):
                return parsed
        except Exception:
            pass
        return value[1:-1]
    return value


def _parse_value(raw: str) -> Any:
    value = raw.strip().rstrip(",").strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return _unquote(value)
    if value == "true":
        return True
    if value == "false":
        return False
    if re.match(r"^-?\d+$", value):
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(item) for item in _split_top_level(inner)]
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        table: dict[str, Any] = {}
        if not inner:
            return table
        for item in _split_top_level(inner):
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.+)$", item)
            if not match:
                continue
            table[match.group(1)] = _parse_value(match.group(2))
        return table
    return value


def _section_dict(root: dict[str, Any], section: str | None) -> dict[str, Any]:
    current = root
    if not section:
        return current
    for part in section.split("."):
        current = current.setdefault(part.strip(), {})
    return current


def _regex_loads(text: str) -> dict[str, Any]:
    """Minimal TOML parser for ClawSeat runtime config fallback.

    It intentionally covers only the TOML shapes ClawSeat reads at runtime:
    strings, integers, booleans, string/scalar arrays, dotted sections, and
    inline tables. It is not a general TOML implementation.
    """
    result: dict[str, Any] = {}
    current_section: str | None = None
    pending_key: str | None = None
    pending_value = ""

    def assign(key: str, raw_value: str) -> None:
        _section_dict(result, current_section)[key] = _parse_value(raw_value)

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line or line.startswith('#'):
            continue
        if pending_key is not None:
            pending_value += " " + line
            if _balanced(pending_value):
                assign(pending_key, pending_value)
                pending_key = None
                pending_value = ""
            continue
        # Section header [section]
        sec_m = re.match(r'^\[([^\[\]]+)\]\s*$', line)
        if sec_m:
            current_section = sec_m.group(1).strip()
            _section_dict(result, current_section)
            continue
        kv_m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.+)$', line)
        if kv_m:
            key, value = kv_m.group(1), kv_m.group(2).strip()
            if _balanced(value):
                assign(key, value)
            else:
                pending_key = key
                pending_value = value
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
