from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_ANCESTOR_SKILL = _REPO / "core" / "skills" / "clawseat-ancestor" / "SKILL.md"
_ANCESTOR_PLIST = _REPO / "core" / "templates" / "ancestor-patrol.plist.in"


def test_ancestor_skill_and_patrol_plist_use_send_and_verify_for_project_seat_messages() -> None:
    skill = _ANCESTOR_SKILL.read_text(encoding="utf-8")
    plist = _ANCESTOR_PLIST.read_text(encoding="utf-8")

    assert "### 5.2 跨 seat 文本通讯（canonical）" in skill
    assert "bash ${CLAWSEAT_ROOT}/core/shell-scripts/send-and-verify.sh" in skill
    assert "你自己 tmux send-keys 给 planner/builder/qa 发消息" in skill
    assert "tmux send-keys -t '=<project>-ancestor-<tool>' \"/patrol-tick\" Enter" not in skill
    assert "send-and-verify.sh" in plist
    assert "tmux send-keys -t '={PROJECT}-ancestor-{TOOL}'" not in plist
    assert "agentctl.sh' session-name ancestor --project '{PROJECT}'" in plist
    assert "={PROJECT}-ancestor-{TOOL}" not in plist
