#!/usr/bin/env python3
"""patrol_pipeline_sla.py — Pipeline SLA + integrity + skill-authorization audit.

Caller: `patrol` (read-only Asset Guardian seat). Mutates nothing.

Three independent check families, each runnable alone or in combination:

sla
---
- Scan PROJECT_INDEX.lanes for state in (spawned, generating)
- Flag any older than --sla-threshold-mins (default 30)
- Reasoning: a lane stuck in spawned/generating means the target seat
  failed to deposit; auto mode should escalate, manual mode should alert

integrity
---------
- For each asset in PROJECT_INDEX.assets, verify path exists + file size
  matches recorded `file_size`
- For each lane in PROJECT_INDEX.lanes, verify lanes/<lane-id>.toml exists
- Never reads asset content (no-image-policy); only stat()

authorization
-------------
- Scan generation_log.jsonl for events whose actor doesn't match the
  protocol's seat-operation matrix (e.g. `writer` calling spawn_lane,
  `patrol` calling pick_winner, `builder-image` depositing video)
- Cross-references the matrix in cartooner-harness/SKILL.md
- Soft enforcement: emits a report; v1 doesn't block

Exit
----
- 0 if --check passed (no anomalies)
- 2 if anomalies detected (so callers / CI can branch on it)
- 1 on validation / read failure (fail-closed)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import _common as common  # noqa: E402

VALID_CHECKS = ("sla", "integrity", "authorization", "all")
VALID_FORMATS = ("text", "json")

# Operation-level authorization (which seat may emit which event).
# Mirrors SKILL.md "Skill Authorization Matrix" and per-seat user-direct
# table; this is the audit ground truth.
EVENT_ALLOWED_ACTORS: dict[str, set[str]] = {
    "lane_spawned": {"memory", "builder-image", "builder-av", "writer"},
    "asset_deposited": {"builder-image", "builder-av", "writer"},
    "pick_winner": {"user", "memory_acting_director"},
    "iterate_prompt": {"user", "memory_acting_director"},
    "share_style_bible": {"user", "memory_acting_director"},
    "set_automation_mode": {"user", "memory_acting_director"},
    "escalate_to_producer": {"memory_acting_director", "patrol"},
    # report_to_memory uses "actor=triggered_by" so it can be user / memory / patrol
    "user_direct_request": {"user"},
    "lane_completed": {"user", "memory", "patrol", "builder-image", "builder-av", "writer"},
    "shot_list_revised": {"user", "memory", "writer", "builder-av"},
    "subagent_started": {"builder-image", "builder-av"},
    "subagent_spawned": {"builder-image", "builder-av"},
    "subagent_completed": {"builder-image", "builder-av"},
    "subagent_failed": {"builder-image", "builder-av"},
    # cross-seat dispatch protocol (communication-protocol.md §6)
    "brief_dispatched": {"memory"},          # only memory dispatches; user-direct self-dispatch logs as actor=<seat> + triggered_by=user_direct
    "brief_delivered": {"writer", "builder-image", "builder-av"},
    "brief_failed": {"writer", "builder-image", "builder-av"},
}

ASSET_TYPE_BY_ACTOR: dict[str, set[str]] = {
    "builder-image": {"image"},
    "builder-av": {"video", "audio"},
    "writer": {"text"},
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="patrol_pipeline_sla")
    p.add_argument("--project", required=True)
    p.add_argument("--check", default="all", choices=VALID_CHECKS)
    p.add_argument("--sla-threshold-mins", type=float, default=30.0)
    p.add_argument("--format", default="text", choices=VALID_FORMATS)
    p.add_argument("--exit-zero-on-anomaly", action="store_true",
                   help="Always exit 0 even if anomalies found (use when invoked by "
                        "memory which logs results without aborting flow)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    project_path = common.project_root(args.project)
    if not (project_path / "PROJECT_INDEX.json").exists():
        sys.stderr.write(f"[patrol] no PROJECT_INDEX at {project_path}\n")
        return 1

    index = common.load_project_index(args.project)

    report: dict[str, Any] = {
        "project": args.project,
        "checked_at": common.now_iso(),
        "checks_run": [],
        "anomalies": [],
    }

    if args.check in ("sla", "all"):
        report["checks_run"].append("sla")
        report["anomalies"].extend(
            _check_sla(args.project, index, args.sla_threshold_mins)
        )

    if args.check in ("integrity", "all"):
        report["checks_run"].append("integrity")
        report["anomalies"].extend(_check_integrity(args.project, index))

    if args.check in ("authorization", "all"):
        report["checks_run"].append("authorization")
        report["anomalies"].extend(_check_authorization(args.project))

    if args.format == "json":
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        for line in _render_text(report):
            sys.stdout.write(line + "\n")

    if report["anomalies"] and not args.exit_zero_on_anomaly:
        return 2
    return 0


def _check_sla(
    project: str,
    index: dict[str, Any],
    threshold_mins: float,
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    now = datetime.now(tz=None).astimezone()

    for lane_id, lane in (index.get("lanes") or {}).items():
        state = lane.get("state")
        if state not in ("spawned", "generating"):
            continue
        created = lane.get("created_at")
        if not created:
            anomalies.append({
                "check": "sla",
                "severity": "warn",
                "lane_id": lane_id,
                "reason": "lane has no created_at; cannot age-check",
            })
            continue
        try:
            ts = datetime.fromisoformat(created)
            if ts.tzinfo is None:
                ts = ts.astimezone()
        except ValueError:
            anomalies.append({
                "check": "sla",
                "severity": "warn",
                "lane_id": lane_id,
                "reason": f"lane has invalid created_at: {created!r}",
            })
            continue

        age_mins = (now - ts).total_seconds() / 60.0
        if age_mins > threshold_mins:
            anomalies.append({
                "check": "sla",
                "severity": "alert",
                "lane_id": lane_id,
                "state": state,
                "age_mins": round(age_mins, 1),
                "threshold_mins": threshold_mins,
                "reason": f"lane stuck in state={state} for {age_mins:.1f} min "
                          f"(> threshold {threshold_mins} min)",
            })
    return anomalies


def _check_integrity(project: str, index: dict[str, Any]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    project_path = common.project_root(project)

    for asset_id, asset in (index.get("assets") or {}).items():
        path_str = asset.get("path")
        if not path_str:
            anomalies.append({
                "check": "integrity",
                "severity": "alert",
                "asset_id": asset_id,
                "reason": "asset has no path field",
            })
            continue
        path = Path(path_str)
        if not path.exists():
            anomalies.append({
                "check": "integrity",
                "severity": "alert",
                "asset_id": asset_id,
                "path": path_str,
                "reason": "asset file missing on disk",
            })
            continue
        if not path.is_file():
            anomalies.append({
                "check": "integrity",
                "severity": "alert",
                "asset_id": asset_id,
                "path": path_str,
                "reason": "asset path is not a regular file",
            })
            continue
        recorded_size = asset.get("file_size")
        actual_size = path.stat().st_size
        if recorded_size is not None and recorded_size != actual_size:
            anomalies.append({
                "check": "integrity",
                "severity": "warn",
                "asset_id": asset_id,
                "path": path_str,
                "recorded_size": recorded_size,
                "actual_size": actual_size,
                "reason": "asset file size differs from recorded value",
            })

    for lane_id in (index.get("lanes") or {}).keys():
        lane_path = project_path / "lanes" / f"{lane_id}.toml"
        if not lane_path.exists():
            anomalies.append({
                "check": "integrity",
                "severity": "alert",
                "lane_id": lane_id,
                "reason": "lane TOML missing on disk (PROJECT_INDEX out of sync)",
            })
    return anomalies


def _check_authorization(project: str) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    log_path = common.project_root(project) / "generation_log.jsonl"
    if not log_path.exists():
        return anomalies

    with log_path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as e:
                anomalies.append({
                    "check": "authorization",
                    "severity": "warn",
                    "line": line_no,
                    "reason": f"unparseable generation_log line: {e}",
                })
                continue

            ev_name = event.get("event")
            actor = event.get("actor")
            allowed = EVENT_ALLOWED_ACTORS.get(ev_name)
            if allowed is not None and actor and actor not in allowed:
                anomalies.append({
                    "check": "authorization",
                    "severity": "alert",
                    "line": line_no,
                    "event": ev_name,
                    "actor": actor,
                    "allowed": sorted(allowed),
                    "reason": f"actor {actor!r} not authorized for event {ev_name!r}",
                })

            if ev_name == "asset_deposited":
                asset_type = event.get("asset_type")
                allowed_types = ASSET_TYPE_BY_ACTOR.get(actor or "", set())
                if asset_type and asset_type not in allowed_types:
                    anomalies.append({
                        "check": "authorization",
                        "severity": "alert",
                        "line": line_no,
                        "event": ev_name,
                        "actor": actor,
                        "asset_type": asset_type,
                        "reason": f"actor {actor!r} not authorized for asset_type "
                                  f"{asset_type!r}",
                    })
    return anomalies


def _render_text(report: dict[str, Any]) -> list[str]:
    out: list[str] = []
    out.append(
        f"patrol report — project={report['project']} "
        f"checked_at={report['checked_at']}"
    )
    out.append(f"  checks: {', '.join(report['checks_run'])}")
    anomalies = report["anomalies"]
    if not anomalies:
        out.append("  result: clean (no anomalies)")
        return out
    out.append(f"  result: {len(anomalies)} anomalies")
    for a in anomalies:
        check = a.get("check", "?")
        sev = a.get("severity", "?")
        reason = a.get("reason", "?")
        loc_bits: list[str] = []
        for k in ("lane_id", "asset_id", "line", "event", "actor"):
            v = a.get(k)
            if v is not None:
                loc_bits.append(f"{k}={v}")
        loc = " ".join(loc_bits) if loc_bits else ""
        out.append(f"    [{sev}] {check}: {reason} {loc}".rstrip())
    return out


if __name__ == "__main__":
    sys.exit(main())
