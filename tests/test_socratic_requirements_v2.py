from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SKILL = _REPO / "core" / "skills" / "socratic-requirements" / "SKILL.md"
_REFS = _SKILL.parent / "references"


def _body(text: str) -> str:
    end = text.find("\n---", 4)
    assert end != -1
    return text[end + 4 :]


def test_skill_is_compact_and_sender_routed() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 150
    assert 'sender == "user"    -> Clarify mode' in text
    assert 'sender == "planner" -> Report mode' in text
    assert "sender unknown      -> Clarify mode" in text
    assert "not semantic keyword matching" in text
    assert "A-class hard constraints" in text
    assert "## Style" in text


def test_skill_body_has_no_keywords_field() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "keywords:" not in _body(text)


def test_clarify_mode_preserves_phase_0_to_3_path() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "Phase 0 -> Phase 3" in text
    assert "references/capability-catalog.yaml" in text
    assert "summary contract" in text


def test_report_mode_reference_has_auto_format_and_example() -> None:
    text = (_REFS / "report-mode.md").read_text(encoding="utf-8")
    assert "[Action] [Reason 1 sentence]" in text
    assert "派工给 builder 实现 X" in text
    assert "Drift recall is the only report-mode path" in text


def test_drift_signals_reference_defines_all_thresholds() -> None:
    text = (_REFS / "drift-signals.md").read_text(encoding="utf-8")
    for signal in ("范围蔓延", "里程碑超期", "假设过时", "焦点偏移"):
        assert signal in text
    for threshold in ("2x", "20%", "1.5x", "3+ consecutive dispatches"):
        assert threshold in text


def test_ux_reference_files_exist() -> None:
    for name in (
        "shared-tone.md",
        "i18n.md",
        "glossary-global.toml",
        "tui-card-format.md",
    ):
        assert (_REFS / name).is_file()


def test_sender_routing_dispatch_contract() -> None:
    routes = {
        "user": "Clarify mode",
        "planner": "Report mode",
        "unknown": "Clarify mode",
    }
    text = _SKILL.read_text(encoding="utf-8")
    for sender, mode in routes.items():
        if sender == "unknown":
            assert f"sender {sender}      -> {mode}" in text
        else:
            assert f'sender == "{sender}"' in text
            assert f"-> {mode}" in text
