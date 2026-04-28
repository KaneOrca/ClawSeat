from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


_REPO = Path(__file__).resolve().parents[1]


def _solo() -> dict:
    return tomllib.loads((_REPO / "templates" / "clawseat-solo.toml").read_text(encoding="utf-8"))


def test_solo_template_loads() -> None:
    """clawseat-solo.toml loads with 3 engineers, split-2 window, monitor_max_panes=3."""
    data = _solo()
    assert len(data["engineers"]) == 3
    assert data["defaults"]["window_mode"] == "split-2"
    assert data["defaults"]["monitor_max_panes"] == 3
    ids = {e["id"] for e in data["engineers"]}
    assert ids == {"memory", "builder", "designer"}


def test_solo_memory_swallows_planner() -> None:
    """memory engineer has active_loop_owner + dispatch_authority + planner SKILL."""
    data = _solo()
    mem = next(e for e in data["engineers"] if e["id"] == "memory")
    assert mem["active_loop_owner"] is True
    assert mem["dispatch_authority"] is True
    skill_paths = " ".join(mem["skills"])
    assert "planner/SKILL.md" in skill_paths
    assert len(mem["skills"]) == 11
    builder = next(e for e in data["engineers"] if e["id"] == "builder")
    assert builder["tool"] == "codex"
    assert builder["auth_mode"] == "oauth"
    assert len(builder["skills"]) == 3
    designer = next(e for e in data["engineers"] if e["id"] == "designer")
    assert designer["tool"] == "gemini"
    assert designer["auth_mode"] == "oauth"
    assert len(designer["skills"]) == 3
