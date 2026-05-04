from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "cartooner-creative.toml"


def _template() -> dict:
    with TEMPLATE.open("rb") as handle:
        return tomllib.load(handle)


def test_cartooner_creative_template_has_four_seats_and_split_layout() -> None:
    data = _template()
    assert data["defaults"]["window_mode"] == "split-2"
    assert data["defaults"]["monitor_max_panes"] == 4
    assert [seat["id"] for seat in data["engineers"]] == [
        "memory",
        "writer",
        "visual",
        "patrol",
    ]


def test_cartooner_creative_template_declared_skills_are_available() -> None:
    data = _template()
    declared = data["defaults"]["declared_skills"]
    assert isinstance(declared, list)
    assert "cartooner-image" in declared
    assert "cartooner-video" in declared
    assert "cartooner-audio" in declared
    assert "cartooner-storyboard" in declared


def test_cartooner_creative_template_left_main_pane_is_memory() -> None:
    data = _template()
    grid = data["window_layout"]["workers_grid"]
    assert grid["left_main_seat"] == "writer"
