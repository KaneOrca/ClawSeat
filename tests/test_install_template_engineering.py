from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "clawseat-engineering.toml"


def _engineering() -> dict:
    with TEMPLATE.open("rb") as handle:
        return tomllib.load(handle)


def test_engineering_template_has_six_memory_primary_seats() -> None:
    data = _engineering()
    assert data["defaults"]["window_mode"] == "split-2"
    assert data["defaults"]["monitor_max_panes"] == 6
    assert [seat["id"] for seat in data["engineers"]] == [
        "memory",
        "planner",
        "builder",
        "reviewer",
        "patrol",
        "designer",
    ]


def test_engineering_template_reviewer_is_independent_claude_oauth() -> None:
    reviewer = next(seat for seat in _engineering()["engineers"] if seat["id"] == "reviewer")
    assert reviewer["role"] == "code-reviewer"
    assert reviewer["tool"] == "claude"
    assert reviewer["auth_mode"] == "oauth"
    assert reviewer["provider"] == "anthropic"
    assert reviewer["review_authority"] is True


def test_engineering_template_builder_and_designer_are_cross_tool() -> None:
    seats = {seat["id"]: seat for seat in _engineering()["engineers"]}
    assert seats["builder"]["tool"] == "codex"
    assert seats["builder"]["provider"] == "openai"
    assert seats["designer"]["tool"] == "gemini"
    assert seats["designer"]["provider"] == "google"
