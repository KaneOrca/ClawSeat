"""Tests for normalize_role handling of creative-* template role names.

creative-planner / creative-builder / creative-designer are the seat roles
in the clawseat-creative template. normalize_role must map them to their
engineering counterparts so planner-event detection and console sort priority
work correctly across templates.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "core" / "skills" / "gstack-harness" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _common import normalize_role, role_sort_key  # noqa: E402


def test_normalize_creative_planner():
    assert normalize_role("creative-planner") == "planner"


def test_normalize_creative_builder():
    assert normalize_role("creative-builder") == "builder"


def test_normalize_creative_designer():
    assert normalize_role("creative-designer") == "designer"


def test_normalize_existing_aliases_unchanged():
    """Existing mappings must not regress."""
    assert normalize_role("planner") == "planner"
    assert normalize_role("planner-dispatcher") == "planner"
    assert normalize_role("memory") == "memory"
    assert normalize_role("memory-oracle") == "memory"
    assert normalize_role("builder") == "builder"
    assert normalize_role("") == "specialist"


def test_role_sort_key_creative_planner_gets_planner_priority():
    """creative-planner must sort at priority 1, same as plain planner."""
    key_creative = role_sort_key("planner", "creative-planner")
    key_plain = role_sort_key("planner", "planner")
    assert key_creative == key_plain, (
        f"creative-planner sort key {key_creative} != planner sort key {key_plain}"
    )


def test_role_sort_key_creative_builder_gets_builder_priority():
    key_creative = role_sort_key("builder", "creative-builder")
    key_plain = role_sort_key("builder", "builder")
    assert key_creative == key_plain


def test_role_sort_key_creative_designer_gets_designer_priority():
    key_creative = role_sort_key("designer", "creative-designer")
    key_plain = role_sort_key("designer", "designer")
    assert key_creative == key_plain
