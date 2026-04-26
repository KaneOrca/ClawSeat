from __future__ import annotations

import os
import importlib.util
from pathlib import Path

_SETUP_HELPERS = Path(__file__).with_name("test_install_privacy_setup.py")
_setup_spec = importlib.util.spec_from_file_location("_h3_install_privacy_setup", _SETUP_HELPERS)
assert _setup_spec is not None
assert _setup_spec.loader is not None
_setup = importlib.util.module_from_spec(_setup_spec)
_setup_spec.loader.exec_module(_setup)

_prepare_h3_fake_root = _setup._prepare_h3_fake_root
_run_install = _setup._run_install


def test_install_creates_new_skill_symlinks(tmp_path: Path) -> None:
    root, home, py_stubs = _prepare_h3_fake_root(tmp_path)
    result = _run_install(root, home, py_stubs, project="h3skills")
    assert result.returncode == 0, result.stderr

    skill_homes = (
        home / ".agents" / "skills",
        home / ".gemini" / "skills",
        home / ".codex" / "skills",
    )
    for skills_home in skill_homes:
        for skill in (
            "clawseat-memory",
            "clawseat-decision-escalation",
            "clawseat-koder",
            "clawseat-privacy",
            "clawseat-memory-reporting",
        ):
            link = skills_home / skill
            assert link.is_symlink()
            assert os.readlink(link) == str(root / "core" / "skills" / skill)


def test_install_skill_symlinks_are_idempotent(tmp_path: Path) -> None:
    root, home, py_stubs = _prepare_h3_fake_root(tmp_path)
    first = _run_install(root, home, py_stubs, project="h3idem")
    second = _run_install(root, home, py_stubs, project="h3idem")
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert (home / ".agents" / "skills" / "clawseat-privacy").is_symlink()
    assert (home / ".gemini" / "skills" / "clawseat-memory-reporting").is_symlink()
    assert (home / ".codex" / "skills" / "clawseat-memory-reporting").is_symlink()


def test_install_leaves_existing_clawseat_memory_symlink(tmp_path: Path) -> None:
    root, home, py_stubs = _prepare_h3_fake_root(tmp_path)
    skills_home = home / ".agents" / "skills"
    skills_home.mkdir(parents=True, exist_ok=True)
    memory_link = skills_home / "clawseat-memory"
    memory_target = root / "core" / "skills" / "clawseat-memory"
    memory_link.symlink_to(memory_target)

    result = _run_install(root, home, py_stubs, project="h3memorylink")
    assert result.returncode == 0, result.stderr
    assert memory_link.is_symlink()
    assert os.readlink(memory_link) == str(memory_target)


def test_install_creates_gemini_and_codex_skill_dirs(tmp_path: Path) -> None:
    root, home, py_stubs = _prepare_h3_fake_root(tmp_path)
    result = _run_install(root, home, py_stubs, project="h3multi")
    assert result.returncode == 0, result.stderr

    for skills_home in (home / ".gemini" / "skills", home / ".codex" / "skills"):
        assert skills_home.is_dir()
        assert (skills_home / "clawseat-memory").is_symlink()
        assert os.readlink(skills_home / "clawseat-memory") == str(
            root / "core" / "skills" / "clawseat-memory"
        )
