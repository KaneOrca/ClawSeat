"""Regression: clawseat-engineering and clawseat-creative templates load correctly.

Verifies that the templates introduced in FEAT-HARNESS-TEMPLATES are syntactically
valid TOML, have the expected seat count, and that each seat has the required fields
(id, role, tool, auth_mode).
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

_REPO = Path(__file__).resolve().parents[1]
_TEMPLATES = _REPO / "templates"


def _load(name: str) -> dict:
    path = _TEMPLATES / f"{name}.toml"
    assert path.exists(), f"template not found: {path}"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _validate_seats(data: dict) -> list[dict]:
    engineers = data.get("engineers", [])
    assert engineers, "template has no engineers"
    for eng in engineers:
        for field in ("id", "role", "tool", "auth_mode"):
            assert field in eng, f"seat {eng.get('id', '?')} missing field: {field}"
    return engineers


def test_clawseat_engineering_loads_with_six_seats() -> None:
    data = _load("clawseat-engineering")
    seats = _validate_seats(data)
    assert len(seats) == 6, f"expected 6 seats, got {len(seats)}: {[s['id'] for s in seats]}"
    seat_ids = [s["id"] for s in seats]
    assert "ancestor" in seat_ids
    assert "planner" in seat_ids
    assert "builder" in seat_ids
    assert "reviewer" in seat_ids
    assert "qa" in seat_ids
    assert "designer" in seat_ids


def test_clawseat_engineering_builder_is_codex_oauth() -> None:
    data = _load("clawseat-engineering")
    builder = next(e for e in data["engineers"] if e["id"] == "builder")
    assert builder["tool"] == "codex"
    assert builder["auth_mode"] == "oauth"
    assert builder["provider"] == "openai"


def test_clawseat_creative_loads_with_four_seats() -> None:
    data = _load("clawseat-creative")
    seats = _validate_seats(data)
    assert len(seats) == 4, f"expected 4 seats, got {len(seats)}: {[s['id'] for s in seats]}"
    seat_ids = [s["id"] for s in seats]
    assert "ancestor" in seat_ids
    assert "planner" in seat_ids
    assert "builder" in seat_ids   # codex execution seat (replaces qa)
    assert "designer" in seat_ids
    assert "qa" not in seat_ids    # qa removed in creative seat redesign


def test_clawseat_creative_designer_is_gemini_oauth() -> None:
    data = _load("clawseat-creative")
    designer = next(e for e in data["engineers"] if e["id"] == "designer")
    assert designer["tool"] == "gemini"
    assert designer["auth_mode"] == "oauth"
    assert designer["provider"] == "google"
    assert designer["role"] == "creative-designer"


def test_clawseat_creative_planner_role() -> None:
    data = _load("clawseat-creative")
    planner = next(e for e in data["engineers"] if e["id"] == "planner")
    assert planner["role"] == "creative-planner"
    assert planner["tool"] == "claude"
    assert planner["auth_mode"] == "oauth"
