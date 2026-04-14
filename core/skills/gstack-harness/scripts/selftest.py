#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[4]


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["python3", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != expect:
        raise RuntimeError(
            f"command failed: {' '.join(args)}\n"
            f"exit={result.returncode}\n"
            f"stdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )
    return result


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="gstack-harness-selftest-"))
    try:
        repo_root = temp_root / "repo"
        tasks_root = repo_root / ".tasks"
        handoff_dir = tasks_root / "patrol" / "handoffs"
        for seat in ("koder", "engineer-a", "engineer-b", "engineer-c", "engineer-d", "engineer-e"):
            (tasks_root / seat).mkdir(parents=True, exist_ok=True)
        handoff_dir.mkdir(parents=True, exist_ok=True)

        write(tasks_root / "PROJECT.md", "# Project\n")
        write(
            tasks_root / "TASKS.md",
            "# Tasks\n\n| ID | Title | Owner | Status | Notes |\n|----|-------|-------|--------|-------|\n",
        )
        write(tasks_root / "STATUS.md", "# Status\n")

        status_script = temp_root / "status.sh"
        write(
            status_script,
            "#!/bin/sh\n"
            "echo \"engineer-b: WORKING\"\n"
            "echo \"engineer-c: IDLE\"\n",
        )
        status_script.chmod(0o755)

        patrol_script = temp_root / "patrol.py"
        write(patrol_script, "print('no reminders')\n")

        heartbeat_receipt = temp_root / "workspaces" / "clawseat" / "koder" / "HEARTBEAT_RECEIPT.toml"
        write(heartbeat_receipt, "installed = true\n")

        profile = temp_root / "clawseat.toml"
        write(
            profile,
            "\n".join(
                [
                    'version = 1',
                    'profile_name = "clawseat-selftest"',
                    'template_name = "gstack-harness"',
                    'project_name = "clawseat-selftest"',
                    f'repo_root = "{repo_root}"',
                    f'tasks_root = "{tasks_root}"',
                    f'project_doc = "{tasks_root / "PROJECT.md"}"',
                    f'tasks_doc = "{tasks_root / "TASKS.md"}"',
                    f'status_doc = "{tasks_root / "STATUS.md"}"',
                    'send_script = "/usr/bin/true"',
                    f'status_script = "{status_script}"',
                    f'patrol_script = "{patrol_script}"',
                    f'agent_admin = "{REPO_ROOT / "core" / "scripts" / "agent_admin.py"}"',
                    f'workspace_root = "{temp_root / "workspaces" / "clawseat"}"',
                    f'handoff_dir = "{handoff_dir}"',
                    'heartbeat_owner = "koder"',
                    'active_loop_owner = "engineer-b"',
                    'default_notify_target = "engineer-b"',
                    f'heartbeat_receipt = "{heartbeat_receipt}"',
                    'seats = ["koder", "engineer-b", "engineer-a", "engineer-c", "engineer-d", "engineer-e"]',
                    'heartbeat_seats = ["koder"]',
                    '',
                    '[seat_roles]',
                    'koder = "frontstage-supervisor"',
                    'engineer-b = "planner-dispatcher"',
                    'engineer-a = "builder"',
                    'engineer-c = "reviewer"',
                    'engineer-d = "qa"',
                    'engineer-e = "designer"',
                    '',
                ]
            ),
        )

        workspace_root = temp_root / "workspaces" / "clawseat"
        koder_workspace = workspace_root / "koder"
        koder_workspace.mkdir(parents=True, exist_ok=True)
        write(
            koder_workspace / "WORKSPACE_CONTRACT.toml",
            "\n".join(
                [
                    'version = 1',
                    'seat_id = "koder"',
                    'project = "clawseat-selftest"',
                    'role = "frontstage-supervisor"',
                    'contract_fingerprint = "selftest-contract-fingerprint"',
                    "",
                ]
            ),
        )

        dispatch_task = ROOT / "dispatch_task.py"
        notify_seat = ROOT / "notify_seat.py"
        complete_handoff = ROOT / "complete_handoff.py"
        verify_handoff = ROOT / "verify_handoff.py"
        render_console = ROOT / "render_console.py"
        provision_heartbeat = ROOT / "provision_heartbeat.py"
        ack_contract = ROOT / "ack_contract.py"

        run(
            str(dispatch_task),
            "--profile",
            str(profile),
            "--source",
            "engineer-b",
            "--target",
            "engineer-c",
            "--task-id",
            "FE-SMOKE",
            "--title",
            "Smoke task",
            "--objective",
            "Review the change set",
        )
        todo_text = (tasks_root / "engineer-c" / "TODO.md").read_text(encoding="utf-8")
        if "source: engineer-b" not in todo_text or "reply_to: engineer-b" not in todo_text:
            raise RuntimeError("dispatch TODO missing source/reply_to fields")

        run(
            str(notify_seat),
            "--profile",
            str(profile),
            "--source",
            "koder",
            "--target",
            "engineer-b",
            "--task-id",
            "FE-NOTICE",
            "--kind",
            "unblock",
            "--reply-to",
            "koder",
            "--message",
            "Resume the mainline and consume the repaired chain.",
        )
        notice_receipt = json.loads((handoff_dir / "FE-NOTICE__koder__engineer-b.json").read_text(encoding="utf-8"))
        if notice_receipt["kind"] != "unblock":
            raise RuntimeError("notify_seat did not write the expected receipt kind")

        run(
            str(ack_contract),
            "--profile",
            str(profile),
            "--seat",
            "koder",
            "--ack-source",
            "selftest",
        )
        contract_receipt = (koder_workspace / "WORKSPACE_CONTRACT_RECEIPT.toml").read_text(encoding="utf-8")
        if 'contract_fingerprint = "selftest-contract-fingerprint"' not in contract_receipt:
            raise RuntimeError("ack_contract missing contract fingerprint")
        if 'ack_source = "selftest"' not in contract_receipt:
            raise RuntimeError("ack_contract missing ack source")

        stale_dispatch = run(
            str(verify_handoff),
            "--profile",
            str(profile),
            "--task-id",
            "FE-OTHER",
            "--source",
            "engineer-b",
            "--target",
            "engineer-c",
            "--json",
            expect=1,
        )
        stale_dispatch_payload = json.loads(stale_dispatch.stdout)
        if stale_dispatch_payload["assigned"]:
            raise RuntimeError("verify_handoff incorrectly marked a stale dispatch as assigned")

        run(
            str(verify_handoff),
            "--profile",
            str(profile),
            "--task-id",
            "FE-SMOKE",
            "--source",
            "engineer-b",
            "--target",
            "engineer-c",
            expect=1,
        )

        missing_verdict = subprocess.run(
            [
                "python3",
                str(complete_handoff),
                "--profile",
                str(profile),
                "--source",
                "engineer-c",
                "--target",
                "engineer-b",
                "--task-id",
                "FE-SMOKE",
                "--title",
                "Review result",
                "--summary",
                "Looks good.",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if missing_verdict.returncode == 0:
            raise RuntimeError("engineer-c completion unexpectedly succeeded without canonical verdict")

        run(
            str(complete_handoff),
            "--profile",
            str(profile),
            "--source",
            "engineer-c",
            "--target",
            "engineer-b",
            "--task-id",
            "FE-SMOKE",
            "--title",
            "Review result",
            "--summary",
            "Looks good.",
            "--verdict",
            "APPROVED",
        )
        delivery_text = (tasks_root / "engineer-c" / "DELIVERY.md").read_text(encoding="utf-8")
        if "owner: engineer-c" not in delivery_text or "target: engineer-b" not in delivery_text:
            raise RuntimeError("delivery missing owner/target fields")

        missing_frontstage_disposition = subprocess.run(
            [
                "python3",
                str(complete_handoff),
                "--profile",
                str(profile),
                "--source",
                "engineer-b",
                "--target",
                "koder",
                "--task-id",
                "FE-CLOSEOUT",
                "--title",
                "Planner closeout",
                "--summary",
                "Chain is done.",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if missing_frontstage_disposition.returncode == 0:
            raise RuntimeError("planner closeout unexpectedly succeeded without frontstage disposition")

        run(
            str(complete_handoff),
            "--profile",
            str(profile),
            "--source",
            "engineer-b",
            "--target",
            "koder",
            "--task-id",
            "FE-CLOSEOUT",
            "--title",
            "Planner closeout",
            "--summary",
            "Review and QA passed. We can keep moving.",
            "--frontstage-disposition",
            "AUTO_ADVANCE",
            "--user-summary",
            "Review and QA passed. We can keep moving.",
        )
        planner_delivery = (tasks_root / "engineer-b" / "DELIVERY.md").read_text(encoding="utf-8")
        if "FrontstageDisposition: AUTO_ADVANCE" not in planner_delivery:
            raise RuntimeError("planner closeout missing FrontstageDisposition")
        if "UserSummary: Review and QA passed. We can keep moving." not in planner_delivery:
            raise RuntimeError("planner closeout missing UserSummary")
        frontstage_todo = (tasks_root / "koder" / "TODO.md").read_text(encoding="utf-8")
        if "task_id: FE-CLOSEOUT" not in frontstage_todo:
            raise RuntimeError("planner closeout did not refresh frontstage TODO")
        if "reply_to: engineer-b" not in frontstage_todo:
            raise RuntimeError("frontstage TODO missing reply_to for planner closeout")
        if "FrontstageDisposition: AUTO_ADVANCE" not in frontstage_todo:
            raise RuntimeError("frontstage TODO missing disposition summary")
        planner_receipt = json.loads(
            (handoff_dir / "FE-CLOSEOUT__engineer-b__koder.json").read_text(encoding="utf-8")
        )
        if planner_receipt.get("frontstage_disposition") != "AUTO_ADVANCE":
            raise RuntimeError("planner closeout receipt missing frontstage disposition")
        if "notify_message" not in planner_receipt:
            raise RuntimeError("planner closeout receipt missing notify evidence")
        if "todo_path" not in planner_receipt:
            raise RuntimeError("planner closeout receipt missing frontstage todo path")

        run(
            str(verify_handoff),
            "--profile",
            str(profile),
            "--task-id",
            "FE-SMOKE",
            "--source",
            "engineer-c",
            "--target",
            "engineer-b",
            expect=1,
        )

        run(
            str(complete_handoff),
            "--profile",
            str(profile),
            "--source",
            "engineer-c",
            "--target",
            "engineer-b",
            "--task-id",
            "FE-SMOKE",
            "--ack-only",
        )

        healthy = run(
            str(verify_handoff),
            "--profile",
            str(profile),
            "--task-id",
            "FE-SMOKE",
            "--source",
            "engineer-c",
            "--target",
            "engineer-b",
            "--json",
        )
        heartbeat_skip = run(
            str(provision_heartbeat),
            "--profile",
            str(profile),
            "--seat",
            "engineer-b",
            "--dry-run",
        )
        console = run(str(render_console), "--profile", str(profile), "--json")
        console_payload = json.loads(console.stdout)
        if console_payload["heartbeat"]["configured"]:
            raise RuntimeError("render_console incorrectly treated an unverified heartbeat receipt as configured")

        result = {
            "temp_root": str(temp_root),
            "healthy_handoff": json.loads(healthy.stdout),
            "heartbeat_skip": heartbeat_skip.stdout.strip(),
            "console": console_payload,
            "missing_verdict_error": (missing_verdict.stderr or missing_verdict.stdout).strip(),
            "missing_frontstage_disposition_error": (
                missing_frontstage_disposition.stderr or missing_frontstage_disposition.stdout
            ).strip(),
            "notice_receipt": notice_receipt,
            "dispatch_todo": todo_text,
            "delivery_text": delivery_text,
            "planner_delivery": planner_delivery,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
