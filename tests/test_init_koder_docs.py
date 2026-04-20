"""Regression guards for init_koder-generated workspace docs."""
from __future__ import annotations

import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "skills" / "clawseat-install" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import init_koder  # noqa: E402


def _rendered_workspace_docs() -> str:
    profile_path = Path("/tmp/install-profile.toml")
    spec = {"skills": [], "role_details": []}
    parts = [
        init_koder.render_tools_dispatch(_REPO),
        init_koder.render_tools_project(_REPO, heartbeat_owner="cartooner"),
        init_koder.render_tools_memory(_REPO, heartbeat_owner="cartooner"),
        init_koder.render_tools_install(_REPO),
        init_koder.render_memory(
            "install",
            profile_path,
            ["cartooner", "planner"],
            heartbeat_owner="cartooner",
            backend_seats=["planner"],
            default_backend_start_seats=["planner"],
        ),
        init_koder.render_agents(
            spec,
            _REPO,
            heartbeat_owner="cartooner",
            backend_seats=["planner"],
        ),
    ]
    return "\n".join(parts)


def test_init_koder_rendered_docs_have_no_local_user_hardcodes():
    content = _rendered_workspace_docs()
    forbidden = (
        "/Users/ywf/.openclaw",
        "/Users/ywf/.agents",
        "/Users/ywf/.gstack",
    )
    assert not any(token in content for token in forbidden)


def test_init_koder_memory_doc_uses_notify_channel():
    content = init_koder.render_tools_memory(_REPO, heartbeat_owner="cartooner")
    assert "notify_seat.py" in content
    assert "dispatch_task.py --target memory" in content


def test_init_koder_install_doc_uses_staged_openclaw_flow():
    content = init_koder.render_tools_install(_REPO)
    assert "install_bundled_skills.py" in content
    assert "install_koder_overlay.py --agent <agent>" in content
    assert "install_openclaw_bundle.py" not in content
