"""Tests for core/adapter/_adapter_exec.py pure functions."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so "core.adapter" is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from core.adapter._adapter_exec import (
    load_toml_like,
    parse_brief,
    parse_pending_frontstage,
    parse_pending_item,
    render_pending_item,
    serialize_adapter_result,
    write_pending_frontstage,
)
from core.adapter._adapter_types import AdapterResult, PendingFrontstageItem


# ---------------------------------------------------------------------------
# load_toml_like
# ---------------------------------------------------------------------------

def test_load_toml_like_simple(tmp_path: Path) -> None:
    f = tmp_path / "cfg.toml"
    f.write_text("name = Alice\nage = 30\n", encoding="utf-8")
    result = load_toml_like(f)
    # Unquoted non-boolean values are skipped by the implementation
    # (only quoted strings and "true"/"false" are kept).
    assert result == {}


def test_load_toml_like_quoted_values(tmp_path: Path) -> None:
    f = tmp_path / "cfg.toml"
    f.write_text('name = "Alice"\nrole = "admin"\n', encoding="utf-8")
    result = load_toml_like(f)
    assert result == {"name": "Alice", "role": "admin"}


def test_load_toml_like_boolean_values(tmp_path: Path) -> None:
    f = tmp_path / "cfg.toml"
    f.write_text("enabled = true\nverbose = false\n", encoding="utf-8")
    result = load_toml_like(f)
    assert result == {"enabled": "true", "verbose": "false"}


def test_load_toml_like_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.toml"
    f.write_text("", encoding="utf-8")
    assert load_toml_like(f) == {}


def test_load_toml_like_comments_and_blanks(tmp_path: Path) -> None:
    content = '# comment line\n\nkey = "value"\n# another comment\n'
    f = tmp_path / "cfg.toml"
    f.write_text(content, encoding="utf-8")
    result = load_toml_like(f)
    # Lines starting with "#" contain "=" after the "#", so the parser will
    # split on "=".  However the extracted raw_value won't match boolean or
    # quoted-string patterns, so those lines are effectively skipped.
    assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# parse_brief
# ---------------------------------------------------------------------------

def test_parse_brief_normal(tmp_path: Path) -> None:
    md = (
        "# Deploy new worker\n"
        "\n"
        "owner: alice\n"
        "status: active\n"
        "updated: 2026-04-01\n"
        "frontstage_disposition: proceed\n"
        "requested_operation: launch\n"
        "target_role: koder\n"
        "target_instance: seat-1\n"
        "template_id: tpl-99\n"
        "reason: scaling\n"
        "resume_task: T-42\n"
        "\n"
        "## \u7528\u6237\u6458\u8981\n"
        "\n"
        "This is the summary.\n"
        "Second line.\n"
        "\n"
        "## Other section\n"
    )
    f = tmp_path / "PLANNER_BRIEF.md"
    f.write_text(md, encoding="utf-8")
    result = parse_brief(f)
    assert result["title"] == "Deploy new worker"
    assert result["owner"] == "alice"
    assert result["status"] == "active"
    assert result["updated"] == "2026-04-01"
    assert result["frontstage_disposition"] == "proceed"
    assert result["requested_operation"] == "launch"
    assert result["target_role"] == "koder"
    assert result["target_instance"] == "seat-1"
    assert result["template_id"] == "tpl-99"
    assert result["reason"] == "scaling"
    assert result["resume_task"] == "T-42"
    assert result["user_summary"] == "This is the summary. Second line."


def test_parse_brief_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "PLANNER_BRIEF.md"
    f.write_text("", encoding="utf-8")
    result = parse_brief(f)
    assert result["title"] == ""
    assert result["owner"] == ""
    assert result["user_summary"] == ""


def test_parse_brief_nonexistent(tmp_path: Path) -> None:
    result = parse_brief(tmp_path / "does_not_exist.md")
    assert result["title"] == ""
    assert result["status"] == ""


# ---------------------------------------------------------------------------
# parse_pending_frontstage / parse_pending_item
# ---------------------------------------------------------------------------

_PENDING_MD = """\
# PENDING_FRONTSTAGE

## \u5b57\u6bb5\u5b9a\u4e49

ignored preamble

## \u5f85\u5904\u7406\u4e8b\u9879

### PF-001
id: PF-001
type: decision
related_task: T-10
summary: Pick a database
planner_recommendation: Use Postgres
koder_default_action: skip
user_input_needed: true
blocking: true
options:
  - Postgres
  - SQLite
resolved: false
resolved_by:
resolved_at:
resolution:

### PF-002
id: PF-002
type: clarification
related_task: T-20
summary: Confirm API version
planner_recommendation: Use v2
koder_default_action: use-v2
user_input_needed: false
blocking: false
options:
  - v1
  - v2
resolved: true
resolved_by: koder
resolved_at: 2026-04-01T00:00:00Z
resolution: v2 selected

## \u5df2\u5f52\u6863

"""


def test_parse_pending_frontstage_normal(tmp_path: Path) -> None:
    f = tmp_path / "PENDING_FRONTSTAGE.md"
    f.write_text(_PENDING_MD, encoding="utf-8")
    items = parse_pending_frontstage(f)
    assert len(items) == 2
    first = items[0]
    assert first.item_id == "PF-001"
    assert first.item_type == "decision"
    assert first.related_task == "T-10"
    assert first.summary == "Pick a database"
    assert first.user_input_needed is True
    assert first.blocking is True
    assert first.options == ["Postgres", "SQLite"]
    assert first.resolved is False
    assert first.section == "pending"

    second = items[1]
    assert second.item_id == "PF-002"
    assert second.resolved is True
    assert second.resolved_by == "koder"
    assert second.section == "pending"


def test_parse_pending_frontstage_empty(tmp_path: Path) -> None:
    f = tmp_path / "PENDING_FRONTSTAGE.md"
    f.write_text("", encoding="utf-8")
    assert parse_pending_frontstage(f) == []


def test_parse_pending_frontstage_nonexistent(tmp_path: Path) -> None:
    assert parse_pending_frontstage(tmp_path / "nope.md") == []


# ---------------------------------------------------------------------------
# render_pending_item
# ---------------------------------------------------------------------------

def test_render_pending_item_contains_fields() -> None:
    item = PendingFrontstageItem(
        item_id="PF-099",
        item_type="decision",
        related_task="T-5",
        summary="Choose colour",
        planner_recommendation="blue",
        koder_default_action="skip",
        user_input_needed=True,
        blocking=False,
        options=["red", "blue"],
        resolved=False,
        resolved_by="",
        resolved_at="",
        resolution="",
        section="pending",
    )
    lines = render_pending_item(item)
    text = "\n".join(lines)
    assert "### PF-099" in text
    assert "type: decision" in text
    assert "related_task: T-5" in text
    assert "summary: Choose colour" in text
    assert "user_input_needed: true" in text
    assert "blocking: false" in text
    assert "- red" in text
    assert "- blue" in text
    assert "resolved: false" in text


# ---------------------------------------------------------------------------
# write_pending_frontstage round-trip
# ---------------------------------------------------------------------------

def test_write_then_parse_round_trip(tmp_path: Path) -> None:
    items = [
        PendingFrontstageItem(
            item_id="PF-100",
            item_type="clarification",
            related_task="T-77",
            summary="Which endpoint?",
            planner_recommendation="/v3",
            koder_default_action="use-v3",
            user_input_needed=False,
            blocking=False,
            options=["/v2", "/v3"],
            resolved=False,
            resolved_by="",
            resolved_at="",
            resolution="",
            section="pending",
        ),
        PendingFrontstageItem(
            item_id="PF-101",
            item_type="decision",
            related_task="T-78",
            summary="Archived item",
            planner_recommendation="done",
            koder_default_action="noop",
            user_input_needed=False,
            blocking=False,
            options=[],
            resolved=True,
            resolved_by="user",
            resolved_at="2026-04-10T12:00:00Z",
            resolution="accepted",
            section="pending",
        ),
    ]
    f = tmp_path / "PENDING_FRONTSTAGE.md"
    write_pending_frontstage(f, items)
    assert f.exists()

    parsed = parse_pending_frontstage(f)
    # PF-100 is pending (not resolved), PF-101 is resolved so lands in archived.
    pending = [i for i in parsed if i.section == "pending"]
    archived = [i for i in parsed if i.section == "archived"]
    assert len(pending) == 1
    assert pending[0].item_id == "PF-100"
    assert pending[0].options == ["/v2", "/v3"]
    assert len(archived) == 1
    assert archived[0].item_id == "PF-101"
    assert archived[0].resolved is True
    assert archived[0].resolution == "accepted"


# ---------------------------------------------------------------------------
# serialize_adapter_result
# ---------------------------------------------------------------------------

def test_serialize_adapter_result() -> None:
    r = AdapterResult(
        command=["echo", "hello"],
        returncode=0,
        stdout="hello\n",
        stderr="",
    )
    d = serialize_adapter_result(r)
    assert d == {
        "command": ["echo", "hello"],
        "returncode": 0,
        "stdout": "hello\n",
        "stderr": "",
    }


# ---------------------------------------------------------------------------
# AdapterResult.ok
# ---------------------------------------------------------------------------

def test_adapter_result_ok_true() -> None:
    r = AdapterResult(command=["true"], returncode=0, stdout="", stderr="")
    assert r.ok is True


def test_adapter_result_ok_false() -> None:
    r = AdapterResult(command=["false"], returncode=1, stdout="", stderr="err")
    assert r.ok is False
