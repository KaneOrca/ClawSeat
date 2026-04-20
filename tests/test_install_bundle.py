"""Tests for shells/openclaw-plugin/install_openclaw_bundle.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Bootstrap paths (mirrors conftest.py).
_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO), str(_REPO / "shells" / "openclaw-plugin")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import install_openclaw_bundle as mod


# ── Helpers ──────────────────────────────────────────────────────────


def _make_source_dirs(base: Path, skills: dict[str, Path]) -> dict[str, Path]:
    """Create fake source directories for every skill entry.

    Returns a new mapping where each value points into *base*,
    mirroring the layout the module expects.
    """
    remapped: dict[str, Path] = {}
    for name in skills:
        d = base / "core" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
        remapped[name] = d
    return remapped


# ══════════════════════════════════════════════════════════════════════
# ensure_symlink
# ══════════════════════════════════════════════════════════════════════


class TestEnsureSymlink:

    def test_creates_new_symlink(self, tmp_path: Path):
        """When destination does not exist, a new symlink is created."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "links" / "my-link"

        mod.ensure_symlink(dest, source, dry_run=False)

        assert dest.is_symlink()
        assert dest.resolve() == source.resolve()

    def test_already_same_target_is_noop(self, tmp_path: Path):
        """When destination already points to the same source, nothing changes."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "link"
        dest.symlink_to(source)

        # Should not raise and symlink should still point to source.
        mod.ensure_symlink(dest, source, dry_run=False)

        assert dest.is_symlink()
        assert dest.resolve() == source.resolve()

    def test_replaces_different_target(self, tmp_path: Path):
        """When destination is a symlink to a different target, it is replaced."""
        old_source = tmp_path / "old-source"
        old_source.mkdir()
        new_source = tmp_path / "new-source"
        new_source.mkdir()
        dest = tmp_path / "link"
        dest.symlink_to(old_source)

        mod.ensure_symlink(dest, new_source, dry_run=False)

        assert dest.is_symlink()
        assert dest.resolve() == new_source.resolve()

    def test_non_symlink_raises_runtime_error(self, tmp_path: Path):
        """When destination is a regular file, RuntimeError is raised."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "regular-file"
        dest.write_text("I am a regular file", encoding="utf-8")

        with pytest.raises(RuntimeError, match="non-symlink"):
            mod.ensure_symlink(dest, source, dry_run=False)

    def test_dry_run_does_not_create(self, tmp_path: Path):
        """In dry-run mode, no symlink is created on disk."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "links" / "my-link"

        mod.ensure_symlink(dest, source, dry_run=True)

        assert not dest.exists()
        assert not dest.is_symlink()


# ══════════════════════════════════════════════════════════════════════
# install_bundle
# ══════════════════════════════════════════════════════════════════════


class TestInstallBundle:

    def test_creates_all_expected_symlinks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """install_bundle should create symlinks for all global + koder skills."""
        fake_root = tmp_path / "clawseat"
        fake_root.mkdir()

        # Build fake source dirs and patch the module-level dicts.
        global_sources = _make_source_dirs(fake_root, mod.GLOBAL_SKILLS)
        koder_sources = _make_source_dirs(fake_root, mod.WORKSPACE_KODER_SKILLS)
        monkeypatch.setattr(mod, "GLOBAL_SKILLS", global_sources)
        monkeypatch.setattr(mod, "WORKSPACE_KODER_SKILLS", koder_sources)

        # Patch external-skill checks to report nothing missing so they
        # don't interfere with the symlink-count assertion.
        monkeypatch.setattr(mod, "REQUIRED_AGENT_SKILLS", [])
        monkeypatch.setattr(mod, "REQUIRED_GSTACK_SKILLS", [])

        openclaw_home = tmp_path / "dot-openclaw"

        result = mod.install_bundle(openclaw_home, dry_run=False)

        skills_root = openclaw_home / "skills"
        koder_root = openclaw_home / "workspace-koder" / "skills"

        for name, source in global_sources.items():
            link = skills_root / name
            assert link.is_symlink(), f"Global skill {name} symlink not created"
            assert link.resolve() == source.resolve()

        for name, source in koder_sources.items():
            link = koder_root / name
            assert link.is_symlink(), f"Koder skill {name} symlink not created"
            assert link.resolve() == source.resolve()

        assert isinstance(result, mod.InstallBundleResult)
        assert result.missing_count == 0

    def test_main_keeps_returncode_zero_when_external_skills_missing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        """Missing external skills should warn but not fail the canonical install handoff."""
        monkeypatch.setattr(
            mod,
            "parse_args",
            lambda: type("Args", (), {"openclaw_home": str(tmp_path / ".openclaw"), "dry_run": False})(),
        )
        monkeypatch.setattr(
            mod,
            "install_bundle",
            lambda *_args, **_kwargs: mod.InstallBundleResult(
                missing_agent_skills=["lark-im"],
                missing_gstack_skills=["gstack-review"],
            ),
        )
        monkeypatch.setattr(mod, "running_from_canonical_checkout", lambda *_args, **_kwargs: False)
        monkeypatch.setattr(mod, "canonical_clawseat_root", lambda *_args, **_kwargs: tmp_path / ".clawseat")
        monkeypatch.setattr(mod, "bundle_source_root", lambda: tmp_path / "dev-clawseat")

        rc = mod.main()
        out = capsys.readouterr().out

        assert rc == 0
        assert "install_warning" in out
        assert "openclaw_first_install.py" in out


# ══════════════════════════════════════════════════════════════════════
# check_agent_skills
# ══════════════════════════════════════════════════════════════════════


class TestCheckAgentSkills:

    def test_all_present_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When every required agent skill has SKILL.md, missing list is empty."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setattr(mod, "REQUIRED_AGENT_SKILLS", ["skill-a", "skill-b"])

        agents_skills = tmp_path / ".agents" / "skills"
        for name in ("skill-a", "skill-b"):
            d = agents_skills / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

        missing = mod.check_agent_skills(dry_run=False)
        assert missing == [], f"Expected no missing skills, got {missing}"

    def test_some_missing_returns_names(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When some skills lack SKILL.md, their names appear in the result."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setattr(
            mod, "REQUIRED_AGENT_SKILLS", ["present", "absent-1", "absent-2"]
        )

        agents_skills = tmp_path / ".agents" / "skills"
        d = agents_skills / "present"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text("# present\n", encoding="utf-8")

        missing = mod.check_agent_skills(dry_run=False)
        assert sorted(missing) == ["absent-1", "absent-2"], (
            f"Expected ['absent-1', 'absent-2'], got {missing}"
        )


# ══════════════════════════════════════════════════════════════════════
# Module-level constants
# ══════════════════════════════════════════════════════════════════════


class TestModuleConstants:

    def test_global_skills_has_10_entries(self):
        assert len(mod.GLOBAL_SKILLS) == 10, (
            f"GLOBAL_SKILLS should have 10 entries, got {len(mod.GLOBAL_SKILLS)}"
        )

    def test_workspace_koder_skills_has_6_entries(self):
        assert len(mod.WORKSPACE_KODER_SKILLS) == 6, (
            f"WORKSPACE_KODER_SKILLS should have 6 entries, "
            f"got {len(mod.WORKSPACE_KODER_SKILLS)}"
        )

    def test_running_from_canonical_checkout_uses_home_relative_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(mod, "CLAWSEAT_ROOT", tmp_path / ".clawseat")

        assert mod.running_from_canonical_checkout(tmp_path) is True
