from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


REPO = Path(__file__).resolve().parents[1]
ARCH = REPO / "docs" / "ARCHITECTURE.md"


def _template_seats(template: Path) -> list[str]:
    data = tomllib.loads(template.read_text(encoding="utf-8"))
    return [str(item["id"]) for item in data["engineers"]]


def test_architecture_project_template_roster_matches_templates() -> None:
    arch = ARCH.read_text(encoding="utf-8")

    for template in sorted((REPO / "templates").glob("clawseat-*.toml")):
        name = template.stem
        seats = _template_seats(template)
        matching_lines = [line for line in arch.splitlines() if f"`{name}`" in line]
        assert matching_lines, f"ARCHITECTURE.md must document {name}"
        joined = "\n".join(matching_lines)
        assert str(len(seats)) in joined, f"{name} count must be {len(seats)}"
        for seat in seats:
            assert seat in joined, f"{name} missing seat {seat}"


def test_architecture_roster_uses_patrol_not_qa() -> None:
    arch = ARCH.read_text(encoding="utf-8")
    template_section = arch.split("### Project Templates", 1)[1].split("### Solo Template", 1)[0]
    assert " patrol " in template_section
    assert " qa " not in template_section
