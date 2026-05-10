"""cartooner-harness shared state primitives.

Single shared module (not a package) intentionally — keep the protocol's
runtime small. All I/O is against ~/.cartooner/projects/<project_id>/.

Path resolution honors `CARTOONER_ROOT` env var (used by tests / sandbox);
default is `~/.cartooner`.

Schemas
-------

PROJECT_INDEX.json (top-level state):
  {
    "project_id": "<id>",
    "version": 1,
    "created_at": "<iso>",
    "automation_mode": "manual" | "auto",
    "lanes":       {<lane_id>: {state, seat, count, shot_id, triggered_by, created_at}},
    "assets":      {<asset_id>: {asset_id, path, type, lane, model, seed, ...}},
    "tournaments": {<round_id>: {candidates, picked, ...}}
  }

generation_log.jsonl (append-only event stream):
  {"ts": "<iso>", "event": "<name>", "actor": "<seat|user|patrol>", ...}

lanes/<lane_id>.toml (per-lane state):
  id / created_at / state / seat / count / prompt / shot_id / input_image /
  style_bible_ref / character_dna_ref / parent_lane / triggered_by /
  [result] candidates / deposited_at

`no-image-policy` is enforced at design time (no helper here reads asset
content); helpers only stat asset files for `file_size` metadata.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARTOONER_ROOT_ENV = "CARTOONER_ROOT"

VALID_SEATS = ("memory", "writer", "builder-image", "builder-av", "patrol")
VALID_LANE_STATES = ("spawned", "generating", "deposited", "picked", "failed", "superseded")
VALID_ASSET_TYPES = ("image", "video", "audio")


def cartooner_root() -> Path:
    override = os.environ.get(CARTOONER_ROOT_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cartooner"


def project_root(project_id: str) -> Path:
    return cartooner_root() / "projects" / project_id


def ensure_project_skeleton(project_id: str) -> Path:
    root = project_root(project_id)
    for sub in (
        "lanes",
        "assets/images",
        "assets/videos",
        "assets/audios",
        "tournaments",
        "references_learned",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def load_project_index(project_id: str) -> dict[str, Any]:
    path = project_root(project_id) / "PROJECT_INDEX.json"
    if not path.exists():
        return {
            "project_id": project_id,
            "version": 1,
            "created_at": now_iso(),
            "automation_mode": "manual",
            "lanes": {},
            "assets": {},
            "tournaments": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def write_project_index(project_id: str, data: dict[str, Any]) -> None:
    ensure_project_skeleton(project_id)
    path = project_root(project_id) / "PROJECT_INDEX.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_generation_log(project_id: str, event: dict[str, Any]) -> None:
    ensure_project_skeleton(project_id)
    path = project_root(project_id) / "generation_log.jsonl"
    payload = {"ts": now_iso(), **event}
    line = json.dumps(payload, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_lane(project_id: str, lane_id: str) -> dict[str, Any] | None:
    path = project_root(project_id) / "lanes" / f"{lane_id}.toml"
    if not path.exists():
        return None
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]
    with path.open("rb") as fh:
        return tomllib.load(fh)


def write_lane(project_id: str, lane_id: str, data: dict[str, Any]) -> None:
    ensure_project_skeleton(project_id)
    path = project_root(project_id) / "lanes" / f"{lane_id}.toml"
    path.write_text(serialize_toml(data), encoding="utf-8")


def serialize_toml(data: dict[str, Any]) -> str:
    """Minimal TOML serializer for our flat-with-one-section lane schema.

    Supports str / int / float / bool / list[str] / nested table (one level).
    Skips keys whose value is None (to keep TOML clean).
    """
    top: list[str] = []
    sections: list[str] = []
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            sections.append(f"\n[{key}]")
            for sub_key, sub_value in value.items():
                if sub_value is None:
                    continue
                sections.append(_kv_line(sub_key, sub_value))
            continue
        top.append(_kv_line(key, value))
    return "\n".join(top + sections) + "\n"


def _kv_line(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, (int, float)):
        return f"{key} = {value}"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key} = "{escaped}"'
    if isinstance(value, list):
        if not value:
            return f"{key} = []"
        items = []
        for item in value:
            if isinstance(item, str):
                esc = item.replace("\\", "\\\\").replace('"', '\\"')
                items.append(f'"{esc}"')
            elif isinstance(item, bool):
                items.append("true" if item else "false")
            else:
                items.append(str(item))
        return f"{key} = [{', '.join(items)}]"
    return f'{key} = "{value}"'


def fail_closed(message: str, code: int = 1) -> None:
    """Print to stderr and exit non-zero. Strict fail-closed semantics."""
    print(f"[cartooner-harness] FAIL: {message}", file=sys.stderr)
    sys.exit(code)
