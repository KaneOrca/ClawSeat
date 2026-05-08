"""Peer protocol contract tests.

Covers the external peer bundle layout, peer liveness states, MiniMax
readiness diagnostics, the memory-side orphan KB synthesis path, and a
regression guard that the canonical handoff script stayed untouched.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MEMORY_SCRIPTS = _REPO_ROOT / "core" / "skills" / "memory-oracle" / "scripts"
if str(_MEMORY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_MEMORY_SCRIPTS))

import scan_index


REPO_ROOT = _REPO_ROOT
PEER_SCRIPT_DIR = REPO_ROOT / "core" / "skills" / "clawseat-peer" / "scripts"
PEER_DELIVER = PEER_SCRIPT_DIR / "peer_deliver.py"
PEER_WATCHDOG = PEER_SCRIPT_DIR / "peer_watchdog.py"
MINIMAX_READINESS = PEER_SCRIPT_DIR / "minimax_readiness.py"
MEMORY_WRITE = REPO_ROOT / "core" / "skills" / "memory-oracle" / "scripts" / "memory_write.py"
COMPLETE_HANDOFF = REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "complete_handoff.py"


def _script_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CLAWSEAT_REAL_HOME": str(home),
            "AGENT_HOME": str(home),
        }
    )
    return env


def _run(script: Path, *args: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _touch_all_files(root: Path, age_seconds: int) -> None:
    stamp = time.time() - age_seconds
    for path in root.rglob("*"):
        if path.is_file():
            os.utime(path, (stamp, stamp))


def _parse_json(output: str) -> dict[str, object]:
    return json.loads(output.strip())


def _deliver_peer_bundle(
    tmp_path: Path,
    *,
    peer_id: str = "peer-195404",
    task_id: str = "DM-PEER-001",
    summary: str = "peer bundle delivered",
    status: str = "submitted",
    task_text: str | None = None,
    receipt_verdict: str = "SUBMITTED",
    receipt_notes: str = "",
    heartbeat_state: str = "progressing",
) -> tuple[dict[str, object], Path, Path]:
    env = _script_env(tmp_path)
    args = [
        "--project", "install",
        "--peer-id", peer_id,
        "--task-id", task_id,
        "--status", status,
        "--summary", summary,
        "--receipt-verdict", receipt_verdict,
        "--heartbeat-state", heartbeat_state,
    ]
    if receipt_notes:
        args.extend(["--receipt-notes", receipt_notes])
    if task_text is not None:
        args.extend(["--task-text", task_text])
    proc = _run(PEER_DELIVER, *args, env=env)
    assert proc.returncode == 0, proc.stderr
    payload = _parse_json(proc.stdout)
    peer_root = Path(payload["peer_root"])
    task_dir = Path(payload["task_dir"])
    return payload, peer_root, task_dir


def _run_watchdog(tmp_path: Path, peer_id: str, task_id: str) -> subprocess.CompletedProcess[str]:
    env = _script_env(tmp_path)
    return _run(
        PEER_WATCHDOG,
        "--project", "install",
        "--peer-id", peer_id,
        "--task-id", task_id,
        env=env,
    )


def test_peer_deliver_writes_expected_bundle_layout_and_frontmatter(tmp_path: Path) -> None:
    payload, peer_root, task_dir = _deliver_peer_bundle(tmp_path)

    assert payload["project"] == "install"
    assert payload["peer_id"] == "peer-195404"
    assert payload["task_id"] == "DM-PEER-001"
    assert payload["status"] == "submitted"
    assert Path(payload["delivery_md"]).exists()
    assert Path(payload["receipt_json"]).exists()
    assert Path(payload["heartbeat_json"]).exists()
    assert Path(payload["task_md"]).exists()
    assert peer_root == Path(payload["peer_root"])
    assert task_dir == peer_root / "tasks" / "DM-PEER-001"

    meta = json.loads((peer_root / "meta.json").read_text(encoding="utf-8"))
    heartbeat = json.loads((peer_root / "heartbeat.json").read_text(encoding="utf-8"))
    receipt = json.loads((task_dir / "receipt.json").read_text(encoding="utf-8"))
    delivery = scan_index.parse_frontmatter(task_dir / "DELIVERY.md")
    task = scan_index.parse_frontmatter(task_dir / "TASK.md")

    assert meta["peer_id"] == "peer-195404"
    assert meta["project"] == "install"
    assert meta["status"] == "active"
    assert heartbeat["state"] == "progressing"
    assert heartbeat["peer_id"] == "peer-195404"
    assert receipt == {
        "acknowledged_at": receipt["acknowledged_at"],
        "acknowledged_by": "peer-195404",
        "notes": "peer bundle delivered",
        "verdict": "SUBMITTED",
    }
    assert delivery is not None
    assert delivery["peer_id"] == "peer-195404"
    assert delivery["task_id"] == "DM-PEER-001"
    assert delivery["status"] == "submitted"
    assert delivery["summary"] == "peer bundle delivered"
    assert delivery["project"] == "install"
    assert task is not None
    assert task["peer_id"] == "peer-195404"
    assert task["task_id"] == "DM-PEER-001"
    assert "No task brief was supplied" in (task_dir / "TASK.md").read_text(encoding="utf-8")


def test_peer_deliver_honors_inline_task_text_and_receipt_overrides(tmp_path: Path) -> None:
    task_text = "raw task body that should stay in TASK.md"
    payload, peer_root, task_dir = _deliver_peer_bundle(
        tmp_path,
        task_id="DM-PEER-002",
        summary="inline task text delivered",
        task_text=task_text,
        receipt_verdict="PASS",
        receipt_notes="memory acknowledged",
    )

    assert payload["task_id"] == "DM-PEER-002"
    assert (task_dir / "TASK.md").read_text(encoding="utf-8") == task_text + "\n"
    receipt = json.loads((task_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["verdict"] == "PASS"
    assert receipt["notes"] == "memory acknowledged"
    assert scan_index.parse_frontmatter(task_dir / "DELIVERY.md")["summary"] == "inline task text delivered"
    assert peer_root == Path(payload["peer_root"])


def test_peer_watchdog_reports_progressing_for_fresh_bundle(tmp_path: Path) -> None:
    _, _, task_dir = _deliver_peer_bundle(tmp_path, task_id="DM-PEER-003")

    proc = _run_watchdog(tmp_path, "peer-195404", "DM-PEER-003")

    payload = _parse_json(proc.stdout)
    assert proc.returncode == 0
    assert payload["state"] == "progressing"
    assert payload["latest_path"] is not None
    assert Path(payload["latest_path"]).is_file()
    assert task_dir.exists()


def test_peer_watchdog_reports_idle_for_stale_bundle(tmp_path: Path) -> None:
    _, peer_root, _ = _deliver_peer_bundle(tmp_path, task_id="DM-PEER-004")
    _touch_all_files(peer_root, age_seconds=300)

    proc = _run_watchdog(tmp_path, "peer-195404", "DM-PEER-004")

    payload = _parse_json(proc.stdout)
    assert proc.returncode == 1
    assert payload["state"] == "idle"
    assert payload["latest_age_seconds"] is not None
    assert float(payload["latest_age_seconds"]) >= 299


def test_peer_watchdog_reports_stalled_for_old_bundle(tmp_path: Path) -> None:
    _, peer_root, _ = _deliver_peer_bundle(tmp_path, task_id="DM-PEER-005")
    _touch_all_files(peer_root, age_seconds=1200)

    proc = _run_watchdog(tmp_path, "peer-195404", "DM-PEER-005")

    payload = _parse_json(proc.stdout)
    assert proc.returncode == 2
    assert payload["state"] == "stalled"
    assert float(payload["latest_age_seconds"]) >= 1199


def test_minimax_readiness_reports_ready_without_token_leak(tmp_path: Path) -> None:
    secret_file = tmp_path / "minimax.env"
    secret_file.write_text(
        "MINIMAX_API_KEY=sk-test-123\n"
        "MINIMAX_BASE_URL=https://example.invalid\n"
        "SECONDARY=pk-test-456\n",
        encoding="utf-8",
    )

    proc = _run(
        MINIMAX_READINESS,
        "--path", str(secret_file),
        "--category", "api_key",
    )

    payload = _parse_json(proc.stdout)
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0
    assert payload["readiness"] == "ready"
    assert payload["category"] == "api_key"
    assert re.search(r"(sk-|pk-|token=|key-)", combined) is None


def test_minimax_readiness_reports_missing_for_absent_path(tmp_path: Path) -> None:
    proc = _run(
        MINIMAX_READINESS,
        "--path", str(tmp_path / "does-not-exist.env"),
        "--category", "api_key",
    )

    payload = _parse_json(proc.stdout)
    assert proc.returncode == 0
    assert payload["readiness"] == "missing"
    assert payload["category"] == "api_key"


def test_minimax_readiness_reports_unreadable_for_bad_bytes(tmp_path: Path) -> None:
    unreadable = tmp_path / "credentials.toml"
    unreadable.write_bytes(b"\xff\xfe\x00")

    proc = _run(
        MINIMAX_READINESS,
        "--path", str(unreadable),
        "--category", "config",
    )

    payload = _parse_json(proc.stdout)
    assert proc.returncode == 0
    assert payload["readiness"] == "unreadable"
    assert payload["category"] == "config"


def test_peer_delivery_can_be_synthesized_into_orphan_finding(tmp_path: Path) -> None:
    raw_task_text = "raw peer task body that must not be copied verbatim"
    _, peer_root, task_dir = _deliver_peer_bundle(
        tmp_path,
        task_id="DM-PEER-006",
        summary="peer delivery ready for orphan synthesis",
        task_text=raw_task_text,
        receipt_verdict="PASS",
        receipt_notes="ACK",
    )

    delivery_path = task_dir / "DELIVERY.md"
    delivery_frontmatter = scan_index.parse_frontmatter(delivery_path)
    assert delivery_frontmatter is not None

    synthesized = tmp_path / "peer-orphan-note.md"
    synthesized.write_text(
        "\n".join(
            [
                "---",
                'schema_version: 1',
                'format: "markdown_note"',
                'id: "peer-synthesis-001"',
                'project: "install"',
                'kind: "finding"',
                'title: "Peer delivery synthesis"',
                'author: "memory"',
                f'ts: "{datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}"',
                'created_at: "2026-05-08T00:00:00Z"',
                'filename_stamp: "peer-synthesis"',
                'content_source: "file"',
                "---",
                "",
                f"Peer {delivery_frontmatter['peer_id']} delivered {delivery_frontmatter['task_id']}.",
                f"Summary: {delivery_frontmatter['summary']}",
                f"Receipt: {(task_dir / 'receipt.json').name}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    memory_root = tmp_path / "memory"
    proc = _run(
        MEMORY_WRITE,
        "--kind", "finding",
        "--project", "install",
        "--title", "Peer delivery synthesis",
        "--author", "memory",
        "--content-file", str(synthesized),
        "--memory-dir", str(memory_root),
    )

    note_path = Path(proc.stdout.strip())
    note_text = note_path.read_text(encoding="utf-8")
    note_frontmatter = scan_index.parse_frontmatter(note_path)

    assert proc.returncode == 0
    assert "/projects/install/finding/" in str(note_path)
    assert note_frontmatter is not None
    assert note_frontmatter["kind"] == "finding"
    assert note_frontmatter["author"] == "memory"
    assert "peer-195404" in note_text
    assert "peer delivery ready for orphan synthesis" in note_text
    assert raw_task_text not in note_text


def test_complete_handoff_script_is_unchanged() -> None:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "diff",
            "--",
            "core/skills/gstack-harness/scripts/complete_handoff.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert proc.stderr.strip() == ""
