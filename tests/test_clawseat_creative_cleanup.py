from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO / "templates"
TEMPLATE_README = TEMPLATES_DIR / "README.md"
DEPRECATED_TEMPLATE = TEMPLATES_DIR / "clawseat-creative.toml"
REFERENCE_SKILL = REPO / "docs" / "references" / "SKILL.md"
SCRIPTS_DIR = REPO / "core" / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import reconcile_seat_states
import agent_admin_session_lifecycle  # noqa: E402


DEPRECATION_NOTE = "`clawseat-creative` 已于 2026-05-02 废弃。使用该模板的项目（install/koder/lotus-radar）在下次 reinstall 时迁移至 `clawseat-engineering`。"


def test_clawseat_creative_template_is_deleted() -> None:
    assert not DEPRECATED_TEMPLATE.exists()


def test_templates_readme_includes_deprecation_note() -> None:
    assert DEPRECATION_NOTE in TEMPLATE_README.read_text(encoding="utf-8")


def test_references_skill_has_solo_migration_note() -> None:
    assert REFERENCE_SKILL.is_file()
    text = REFERENCE_SKILL.read_text(encoding="utf-8")
    assert "## Template" in text
    assert "已废弃，参考 clawseat-solo" in text


def test_clawseat_minimal_occurs_only_in_approved_notes_or_live_configs() -> None:
    needle = "clawseat-" + "minimal"
    hits: list[tuple[Path, int, str]] = []
    for path in REPO.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "tests" in path.parts or "artifacts" in path.parts:
            continue
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if needle in line:
                    hits.append((path, line_no, line))
        except UnicodeDecodeError:
            continue
    assert not hits, f"unexpected {needle} references: {hits}"


def test_reconcile_seat_states_warns_on_legacy_role_prefixes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for legacy in ("creative-builder", "minimal-designer"):
        reconcile_seat_states._normalise_role(legacy, "seat")
        captured = capsys.readouterr()
        assert "warn: deprecated role namespace in session metadata" in captured.err
        assert "for seat=" in captured.err

    assert reconcile_seat_states._normalise_role("creative-builder", "builder") == "builder"
    assert reconcile_seat_states._normalise_role("minimal-designer", "designer") == "designer"


def test_session_lifecycle_warns_on_legacy_role_prefix(capsys: pytest.CaptureFixture[str]) -> None:
    lifecycle = agent_admin_session_lifecycle.SessionStartLifecycle()
    for seat_id, legacy, expected in (
        ("builder-1", "creative-builder", "builder"),
        ("designer-1", "minimal-designer", "designer"),
    ):
        session = SimpleNamespace(
            engineer_id=seat_id,
            project_engineers={seat_id: SimpleNamespace(role=legacy)},
        )
        assert lifecycle._role_for_session(session, SimpleNamespace()) == expected
        captured = capsys.readouterr()
        assert (
            f"warn: deprecated role namespace in project context mapped from {legacy} -> {expected}"
            in captured.err
        )
