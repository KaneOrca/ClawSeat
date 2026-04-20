"""Tests for T18 D1: ancestor-runbook.md canonical SOP doc tests."""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_RUNBOOK = _REPO / "core" / "skills" / "clawseat-install" / "references" / "ancestor-runbook.md"


def _text() -> str:
    assert _RUNBOOK.exists(), f"ancestor-runbook.md not found at {_RUNBOOK}"
    return _RUNBOOK.read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: all Phase 0-7 section headings present
# ══════════════════════════════════════════════════════════════════════════════

def test_runbook_has_phase_0_through_7():
    text = _text()
    for phase in range(8):
        assert f"Phase {phase}" in text, f"Phase {phase} heading missing from runbook"


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: all G1-G15 referenced in checklist
# ══════════════════════════════════════════════════════════════════════════════

def test_runbook_references_all_gaps():
    text = _text()
    for i in range(1, 16):
        assert f"G{i}" in text, f"G{i} missing from runbook"
    for i in range(1, 7):
        assert f"B{i}" in text, f"B{i} missing from runbook"


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: TUI decode table has 4 required entries
# ══════════════════════════════════════════════════════════════════════════════

def test_runbook_tui_decode_table_has_four_entries():
    text = _text()
    assert "bypass on" in text
    assert "shift+tab to cycle" in text
    assert "Select login method" in text
    assert "Do you trust this folder" in text


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: alarm discipline section includes git log -5
# ══════════════════════════════════════════════════════════════════════════════

def test_runbook_alarm_discipline_has_git_log():
    text = _text()
    assert "log -5" in text
    assert "Alarm" in text or "alarm" in text


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 (T17): TUI decode table has lark-cli ---WAIT--- (device flow polling)
# ══════════════════════════════════════════════════════════════════════════════

def test_runbook_tui_decode_has_lark_cli_wait():
    text = _text()
    assert "---WAIT---" in text or "WAIT" in text, (
        "runbook TUI decode must explain lark-cli ---WAIT--- as device flow polling"
    )
    assert "device flow" in text.lower() or "polling" in text.lower(), (
        "runbook must explain ---WAIT--- as device flow polling, not a block"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 6 (T17): TUI decode table has auth_needs_refresh (user token expired)
# ══════════════════════════════════════════════════════════════════════════════

def test_runbook_tui_decode_has_auth_needs_refresh():
    text = _text()
    assert "auth_needs_refresh" in text, (
        "runbook TUI decode must document auth_needs_refresh as user token expired"
    )
    assert "lark-cli auth login" in text, (
        "runbook must prescribe 'lark-cli auth login' as the fix for auth_needs_refresh"
    )
