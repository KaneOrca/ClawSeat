from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import agent_admin_workspace as workspace  # noqa: E402


def _write_multi_profile(home: Path) -> Path:
    profile = home / ".agents" / "profiles" / "cartooner-profile-dynamic.toml"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        """
project_name = "cartooner"
repo_root = "/repo/cartooner"
seats = [
  "memory",
  "cartooner-front-planner",
  "cartooner-front-builder-ui",
  "cartooner-front-builder-state",
  "cartooner-front-reviewer",
]

[mode]
team_structure = "multi"
project_memory = "memory"

[teams]
cartooner-front = { seats = ["cartooner-front-planner", "cartooner-front-builder-ui", "cartooner-front-builder-state", "cartooner-front-reviewer"], team_type = "subteam", ownership_paths = ["apps/web/src/components/**", "apps/web/src/store/**"], scaling_policy = { max_builders = 3, reviewer_required_when_builders_gte = 2, overflow_action = "propose_new_subteam", reviewer_fallback = "planner" } }

[seat_roles]
memory = "project-memory"
cartooner-front-planner = "planner"
cartooner-front-builder-ui = "builder"
cartooner-front-builder-state = "builder"
cartooner-front-reviewer = "reviewer"

[seat_overrides.memory]
tool = "codex"
auth_mode = "oauth"
provider = "openai"

[seat_overrides.cartooner-front-planner]
tool = "claude"
auth_mode = "oauth_token"
provider = "anthropic"

[seat_overrides.cartooner-front-builder-ui]
tool = "codex"
auth_mode = "oauth"
provider = "openai"
instance = "ui"
purpose = "React surfaces and component integration"
capabilities = ["react", "tailwind", "electron-ui"]

[seat_overrides.cartooner-front-builder-state]
tool = "codex"
auth_mode = "oauth"
provider = "openai"
instance = "state"
purpose = "Zustand stores and IPC data flow"
capabilities = ["zustand", "ipc", "state"]

[seat_overrides.cartooner-front-reviewer]
tool = "codex"
auth_mode = "oauth"
provider = "openai"
""".lstrip(),
        encoding="utf-8",
    )
    return profile


def test_multi_team_planner_workspace_shows_team_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    profile = _write_multi_profile(home)
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(home))
    monkeypatch.setenv("HOME", str(home))

    session = SimpleNamespace(engineer_id="cartooner-front-planner")
    project = SimpleNamespace(name="cartooner", engineers=[], repo_root="/repo/cartooner")
    engineer = SimpleNamespace(role="planner")

    lines = workspace.render_project_seat_map_lines(session, project, engineer)
    text = "\n".join(lines)

    assert f"- Profile: `{profile}`" in text
    assert "- Your team: `cartooner-front`" in text
    assert "- Your seat: `cartooner-front-planner` (`planner`)" in text
    assert "`apps/web/src/components/**`" in text
    assert "`apps/web/src/store/**`" in text
    assert "`cartooner-front-builder-ui`" in text
    assert "capabilities: `react`, `tailwind`, `electron-ui`" in text
    assert "`cartooner-front-builder-state`" in text
    assert "## Builder Assignment Rules" in text
    assert "never dispatch to bare role `builder`" in text
    assert "exact `owner_seat`" in text
    assert "Reviewer gate: `cartooner-front-reviewer`" in text


def test_multi_team_scope_is_rendered_even_when_role_stub_is_dynamic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    _write_multi_profile(home)
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(home))
    monkeypatch.setenv("HOME", str(home))

    session = SimpleNamespace(engineer_id="cartooner-front-planner")
    project = SimpleNamespace(name="cartooner", engineers=[], repo_root="/repo/cartooner")
    engineer = SimpleNamespace(role="cartooner-front-planner")

    text = "\n".join(workspace.render_project_seat_map_lines(session, project, engineer))

    assert "- Your team: `cartooner-front`" in text
    assert "## Builder Assignment Rules" in text
