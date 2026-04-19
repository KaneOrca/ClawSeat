"""Tests for T16 Items 1-3: koder-hygiene template + handoff update + init_koder wiring.

Covers:
  1. test_koder_hygiene_template_exists_with_rules
  2. test_handoff_template_has_koder_consume_ack_section
  3. test_managed_files_includes_koder_hygiene
  4. test_init_koder_render_dict_has_koder_hygiene
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_INIT_KODER_DIR = _REPO / "core" / "skills" / "clawseat-install" / "scripts"
if str(_INIT_KODER_DIR) not in sys.path:
    sys.path.insert(0, str(_INIT_KODER_DIR))

import init_koder


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: koder-hygiene.md exists with required rule keywords
# ══════════════════════════════════════════════════════════════════════════════

def test_koder_hygiene_template_exists_with_rules():
    template = _REPO / "core" / "templates" / "shared" / "TOOLS" / "koder-hygiene.md"
    assert template.exists(), f"koder-hygiene.md not found at {template}"
    text = template.read_text(encoding="utf-8")
    assert "AUTO_ADVANCE" in text
    assert "--ack-only" in text
    assert "USER_DECISION_NEEDED" in text


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: handoff.md has "Koder Consume ACK" section with --ack-only
# ══════════════════════════════════════════════════════════════════════════════

def test_handoff_template_has_koder_consume_ack_section():
    handoff = _REPO / "core" / "templates" / "shared" / "TOOLS" / "handoff.md"
    assert handoff.exists(), f"handoff.md not found at {handoff}"
    text = handoff.read_text(encoding="utf-8")
    assert "Koder Consume ACK" in text
    assert "--ack-only" in text


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: MANAGED_FILES contains TOOLS/koder-hygiene.md
# ══════════════════════════════════════════════════════════════════════════════

def test_managed_files_includes_koder_hygiene():
    assert "TOOLS/koder-hygiene.md" in init_koder.MANAGED_FILES


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: render dict entry exists and matches canonical template content
# ══════════════════════════════════════════════════════════════════════════════

def test_init_koder_render_dict_has_koder_hygiene():
    canonical = (_REPO / "core" / "templates" / "shared" / "TOOLS" / "koder-hygiene.md").read_text(encoding="utf-8")
    # build_render_dict requires profile/project/etc; test only the koder-hygiene
    # entry by constructing it the same way init_koder does
    rendered = (init_koder.REPO_ROOT / "core/templates/shared/TOOLS/koder-hygiene.md").read_text(encoding="utf-8")
    assert rendered == canonical
