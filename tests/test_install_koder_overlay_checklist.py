"""Tests for T13: install_koder_overlay post-install Feishu checklist.

Covers:
  1. test_checklist_prints_when_appid_found — appId in openclaw.json → URL + scopes + version
  2. test_checklist_warns_when_appid_placeholder — placeholder appId → warning text
  3. test_no_feishu_checklist_flag_disables_print — --no-feishu-checklist → no output
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_OVERLAY_SCRIPT = _REPO / "shells" / "openclaw-plugin"
if str(_OVERLAY_SCRIPT) not in sys.path:
    sys.path.insert(0, str(_OVERLAY_SCRIPT))

from install_koder_overlay import _print_feishu_checklist, _FEISHU_PLACEHOLDER


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_openclaw_json(openclaw_home: Path, agent: str, app_id: str) -> None:
    openclaw_home.mkdir(parents=True, exist_ok=True)
    (openclaw_home / "openclaw.json").write_text(
        json.dumps({
            "channels": {
                "feishu": {
                    "accounts": {agent: {"appId": app_id}}
                }
            }
        }),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: appId found → URL and scopes printed
# ══════════════════════════════════════════════════════════════════════════════

def test_checklist_prints_when_appid_found(tmp_path, capsys):
    openclaw_home = tmp_path / ".openclaw"
    _write_openclaw_json(openclaw_home, "koder", "cli_a93c3968a3385bb5")

    _print_feishu_checklist("koder", openclaw_home, no_checklist=False)

    out = capsys.readouterr().out
    assert "Post-install Checklist" in out
    assert "cli_a93c3968a3385bb5" in out
    assert "https://open.feishu.cn/app/cli_a93c3968a3385bb5/event-subscription" in out
    assert "im:message.group_msg:receive" in out
    assert "2026.4.9" in out
    assert "feishu-bridge-setup.md" in out


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: placeholder appId → warning printed instead of URL
# ══════════════════════════════════════════════════════════════════════════════

def test_checklist_warns_when_appid_placeholder(tmp_path, capsys):
    openclaw_home = tmp_path / ".openclaw"
    _write_openclaw_json(openclaw_home, "koder", _FEISHU_PLACEHOLDER)

    _print_feishu_checklist("koder", openclaw_home, no_checklist=False)

    out = capsys.readouterr().out
    assert "Post-install Checklist" in out
    assert "appId 未配置" in out
    # Should NOT contain a real appId URL
    assert _FEISHU_PLACEHOLDER not in out or "WARNING" in out


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: --no-feishu-checklist disables all output
# ══════════════════════════════════════════════════════════════════════════════

def test_no_feishu_checklist_flag_disables_print(tmp_path, capsys):
    openclaw_home = tmp_path / ".openclaw"
    _write_openclaw_json(openclaw_home, "koder", "cli_abc123")

    _print_feishu_checklist("koder", openclaw_home, no_checklist=True)

    out = capsys.readouterr().out
    assert "Post-install Checklist" not in out
    assert "im:message" not in out
    assert out == "", f"expected empty output, got: {out!r}"
