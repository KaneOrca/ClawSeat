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
    assert "memory" in seat_ids
    assert "planner" in seat_ids
    assert "builder" in seat_ids
    assert "reviewer" in seat_ids
    assert "patrol" in seat_ids
    assert "designer" in seat_ids


def test_clawseat_engineering_builder_is_codex_oauth() -> None:
    data = _load("clawseat-engineering")
    builder = next(e for e in data["engineers"] if e["id"] == "builder")
    assert builder["tool"] == "codex"
    assert builder["auth_mode"] == "oauth"
    assert builder["provider"] == "openai"


def test_clawseat_creative_memory_defaults_to_claude_oauth() -> None:
    data = _load("clawseat-creative")
    seats = _validate_seats(data)
    memory = next(e for e in seats if e["id"] == "memory")
    assert memory["tool"] == "claude"
    assert memory["auth_mode"] == "oauth"
    assert memory["provider"] == "anthropic"


def test_clawseat_creative_loads_with_five_seats() -> None:
    data = _load("clawseat-creative")
    seats = _validate_seats(data)
    assert len(seats) == 5, f"expected 5 seats, got {len(seats)}: {[s['id'] for s in seats]}"
    seat_ids = [s["id"] for s in seats]
    assert "memory" in seat_ids
    assert "planner" in seat_ids
    assert "builder" in seat_ids   # codex classification seat
    assert "patrol" in seat_ids
    assert "designer" in seat_ids  # gemini writing + scoring seat


def test_clawseat_creative_builder_skills_has_classify_not_write() -> None:
    """builder(codex) executes cs-classify only — cs-write must NOT be in its skills."""
    data = _load("clawseat-creative")
    builder = next(e for e in data["engineers"] if e["id"] == "builder")
    skill_names = [s.split("/")[-2] for s in builder.get("skills", [])]
    assert "cs-classify" in skill_names, f"builder must have cs-classify; got {skill_names}"
    assert "cs-write" not in skill_names, f"builder must NOT have cs-write; got {skill_names}"


def test_clawseat_creative_designer_skills_has_write_and_score() -> None:
    """designer(gemini) executes cs-write + cs-score — both must be in its skills."""
    data = _load("clawseat-creative")
    designer = next(e for e in data["engineers"] if e["id"] == "designer")
    skill_names = [s.split("/")[-2] for s in designer.get("skills", [])]
    assert "cs-write" in skill_names, f"designer must have cs-write; got {skill_names}"
    assert "cs-score" in skill_names, f"designer must have cs-score; got {skill_names}"


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
    assert planner["auth_mode"] == "api"
    assert planner["provider"] == "deepseek"
    assert planner["model"] == "deepseek-v4-pro"
