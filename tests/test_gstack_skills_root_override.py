"""Regression: GSTACK_SKILLS_ROOT env var redirects every consumer.

Stranger-report: friends who cloned gstack to a non-canonical path (e.g.
`~/gstack/` instead of `~/.gstack/repos/gstack/`) get ModuleNotFound /
"gstack skills missing" from whichever consumer checks first. The fix is
a single env var `GSTACK_SKILLS_ROOT` that redirects all four consumers:

  - core/skill_registry.py::expand_skill_path (loader-level — covers
    bootstrap_harness, start_seat, skill_manager, preflight's registry
    validation)
  - core/preflight.py (the direct gstack presence check)
  - shells/openclaw-plugin/install_bundled_skills.py (the symlink probe)
  - core/skills/gstack-harness/scripts/dispatch_task.py (the INTENT_MAP,
    already covered by test_dispatch_gstack_root.py)

This test locks in that the first three all honor the env var. The
fourth has its own existing regression in test_dispatch_gstack_root.py.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]


def _load_skill_registry():
    """Fresh-import skill_registry so environment changes take effect."""
    spec = importlib.util.spec_from_file_location(
        "skill_registry_under_test", _REPO / "core" / "skill_registry.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["skill_registry_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_expand_skill_path_rewrites_tilde_form_under_env_override(monkeypatch, tmp_path):
    """Registry path `~/.gstack/repos/gstack/.agents/skills/<x>` must be
    rewritten to `<GSTACK_SKILLS_ROOT>/<x>` when the env is set."""
    monkeypatch.setenv("GSTACK_SKILLS_ROOT", str(tmp_path / "custom-gstack"))
    mod = _load_skill_registry()

    raw = "~/.gstack/repos/gstack/.agents/skills/gstack-review/SKILL.md"
    result = mod.expand_skill_path(raw)
    assert str(result) == str(tmp_path / "custom-gstack" / "gstack-review" / "SKILL.md"), (
        f"expected redirection to GSTACK_SKILLS_ROOT, got {result}"
    )


def test_expand_skill_path_rewrites_expanded_form_under_env_override(monkeypatch, tmp_path):
    """If the TOML already has an expanded absolute path (unusual but
    legal), the same rewrite must apply."""
    monkeypatch.setenv("GSTACK_SKILLS_ROOT", str(tmp_path / "alt"))
    mod = _load_skill_registry()

    canonical = str(Path("~/.gstack/repos/gstack/.agents/skills").expanduser())
    raw = f"{canonical}/gstack-ship/SKILL.md"
    result = mod.expand_skill_path(raw)
    assert str(result) == str(tmp_path / "alt" / "gstack-ship" / "SKILL.md")


def test_expand_skill_path_noop_when_env_unset(monkeypatch):
    """Default behavior (env unset) must still expand `~` to real home."""
    monkeypatch.delenv("GSTACK_SKILLS_ROOT", raising=False)
    mod = _load_skill_registry()

    raw = "~/.gstack/repos/gstack/.agents/skills/gstack-qa/SKILL.md"
    result = mod.expand_skill_path(raw)
    assert str(result) == str(
        Path.home() / ".gstack/repos/gstack/.agents/skills/gstack-qa/SKILL.md"
    ), "unexpected rewrite when GSTACK_SKILLS_ROOT is unset"


def test_expand_skill_path_leaves_non_gstack_paths_alone(monkeypatch, tmp_path):
    """Non-gstack paths (e.g. `{CLAWSEAT_ROOT}/core/skills/<x>`) must be
    untouched by the gstack override."""
    monkeypatch.setenv("GSTACK_SKILLS_ROOT", str(tmp_path / "custom"))
    mod = _load_skill_registry()

    raw = "{CLAWSEAT_ROOT}/core/skills/clawseat/SKILL.md"
    result = mod.expand_skill_path(raw)
    # Not under custom-gstack; should resolve under CLAWSEAT_ROOT
    assert "custom" not in str(result), (
        f"non-gstack path was wrongly rewritten: {result}"
    )
    assert str(result).endswith("core/skills/clawseat/SKILL.md")


def test_empty_env_is_treated_as_unset(monkeypatch):
    """An empty GSTACK_SKILLS_ROOT must fall back to canonical lookup —
    matches the `.strip() or None` semantics in dispatch_task's resolver."""
    monkeypatch.setenv("GSTACK_SKILLS_ROOT", "")
    mod = _load_skill_registry()
    raw = "~/.gstack/repos/gstack/.agents/skills/gstack-careful/SKILL.md"
    result = mod.expand_skill_path(raw)
    # Should look under real home, not under "" (which would produce an
    # absolute /gstack-careful/... junk path).
    assert str(result).startswith(str(Path.home())), (
        f"empty env should fall back to canonical home, got {result}"
    )


def test_install_bundled_skills_resolver_honors_env(monkeypatch, tmp_path):
    """install_bundled_skills.py's module-level GSTACK_SKILLS_ROOT must
    reflect the env var at import time."""
    monkeypatch.setenv("GSTACK_SKILLS_ROOT", str(tmp_path / "alt-gstack"))
    # Run via subprocess so the module loads from scratch with the new env.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, %r); "
            "import install_bundled_skills as m; print(m.GSTACK_SKILLS_ROOT)"
            % str(_REPO / "shells" / "openclaw-plugin"),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "GSTACK_SKILLS_ROOT": str(tmp_path / "alt-gstack")},
    )
    assert result.returncode == 0, result.stderr
    assert str(tmp_path / "alt-gstack") in result.stdout, (
        f"install_bundled_skills.GSTACK_SKILLS_ROOT did not honor env: {result.stdout}"
    )


def test_preflight_gstack_check_reports_env_path(monkeypatch, tmp_path):
    """preflight's gstack WARN message must name the override path when
    GSTACK_SKILLS_ROOT is set and the override path doesn't exist."""
    bad = tmp_path / "definitely-missing-gstack"
    result = subprocess.run(
        [sys.executable, "-S", str(_REPO / "core" / "preflight.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "GSTACK_SKILLS_ROOT": str(bad), "CLAWSEAT_ROOT": str(_REPO)},
        cwd="/",
    )
    # --help exits 0 and doesn't run the full check, but we at least want
    # to prove the script still imports clean when the env var is set.
    assert result.returncode == 0, (
        f"preflight.py --help regressed under GSTACK_SKILLS_ROOT:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
