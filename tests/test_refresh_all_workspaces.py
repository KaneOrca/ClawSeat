from __future__ import annotations

import os
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import refresh_all_workspaces  # noqa: E402


def _write_stub_agent_admin(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os, sys",
                "from pathlib import Path",
                "project = sys.argv[sys.argv.index('--project') + 1]",
                "workspace = Path(os.environ['HOME']) / '.agents' / 'workspaces' / project / 'builder'",
                "workspace.mkdir(parents=True, exist_ok=True)",
                "target = workspace / 'AGENTS.md'",
                "target.write_text('\\n'.join([",
                "    '# AGENTS.md',",
                "    'canonical dispatch',",
                "    'dispatch_task.py',",
                "    'complete_handoff.py',",
                "    'Fan-out Default',",
                "    '2+ independent sub-goals must fan-out',",
                "    '',",
                "]), encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_refresh_all_workspaces_dry_run_lists_each_project(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    for project in ("alpha", "beta"):
        (home / ".agents" / "projects" / project).mkdir(parents=True)
    stub = tmp_path / "agent_admin.py"
    _write_stub_agent_admin(stub)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAWSEAT_REAL_HOME", raising=False)
    monkeypatch.setenv("CLAWSEAT_AGENT_ADMIN", str(stub))

    assert refresh_all_workspaces.main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "--project alpha --yes" in out
    assert "--project beta --yes" in out
    assert "regenerate-workspace --all-seats" in out


def test_refresh_all_workspaces_real_run_updates_workspace_with_canonical_surface(
    tmp_path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    (home / ".agents" / "projects" / "alpha").mkdir(parents=True)
    workspace = home / ".agents" / "workspaces" / "alpha" / "builder"
    workspace.mkdir(parents=True)
    target = workspace / "AGENTS.md"
    target.write_text("old workspace\n", encoding="utf-8")
    os.utime(target, (1, 1))
    before = target.stat().st_mtime
    stub = tmp_path / "agent_admin.py"
    _write_stub_agent_admin(stub)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAWSEAT_REAL_HOME", raising=False)
    monkeypatch.setenv("CLAWSEAT_AGENT_ADMIN", str(stub))

    assert refresh_all_workspaces.main(["--projects", "alpha"]) == 0

    text = target.read_text(encoding="utf-8")
    assert target.stat().st_mtime > before
    assert "canonical dispatch" in text
    assert "complete_handoff.py" in text
    assert "Fan-out Default" in text
    assert "fan-out" in text
