#!/usr/bin/env python3
"""deposit_asset.py — Persist a generated asset with metadata only.

Caller: `builder-image` or `builder-av` after API generation completes.

no-image-policy
---------------
This script NEVER reads asset content. It only:
- stat()s the asset file for size + existence
- captures model-provided metadata (passed as --model-metadata JSON)
- captures generation params (prompt_l3, seed, model)

If you find yourself wanting to load image bytes here, you are violating
the protocol. See `references/no-image-policy.md`.

Effect
------
- Validates the lane exists and the actor matches the lane's seat
- Validates asset_type matches the actor (image -> builder-image only;
  video / audio -> builder-av only)
- Records asset metadata in PROJECT_INDEX.assets[<asset_id>]
- Appends asset_id to lane.result.candidates
- Transitions lane state to "generating" or, with --all-candidates-deposited,
  to "deposited"
- Appends generation_log entry (event=asset_deposited)

Exit
----
- 0 on success
- non-zero on validation / IO failure (fail-closed)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _common as common  # noqa: E402

VALID_DEPOSIT_ACTORS = ("builder-image", "builder-av")
VALID_TYPES_PER_ACTOR = {
    "builder-image": ("image",),
    "builder-av": ("video", "audio"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="deposit_asset")
    p.add_argument("--project", required=True)
    p.add_argument("--lane-id", required=True)
    p.add_argument("--asset-id", required=True,
                   help="Unique asset id (e.g. img-042-a)")
    p.add_argument("--asset-path", required=True,
                   help="Path to deposited asset file (must exist + size > 0)")
    p.add_argument("--actor", required=True, choices=VALID_DEPOSIT_ACTORS,
                   help="Depositing seat (must match lane.seat)")
    p.add_argument("--asset-type", required=True, choices=common.VALID_ASSET_TYPES)
    p.add_argument("--prompt-l3", default="", help="Model-specific prompt used")
    p.add_argument("--model", default="",
                   help="e.g. nano-banana, gpt-image-2, seedance-2.0-i2v")
    p.add_argument("--seed", type=int, default=None,
                   help="Generation seed if known")
    p.add_argument("--api-status", default="200",
                   help="API response status (default 200)")
    p.add_argument("--model-metadata", default="{}",
                   help="JSON-encoded model-provided metadata "
                        "(aesthetic_score / safety / etc)")
    p.add_argument("--all-candidates-deposited", action="store_true",
                   help="Set lane state=deposited (final candidate landed)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    asset_path = Path(args.asset_path).expanduser()
    if not asset_path.exists():
        common.fail_closed(f"asset file not found: {asset_path}")
    if not asset_path.is_file():
        common.fail_closed(f"asset path is not a file: {asset_path}")

    file_size = asset_path.stat().st_size
    if file_size <= 0:
        common.fail_closed(f"asset file is empty: {asset_path}")

    try:
        model_metadata = json.loads(args.model_metadata)
    except json.JSONDecodeError as e:
        common.fail_closed(f"invalid --model-metadata JSON: {e}")

    if args.asset_type not in VALID_TYPES_PER_ACTOR[args.actor]:
        common.fail_closed(
            f"actor {args.actor!r} cannot deposit asset_type={args.asset_type!r}"
        )

    lane = common.load_lane(args.project, args.lane_id)
    if lane is None:
        common.fail_closed(f"lane not found: {args.lane_id}")

    if lane.get("seat") != args.actor:
        common.fail_closed(
            f"actor mismatch: lane.seat={lane.get('seat')!r} actor={args.actor!r}"
        )

    if lane.get("state") in ("superseded", "failed"):
        common.fail_closed(
            f"cannot deposit into lane {args.lane_id} (state={lane.get('state')})"
        )

    now = common.now_iso()
    final = bool(args.all_candidates_deposited)
    new_state = "deposited" if final else "generating"

    asset_record = {
        "asset_id": args.asset_id,
        "path": str(asset_path),
        "type": args.asset_type,
        "lane": args.lane_id,
        "model": args.model,
        "seed": args.seed,
        "api_status": args.api_status,
        "file_size": file_size,
        "model_metadata": model_metadata,
        "deposited_at": now,
        "triggered_by": lane.get("triggered_by", "memory_spawn"),
    }

    index = common.load_project_index(args.project)
    index.setdefault("assets", {})[args.asset_id] = asset_record
    lane_idx = index.setdefault("lanes", {}).setdefault(args.lane_id, {})
    lane_idx["state"] = new_state
    if final:
        lane_idx["deposited_at"] = now
    common.write_project_index(args.project, index)

    lane.setdefault("result", {}).setdefault("candidates", [])
    if args.asset_id not in lane["result"]["candidates"]:
        lane["result"]["candidates"].append(args.asset_id)
    lane["state"] = new_state
    if final:
        lane["result"]["deposited_at"] = now
    common.write_lane(args.project, args.lane_id, lane)

    common.append_generation_log(args.project, {
        "event": "asset_deposited",
        "lane_id": args.lane_id,
        "asset_id": args.asset_id,
        "asset_type": args.asset_type,
        "actor": args.actor,
        "model": args.model,
        "seed": args.seed,
        "prompt_l3": args.prompt_l3,
        "api_status": args.api_status,
        "file_size": file_size,
        "model_metadata": model_metadata,
        "lane_final": final,
    })

    print(args.asset_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
