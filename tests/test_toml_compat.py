from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _toml_compat import loads_safe  # noqa: E402


def test_fallback_parses_project_toml_shapes_without_toml_modules(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "tomllib", None)
    monkeypatch.setitem(sys.modules, "tomli", None)

    data = loads_safe(
        """
        version = 1
        name = "cartooner-front"
        repo_root = "/Users/ywf/coding/cartooner"
        monitor_session = "project-cartooner-front-monitor"
        open_detail_windows = false
        engineers = [
          "memory",
          "cartooner-product-solo-planner",
          "cartooner-product2-planner",
        ]
        monitor_engineers = ["memory", "cartooner-product2-planner"]

        [seat_overrides.cartooner-product2-planner]
        tool = "codex"
        auth_mode = "api"
        provider = "xcode-best"
        capabilities = ["root-cause research", "tests"]
        purpose = "负责 Cartooner 产品任务调研、实现、测试和自审。"
        planner_self_contained = true
        """
    )

    assert data["name"] == "cartooner-front"
    assert data["open_detail_windows"] is False
    assert data["engineers"] == [
        "memory",
        "cartooner-product-solo-planner",
        "cartooner-product2-planner",
    ]
    assert data["monitor_engineers"] == ["memory", "cartooner-product2-planner"]
    seat = data["seat_overrides"]["cartooner-product2-planner"]
    assert seat["provider"] == "xcode-best"
    assert seat["capabilities"] == ["root-cause research", "tests"]
    assert seat["purpose"] == "负责 Cartooner 产品任务调研、实现、测试和自审。"
    assert seat["planner_self_contained"] is True


def test_fallback_parses_profile_inline_team_tables_without_toml_modules(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "tomllib", None)
    monkeypatch.setitem(sys.modules, "tomli", None)

    data = loads_safe(
        """
        seats = [
          "memory",
          "cartooner-product2-planner",
        ]

        [teams]
        cartooner-product2 = { seats = ["cartooner-product2-planner"], team_type = "subteam", subgroup_profile = "planner-only", planner_count = 1, builder_count = 0, dedicated_reviewer = false, scaling_policy = { max_builders = 0, reviewer_fallback = "planner" } }
        """
    )

    assert data["seats"] == ["memory", "cartooner-product2-planner"]
    team = data["teams"]["cartooner-product2"]
    assert team["seats"] == ["cartooner-product2-planner"]
    assert team["subgroup_profile"] == "planner-only"
    assert team["builder_count"] == 0
    assert team["dedicated_reviewer"] is False
    assert team["scaling_policy"]["reviewer_fallback"] == "planner"
