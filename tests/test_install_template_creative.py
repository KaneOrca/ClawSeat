from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "clawseat-creative.toml"


def _creative() -> dict:
    with TEMPLATE.open("rb") as handle:
        return tomllib.load(handle)


def test_creative_template_has_five_seats_and_four_worker_panes() -> None:
    data = _creative()
    assert data["defaults"]["window_mode"] == "split-2"
    assert data["defaults"]["monitor_max_panes"] == 4
    assert [seat["id"] for seat in data["engineers"]] == ["memory", "planner", "builder", "patrol", "designer"]


def test_creative_template_memory_is_claude_oauth() -> None:
    memory = next(seat for seat in _creative()["engineers"] if seat["id"] == "memory")
    assert memory["tool"] == "claude"
    assert memory["auth_mode"] == "oauth"
    assert memory["provider"] == "anthropic"


def test_creative_template_api_workers_have_seed_providers() -> None:
    seats = {seat["id"]: seat for seat in _creative()["engineers"]}
    assert seats["planner"]["provider"] == "deepseek"
    assert seats["planner"]["model"] == "deepseek-v4-pro"
    assert seats["patrol"]["provider"] == "minimax"
    assert seats["patrol"]["model"] == "MiniMax-M2.7-highspeed"
