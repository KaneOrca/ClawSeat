#!/usr/bin/env python3
"""spawn_lane.py — Open N concurrent generation lanes on a target seat.

Caller: `memory` (default) or seat self-dispatch (with --triggered-by user_direct).

Effect
------
- Generates a unique lane_id (lane-<seat>-<short-hash>)
- Writes lanes/<lane-id>.toml with state=spawned
- Updates PROJECT_INDEX.json lanes[<lane-id>]
- Appends generation_log entry (event=lane_spawned)
- Prints lane_id to stdout

Exit
----
- 0 on success
- non-zero on validation / IO failure (fail-closed)

Note: this script does NOT invoke any cartooner-* skill — it only registers
the lane intent. The target seat picks up lane state from PROJECT_INDEX
and runs the actual generation in its own LLM call.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _common as common  # noqa: E402

VALID_SPAWN_SEATS = ("builder-image", "builder-av", "writer")
VALID_TRIGGERS = ("memory_spawn", "user_direct", "iterate_prompt", "auto_iterate")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="spawn_lane")
    p.add_argument("--project", required=True)
    p.add_argument("--seat", required=True, choices=VALID_SPAWN_SEATS,
                   help="Target seat to spawn the lane on (only generation seats accept lanes)")
    p.add_argument("--count", type=int, default=4,
                   help="Number of concurrent generations (1..16)")
    p.add_argument("--prompt", required=True,
                   help="L2 shot description (writer's narrative for this shot)")
    p.add_argument("--shot-id", default="",
                   help="Cross-modal join key from shot_list.toml")
    p.add_argument("--input-image", default="",
                   help="Optional input image asset id (i2v scenarios)")
    p.add_argument("--style-bible-ref", default="",
                   help="Style bible version ref (e.g. style_bible.md@v3)")
    p.add_argument("--character-dna-ref", default="",
                   help="Character DNA version ref (optional)")
    p.add_argument("--parent-lane", default="",
                   help="Parent lane id (for iteration / re-spawn)")
    p.add_argument("--triggered-by", default="memory_spawn", choices=VALID_TRIGGERS)
    p.add_argument("--actor", default="memory",
                   help="Calling seat id (defaults to memory)")
    p.add_argument("--skip-wakeup", action="store_true",
                   help="Skip tmux wakeup (tests / dry runs)")
    p.add_argument("--target-session", default="",
                   help="Explicit tmux session name to wake (overrides "
                        "resolve_seat_session). Use when target seat's tmux "
                        "is bound to a different project than --project.")
    return p.parse_args(argv)


def make_lane_id(seat: str) -> str:
    return f"lane-{seat}-{secrets.token_hex(4)}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.count <= 0 or args.count > 16:
        common.fail_closed(f"--count must be in 1..16, got {args.count}")

    common.ensure_project_skeleton(args.project)

    lane_id = make_lane_id(args.seat)
    now = common.now_iso()

    lane_data = {
        "id": lane_id,
        "created_at": now,
        "state": "spawned",
        "seat": args.seat,
        "count": args.count,
        "prompt": args.prompt,
        "shot_id": args.shot_id,
        "input_image": args.input_image,
        "style_bible_ref": args.style_bible_ref,
        "character_dna_ref": args.character_dna_ref,
        "parent_lane": args.parent_lane,
        "triggered_by": args.triggered_by,
    }
    common.write_lane(args.project, lane_id, lane_data)

    index = common.load_project_index(args.project)
    index.setdefault("lanes", {})[lane_id] = {
        "state": "spawned",
        "seat": args.seat,
        "count": args.count,
        "shot_id": args.shot_id or None,
        "triggered_by": args.triggered_by,
        "created_at": now,
    }
    common.write_project_index(args.project, index)

    target_session = args.target_session.strip() or (
        common.resolve_seat_session(args.project, args.seat) or ""
    )
    wakeup_message = (
        f"[{args.actor}] lane_spawned: {lane_id} seat={args.seat} "
        f"count={args.count} shot={args.shot_id or '-'}; "
        f"read lanes/{lane_id}.toml then deposit_asset.py × {args.count}"
    )
    wakeup = common.send_wakeup(
        args.project,
        target_session,
        wakeup_message,
        skip=args.skip_wakeup,
    )

    common.append_generation_log(args.project, {
        "event": "lane_spawned",
        "lane_id": lane_id,
        "seat": args.seat,
        "actor": args.actor,
        "triggered_by": args.triggered_by,
        "count": args.count,
        "prompt_l2": args.prompt,
        "shot_id": args.shot_id or None,
        "parent_lane": args.parent_lane or None,
        "wakeup_ok": wakeup["ok"],
        "wakeup_reason": wakeup["reason"],
    })

    if not wakeup["ok"] and not args.skip_wakeup:
        sys.stderr.write(
            f"[spawn_lane] WARN wakeup failed: {wakeup['reason']} "
            f"(lane is durable; receiver can pull via render_asset_tree)\n"
        )

    print(lane_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
