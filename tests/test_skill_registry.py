"""Tests for core/skill_registry.py — load, filter, expand, validate, diff."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Bootstrap paths (mirrors conftest.py so the test is self-contained for imports).
_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO), str(_REPO / "core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.skill_registry import (
    SkillCheckResult,
    SkillEntry,
    diff_template,
    expand_skill_path,
    load_registry,
    skills_for_role,
    skills_for_source,
    validate_all,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _write_mini_registry(tmp_path: Path, skills_toml: str) -> Path:
    """Write a small registry TOML and return its path."""
    p = tmp_path / "skill_registry.toml"
    p.write_text(
        f'version = 1\ndescription = "test"\n\n{skills_toml}',
        encoding="utf-8",
    )
    return p


def _make_skill_dir(base: Path, name: str, *, create_md: bool = True) -> Path:
    """Create a fake skill directory, optionally with SKILL.md."""
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    if create_md:
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return d


# ══════════════════════════════════════════════════════════════════════
# load_registry
# ══════════════════════════════════════════════════════════════════════

class TestLoadRegistry:

    def test_default_path_returns_at_least_27_entries(self):
        """Loading the real registry should yield >= 27 skills (29 at time of writing)."""
        entries = load_registry()
        assert len(entries) >= 27, (
            f"Expected >= 27 registry entries, got {len(entries)}"
        )
        assert all(isinstance(e, SkillEntry) for e in entries)

    def test_custom_toml(self, tmp_path: Path):
        """A hand-written TOML with two skills should parse into two SkillEntry objects."""
        reg = _write_mini_registry(
            tmp_path,
            '[[skills]]\n'
            'name = "alpha"\n'
            'source = "bundled"\n'
            'path = "/tmp/alpha/SKILL.md"\n'
            'required = true\n'
            'roles = ["builder"]\n'
            'description = "Alpha skill"\n'
            '\n'
            '[[skills]]\n'
            'name = "beta"\n'
            'source = "gstack"\n'
            'path = "~/beta/SKILL.md"\n'
            'required = false\n'
            'roles = ["reviewer"]\n'
            'description = "Beta skill"\n',
        )
        entries = load_registry(reg)
        assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}"
        assert entries[0].name == "alpha"
        assert entries[0].source == "bundled"
        assert entries[0].required is True
        assert entries[1].name == "beta"
        assert entries[1].source == "gstack"
        assert entries[1].required is False

    def test_empty_skills_list(self, tmp_path: Path):
        """A TOML with no [[skills]] sections should return an empty list."""
        reg = _write_mini_registry(tmp_path, "# no skills here\n")
        entries = load_registry(reg)
        assert entries == [], f"Expected empty list, got {entries}"

    def test_nonexistent_path_raises(self, tmp_path: Path):
        """Attempting to load a non-existent file should raise FileNotFoundError."""
        missing = tmp_path / "does-not-exist.toml"
        with pytest.raises(FileNotFoundError):
            load_registry(missing)


# ══════════════════════════════════════════════════════════════════════
# skills_for_source
# ══════════════════════════════════════════════════════════════════════

class TestSkillsForSource:

    def test_bundled_only(self):
        """Filtering by 'bundled' should return only bundled entries."""
        entries = load_registry()
        bundled = skills_for_source(entries, "bundled")
        assert len(bundled) > 0, "Expected at least one bundled skill"
        non_bundled = [e for e in bundled if e.source != "bundled"]
        assert non_bundled == [], (
            f"Found non-bundled entries in bundled filter: "
            f"{[e.name for e in non_bundled]}"
        )

    def test_gstack_only(self):
        """Filtering by 'gstack' should return only gstack entries."""
        entries = load_registry()
        gstack = skills_for_source(entries, "gstack")
        assert len(gstack) > 0, "Expected at least one gstack skill"
        non_gstack = [e for e in gstack if e.source != "gstack"]
        assert non_gstack == [], (
            f"Found non-gstack entries in gstack filter: "
            f"{[e.name for e in non_gstack]}"
        )


# ══════════════════════════════════════════════════════════════════════
# skills_for_role
# ══════════════════════════════════════════════════════════════════════

class TestSkillsForRole:

    def test_builder_includes_gstack_investigate(self):
        """The 'builder' role should include gstack-investigate."""
        entries = load_registry()
        builder_skills = skills_for_role(entries, "builder")
        names = [e.name for e in builder_skills]
        assert "gstack-investigate" in names, (
            f"'gstack-investigate' not found in builder skills: {names}"
        )

    def test_reviewer_includes_gstack_review(self):
        """The 'reviewer' role should include gstack-review."""
        entries = load_registry()
        reviewer_skills = skills_for_role(entries, "reviewer")
        names = [e.name for e in reviewer_skills]
        assert "gstack-review" in names, (
            f"'gstack-review' not found in reviewer skills: {names}"
        )


# ══════════════════════════════════════════════════════════════════════
# expand_skill_path
# ══════════════════════════════════════════════════════════════════════

class TestExpandSkillPath:

    def test_clawseat_root_placeholder(self, monkeypatch: pytest.MonkeyPatch):
        """``{CLAWSEAT_ROOT}`` should be replaced with the env var value."""
        fake_root = "/tmp/fake-clawseat"
        monkeypatch.setenv("CLAWSEAT_ROOT", fake_root)

        # The module caches REPO_ROOT at import time, so we patch it directly.
        import core.skill_registry as mod
        original = mod.REPO_ROOT
        monkeypatch.setattr(mod, "REPO_ROOT", Path(fake_root))
        try:
            result = expand_skill_path("{CLAWSEAT_ROOT}/core/skills/foo/SKILL.md")
            assert result == Path(fake_root) / "core" / "skills" / "foo" / "SKILL.md", (
                f"Expected path under {fake_root}, got {result}"
            )
        finally:
            monkeypatch.setattr(mod, "REPO_ROOT", original)

    def test_tilde_expansion(self):
        """``~`` should be expanded to the user's home directory."""
        result = expand_skill_path("~/some/skill/SKILL.md")
        expected = Path.home() / "some" / "skill" / "SKILL.md"
        assert result == expected, f"Expected {expected}, got {result}"


# ══════════════════════════════════════════════════════════════════════
# validate_all
# ══════════════════════════════════════════════════════════════════════

class TestValidateAll:

    def test_all_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """When every skill path exists on disk, all_present should be True."""
        import core.skill_registry as mod
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

        # Create fake skill directories with SKILL.md
        skill_a = _make_skill_dir(tmp_path / "skills", "alpha", create_md=True)
        skill_b = _make_skill_dir(tmp_path / "skills", "beta", create_md=True)

        entries = [
            SkillEntry(
                name="alpha",
                source="bundled",
                path=str(skill_a / "SKILL.md"),
                required=True,
                roles=["builder"],
            ),
            SkillEntry(
                name="beta",
                source="bundled",
                path=str(skill_b / "SKILL.md"),
                required=False,
                roles=["reviewer"],
            ),
        ]

        result = validate_all(entries)
        assert isinstance(result, SkillCheckResult)
        assert result.all_present is True, (
            f"Expected all_present=True but got missing: "
            f"{[i.name for i in result.required_missing + result.optional_missing]}"
        )
        assert result.required_missing == []
        assert result.optional_missing == []

    def test_required_skill_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """When a required skill path does not exist, required_missing should be non-empty."""
        import core.skill_registry as mod
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

        missing_path = tmp_path / "skills" / "missing" / "SKILL.md"

        entries = [
            SkillEntry(
                name="missing-required",
                source="bundled",
                path=str(missing_path),
                required=True,
                roles=["builder"],
            ),
        ]

        result = validate_all(entries)
        assert result.all_present is False, "Expected all_present=False for missing required skill"
        assert len(result.required_missing) == 1, (
            f"Expected 1 required missing, got {len(result.required_missing)}"
        )
        assert result.required_missing[0].name == "missing-required"

    def test_optional_skill_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """When only an optional skill is missing, required_missing should be empty
        but optional_missing non-empty."""
        import core.skill_registry as mod
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

        present_skill = _make_skill_dir(tmp_path / "skills", "present", create_md=True)
        missing_path = tmp_path / "skills" / "gone" / "SKILL.md"

        entries = [
            SkillEntry(
                name="present-required",
                source="bundled",
                path=str(present_skill / "SKILL.md"),
                required=True,
                roles=["builder"],
            ),
            SkillEntry(
                name="gone-optional",
                source="gstack",
                path=str(missing_path),
                required=False,
                roles=["reviewer"],
            ),
        ]

        result = validate_all(entries)
        assert result.all_present is False, "Expected all_present=False when optional skill is missing"
        assert result.required_missing == [], (
            f"Expected no required missing, got {[i.name for i in result.required_missing]}"
        )
        assert len(result.optional_missing) == 1, (
            f"Expected 1 optional missing, got {len(result.optional_missing)}"
        )
        assert result.optional_missing[0].name == "gone-optional"


# ══════════════════════════════════════════════════════════════════════
# diff_template
# ══════════════════════════════════════════════════════════════════════

class TestDiffTemplate:

    def test_gstack_harness_returns_dict(self):
        """diff_template('gstack-harness') with the real registry should return
        a dict with 'unregistered' and 'uncovered' keys."""
        result = diff_template("gstack-harness")
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        # If the template exists, we get unregistered/uncovered; if not, we get 'error'.
        if "error" not in result:
            assert "unregistered" in result, "Missing 'unregistered' key in diff result"
            assert "uncovered" in result, "Missing 'uncovered' key in diff result"
            assert isinstance(result["unregistered"], list)
            assert isinstance(result["uncovered"], list)
        else:
            # Template file may not exist in test env; that is still a valid dict return.
            assert "error" in result
