from __future__ import annotations

import importlib.util
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "scripts" / "migrate_kb_singular.py"


def _load_migrate():
    spec = importlib.util.spec_from_file_location("migrate_kb_singular", _SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_rename_when_singular_missing(tmp_path: Path) -> None:
    (tmp_path / "arena" / "decisions").mkdir(parents=True)
    (tmp_path / "arena" / "decisions" / "one.md").write_text("one", encoding="utf-8")
    migrate = _load_migrate()

    report = migrate.migrate_all(tmp_path, commit=True)

    assert (tmp_path / "arena" / "decision" / "one.md").is_file()
    assert not (tmp_path / "arena" / "decisions").exists()
    assert report["projects"][0]["renamed_dirs"]


def test_merge_when_both_exist(tmp_path: Path) -> None:
    (tmp_path / "cartooner" / "decision").mkdir(parents=True)
    (tmp_path / "cartooner" / "decisions").mkdir(parents=True)
    (tmp_path / "cartooner" / "decision" / "one.md").write_text("one", encoding="utf-8")
    (tmp_path / "cartooner" / "decisions" / "two.md").write_text("two", encoding="utf-8")
    migrate = _load_migrate()

    report = migrate.migrate_all(tmp_path, commit=True)

    assert (tmp_path / "cartooner" / "decision" / "one.md").is_file()
    assert (tmp_path / "cartooner" / "decision" / "two.md").is_file()
    assert not (tmp_path / "cartooner" / "decisions").exists()
    assert report["projects"][0]["merged_dirs"]


def test_dry_run_no_writes(tmp_path: Path) -> None:
    (tmp_path / "cartooner" / "findings").mkdir(parents=True)
    (tmp_path / "cartooner" / "findings" / "one.md").write_text("one", encoding="utf-8")
    migrate = _load_migrate()

    migrate.migrate_all(tmp_path, commit=False)

    assert (tmp_path / "cartooner" / "findings" / "one.md").is_file()
    assert not (tmp_path / "cartooner" / "finding").exists()


def test_idempotent_already_singular(tmp_path: Path) -> None:
    (tmp_path / "install" / "decision").mkdir(parents=True)
    (tmp_path / "install" / "decision" / "one.md").write_text("one", encoding="utf-8")
    migrate = _load_migrate()

    first = migrate.migrate_all(tmp_path, commit=True)
    second = migrate.migrate_all(tmp_path, commit=True)

    assert (tmp_path / "install" / "decision" / "one.md").is_file()
    assert first["projects"][0]["renamed_dirs"] == []
    assert second["projects"][0]["merged_dirs"] == []
