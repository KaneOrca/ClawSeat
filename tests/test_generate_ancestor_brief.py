"""Tests for T18 D4: generate_ancestor_brief.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import generate_ancestor_brief as gab


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_fake_runbook(tmp_path: Path) -> Path:
    rb = tmp_path / "runbook.md"
    rb.write_text(
        "# Test Runbook\n\n"
        "## Phase 0 — Pre-flight\n\nPhase 0 content for <PROJECT> using agent <AGENT_NAME>.\n\n"
        "## Phase 1 — Memory\n\nMemory content group <GROUP_ID>.\n\n"
        "## Phase 2 — Overlay\n\nOverlay content.\n\n"
        "## Phase 3 — Bootstrap\n\nBootstrap content.\n\n"
        "## Phase 4 — Config\n\nConfig content.\n\n"
        "## Phase 5 — Feishu\n\nFeishu content ${PROJECT}.\n\n"
        "## Phase 6 — TUI\n\nTUI content.\n\n"
        "## Phase 7 — Alarm\n\nAlarm content.\n\n",
        encoding="utf-8",
    )
    return rb


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: smoke — command does not crash and stdout has 5+ phase headers
# ══════════════════════════════════════════════════════════════════════════════

def test_smoke_stdout_has_phase_headers(capsys):
    rc = gab.main([
        "--project", "testproj",
        "--koder-agent", "mor",
        "--feishu-group-id", "oc_test123",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    phase_count = sum(1 for i in range(8) if f"Phase {i}" in out)
    assert phase_count >= 5, f"Expected ≥5 Phase headers in output, found {phase_count}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: substitution — placeholders replaced in output
# ══════════════════════════════════════════════════════════════════════════════

def test_substitution_replaces_placeholders(tmp_path):
    rb = _make_fake_runbook(tmp_path)
    brief = gab.generate(
        "myproj", "myagent", "oc_abc999",
        runbook_path=rb,
    )
    assert "<PROJECT>" not in brief, "bare <PROJECT> placeholder not replaced"
    assert "${PROJECT}" not in brief, "${PROJECT} placeholder not replaced"
    assert "<AGENT_NAME>" not in brief, "<AGENT_NAME> not replaced"
    assert "<GROUP_ID>" not in brief, "<GROUP_ID> not replaced"
    assert "myproj" in brief
    assert "myagent" in brief
    assert "oc_abc999" in brief


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: missing required arg → non-zero exit (argparse error)
# ══════════════════════════════════════════════════════════════════════════════

def test_missing_required_arg_exits_nonzero():
    with pytest.raises(SystemExit) as exc_info:
        gab.main(["--project", "foo"])  # missing --koder-agent and --feishu-group-id
    assert exc_info.value.code != 0


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: generated brief internal consistency — all phase vars are present
# ══════════════════════════════════════════════════════════════════════════════

def test_generated_brief_internal_consistency(tmp_path):
    rb = _make_fake_runbook(tmp_path)
    brief = gab.generate("proj-x", "agent-y", "oc_zzz", runbook_path=rb)
    # All 8 phase sections should be present in fake runbook
    for i in range(8):
        assert f"Phase {i}" in brief, f"Phase {i} missing from generated brief"
    # Variables used in body should be substituted
    assert "proj-x" in brief
    assert "agent-y" in brief
    assert "oc_zzz" in brief


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 (T17): Phase 5 section is non-empty in real runbook output
# ══════════════════════════════════════════════════════════════════════════════

def test_phase5_section_is_nonempty_in_real_runbook_brief():
    """Phase 5 in the canonical ancestor-runbook.md must produce non-trivial content."""
    brief = gab.generate("testproj", "koder", "oc_test999")
    # Phase 5 heading must appear
    assert "Phase 5" in brief, "Phase 5 must appear in generated brief from real runbook"
    # Phase 5 must contain Feishu-related content
    phase5_start = brief.find("Phase 5")
    phase6_start = brief.find("Phase 6", phase5_start)
    phase5_content = brief[phase5_start:phase6_start] if phase6_start != -1 else brief[phase5_start:]
    assert len(phase5_content) > 100, (
        f"Phase 5 section must be non-trivial (>100 chars); got {len(phase5_content)}"
    )
    assert "Feishu" in phase5_content or "lark" in phase5_content.lower(), (
        "Phase 5 content must mention Feishu or lark"
    )
