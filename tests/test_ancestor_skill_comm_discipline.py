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
    # Round-8 #6: `/patrol-tick` was a slash-command-looking token that Claude
    # Code's resolver rejects as "Unknown command". The **active invocation
    # form** must no longer appear — i.e. no `send-and-verify.sh ... ancestor
    # "/patrol-tick"` instruction and no bare `/patrol-tick` payload arg.
    # (Historical explanation text that *mentions* the deprecated token to
    # justify its removal is allowed — we only block live trigger patterns.)
    assert 'ancestor "/patrol-tick"' not in skill
    assert "ancestor '/patrol-tick'" not in plist
    assert 'ancestor "/patrol-tick"' not in plist
    # Round-8 #6: patrol is manual-by-default; LaunchAgent is opt-in via flag.
    assert "--enable-auto-patrol" in skill
    # Round-8 #6: plist payload must be the natural-language Phase-B request
    # that ancestor SKILL §3 recognizes semantically (bilingual).
    assert "Phase-B 稳态巡检" in plist
    assert "Phase-B patrol cycle" in plist
    # Existing canonical-send invariants still hold.
    assert "send-and-verify.sh" in plist
    assert "tmux send-keys -t '={PROJECT}-ancestor-{TOOL}'" not in plist
    assert "agentctl.sh' session-name ancestor --project '{PROJECT}'" in plist
    assert "={PROJECT}-ancestor-{TOOL}" not in plist
