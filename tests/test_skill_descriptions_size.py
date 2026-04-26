from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_MAX_DESCRIPTION_CHARS = 150


def _frontmatter_description(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} is missing frontmatter"
    end = text.find("\n---", 4)
    assert end != -1, f"{path} frontmatter is not closed"
    for line in text[4:end].splitlines():
        if line.startswith("description:"):
            value = line.split(":", 1)[1].strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            return value
    raise AssertionError(f"{path} frontmatter has no description")


def test_clawseat_skill_descriptions_fit_codex_budget() -> None:
    skill_files = sorted(
        path
        for path in (_REPO / "core" / "skills").glob("clawseat*/SKILL.md")
        if not path.is_symlink()
    )
    assert skill_files

    for path in skill_files:
        description = _frontmatter_description(path)
        assert description
        assert len(description) < _MAX_DESCRIPTION_CHARS, (
            f"{path} description has {len(description)} chars: {description}"
        )
