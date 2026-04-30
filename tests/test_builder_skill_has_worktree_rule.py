from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_BUILDER_SKILL = _REPO / "core" / "skills" / "builder" / "SKILL.md"
_CREATIVE_BUILDER_SKILL = _REPO / "core" / "skills" / "creative-builder" / "SKILL.md"

_REQUIRED_KEYWORDS = ("worktree", "isolated", "clawseat/main", "不动 operator")


def test_builder_skills_contain_worktree_rule_keywords() -> None:
    for skill_path in (_BUILDER_SKILL, _CREATIVE_BUILDER_SKILL):
        text = skill_path.read_text(encoding="utf-8").lower()

        for keyword in _REQUIRED_KEYWORDS:
            assert keyword in text, f"{skill_path} must contain keyword: {keyword}"
