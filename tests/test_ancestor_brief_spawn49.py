from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_BRIEF_TEMPLATE = _REPO / "core" / "templates" / "ancestor-brief.template.md"


def test_spawn49_brief_uses_agent_admin_session_start_engineer() -> None:
    text = _BRIEF_TEMPLATE.read_text(encoding="utf-8")

    assert "scripts/wait-for-seat.sh" in text
    assert "~/" not in text
    assert "${AGENT_HOME}/.agents/memory/machine/" in text
    assert "### B2.5 — Bootstrap machine tenants + ancestor 快速概览" in text
    assert "### B2.6" not in text
    assert "tmux send-keys -t '=machine-memory-claude' \"$MEMORY_PROMPT\" Enter" not in text
    assert "${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-bootstrap-report.md" not in text
    assert "MEMORY_REPORT_READY" not in text
    assert "### B5 — Feishu group binding（ancestor 自读 + agent-driven 新建群流程）" in text
    assert "agent_admin.py project binding-list" in text
    assert "${AGENT_HOME}/.agents/tasks/*/PROJECT_BINDING.toml" in text
    assert "${AGENT_HOME}/.lark-cli/config.json" in text
    assert "Ancestor 自读结果：" in text
    assert "${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-feishu-binding-report.md" not in text
    assert "FEISHU_REPORT_READY" not in text
    assert "agent_admin.py project bind" in text
    assert "本机可用 openclaw agent" in text
    assert "创建新群" in text
    assert "--feishu-bot-account <selected_agent_name>" in text
    assert "--require-mention" in text
    assert "${AGENT_HOME}/.agents/memory/learnings/${PROJECT_NAME}-phase-a-decisions.md" in text
    assert "不要 tmux send-keys 给 memory" in text
    assert "${AGENT_HOME}/.openclaw/workspace.toml" in text
    assert "agent_admin.py session start-engineer ${seat} --project ${PROJECT_NAME}" in text
    assert "agent_admin.py session switch-harness --project ${PROJECT_NAME} --engineer ${seat}" in text
    assert "agent_admin.py session-name ${seat} --project ${PROJECT_NAME}" in text
    assert "agent-launcher.sh --headless --engineer ${seat} --project ${PROJECT_NAME}" not in text
