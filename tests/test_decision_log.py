from __future__ import annotations

import importlib.util
import json
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "core" / "skills" / "socratic-requirements" / "scripts" / "decision-log.py"


def _load_decision_log():
    spec = importlib.util.spec_from_file_location("decision_log", _SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_append_creates_dir_and_jsonl(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    decision_log = _load_decision_log()

    record = decision_log.append_decision(
        "install",
        "task-1",
        "Dispatch builder",
        "Implementation lane is the fastest path.",
    )

    log_path = tmp_path / ".agents" / "projects" / "install" / "memory-data" / "decision-log.jsonl"
    assert log_path.is_file()
    assert json.loads(log_path.read_text(encoding="utf-8")) == record


def test_append_record_has_required_federated_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    decision_log = _load_decision_log()

    record = decision_log.append_decision(
        "install",
        "task-2",
        "Record dispatch",
        "Planner selected builder.",
        seat="memory",
        decision_type="dispatch",
    )

    for field in ("ts", "task_id", "project", "seat", "title", "detail"):
        assert field in record
    assert record["decision_type"] == "dispatch"
    assert record["auto_mode"] is True
    assert record["reason"] == "Planner selected builder."


def test_list_decisions_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    decision_log = _load_decision_log()

    for index in range(5):
        decision_log.append_decision("install", f"task-{index}", f"title {index}", f"detail {index}")

    records = decision_log.list_decisions("install", limit=2)
    assert [record["task_id"] for record in records] == ["task-3", "task-4"]


def test_get_project_list_reads_projects_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    registry = tmp_path / ".clawseat" / "projects.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "projects": {
                    "install": {"status": "active"},
                    "cartooner": {"status": "active"},
                },
            }
        ),
        encoding="utf-8",
    )
    decision_log = _load_decision_log()

    assert decision_log.get_project_list() == ["install", "cartooner"]


def test_decision_log_integration_install(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    decision_log = _load_decision_log()

    decision_log.append_decision("install", "task-a", "First decision", "Start Stage 2.")
    decision_log.append_decision("install", "task-b", "Second decision", "Continue data layer.")

    records = decision_log.list_decisions("install")
    assert len(records) == 2
    assert [record["title"] for record in records] == ["First decision", "Second decision"]
