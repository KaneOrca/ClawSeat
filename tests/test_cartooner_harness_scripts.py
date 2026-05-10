"""Tests for cartooner-harness MVP protocol scripts.

Covers spawn_lane, deposit_asset, report_to_memory — the minimum trio
needed to drive a creative project's lane lifecycle from spawn to deposit
to user-direct supersession.

All tests run against a tmp-rooted CARTOONER_ROOT (env var) so they do
not touch the operator's real ~/.cartooner/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "skills" / "cartooner-harness" / "scripts"


def _run(script: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, str(_SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        env=full_env,
        check=False,
    )


@pytest.fixture
def cartooner_env(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "cartooner"
    return {"CARTOONER_ROOT": str(root)}


@pytest.fixture
def cartooner_root(cartooner_env: dict[str, str]) -> Path:
    return Path(cartooner_env["CARTOONER_ROOT"])


# ── spawn_lane ────────────────────────────────────────────────────────


def test_spawn_lane_creates_lane_file_index_and_log(cartooner_env, cartooner_root):
    res = _run(
        "spawn_lane.py",
        "--project", "demo",
        "--seat", "builder-image",
        "--count", "4",
        "--prompt", "苹果特写, 露珠从顶部滑落",
        "--shot-id", "shot-1",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    lane_id = res.stdout.strip()
    assert lane_id.startswith("lane-builder-image-")

    project_root = cartooner_root / "projects" / "demo"

    lane_file = project_root / "lanes" / f"{lane_id}.toml"
    assert lane_file.is_file()
    text = lane_file.read_text(encoding="utf-8")
    assert 'seat = "builder-image"' in text
    assert 'state = "spawned"' in text
    assert "count = 4" in text
    assert 'shot_id = "shot-1"' in text

    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert index["project_id"] == "demo"
    assert index["automation_mode"] == "manual"
    assert lane_id in index["lanes"]
    assert index["lanes"][lane_id]["seat"] == "builder-image"
    assert index["lanes"][lane_id]["count"] == 4
    assert index["lanes"][lane_id]["shot_id"] == "shot-1"

    log_lines = (project_root / "generation_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 1
    log = json.loads(log_lines[0])
    assert log["event"] == "lane_spawned"
    assert log["lane_id"] == lane_id
    assert log["seat"] == "builder-image"
    assert log["count"] == 4
    assert log["actor"] == "memory"
    assert log["triggered_by"] == "memory_spawn"


def test_spawn_lane_user_direct_records_trigger(cartooner_env, cartooner_root):
    res = _run(
        "spawn_lane.py",
        "--project", "demo",
        "--seat", "builder-image",
        "--count", "2",
        "--prompt", "再来 2 张更暗的",
        "--triggered-by", "user_direct",
        "--actor", "builder-image",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    project_root = cartooner_root / "projects" / "demo"
    log = json.loads((project_root / "generation_log.jsonl").read_text(encoding="utf-8").strip())
    assert log["triggered_by"] == "user_direct"
    assert log["actor"] == "builder-image"


def test_spawn_lane_rejects_invalid_seat(cartooner_env):
    res = _run(
        "spawn_lane.py",
        "--project", "demo",
        "--seat", "memory",  # not a generation seat
        "--count", "4",
        "--prompt", "x",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_spawn_lane_rejects_count_out_of_range(cartooner_env):
    for bad_count in ("0", "-1", "32"):
        res = _run(
            "spawn_lane.py",
            "--project", "demo",
            "--seat", "builder-image",
            "--count", bad_count,
            "--prompt", "x",
            env=cartooner_env,
        )
        assert res.returncode != 0, f"count={bad_count} should fail"


# ── deposit_asset ─────────────────────────────────────────────────────


def _spawn(env, seat="builder-image", count=2, prompt="x"):
    res = _run(
        "spawn_lane.py",
        "--project", "demo",
        "--seat", seat,
        "--count", str(count),
        "--prompt", prompt,
        env=env,
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def _make_fake_asset(tmp_path: Path, name: str, body: bytes = b"X" * 100) -> Path:
    f = tmp_path / name
    f.write_bytes(body)
    return f


def test_deposit_asset_records_metadata_only(cartooner_env, cartooner_root, tmp_path):
    lane_id = _spawn(cartooner_env, seat="builder-image", count=2)
    asset = _make_fake_asset(tmp_path, "img-001.png", b"\x89PNG\r\n\x1a\n" + b"X" * 100)

    res = _run(
        "deposit_asset.py",
        "--project", "demo",
        "--lane-id", lane_id,
        "--asset-id", "img-001",
        "--asset-path", str(asset),
        "--actor", "builder-image",
        "--asset-type", "image",
        "--model", "nano-banana",
        "--seed", "42",
        "--model-metadata", '{"aesthetic_score": 0.81, "safety": "ok"}',
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert "img-001" in index["assets"]
    a = index["assets"]["img-001"]
    assert a["model"] == "nano-banana"
    assert a["seed"] == 42
    assert a["lane"] == lane_id
    assert a["model_metadata"]["aesthetic_score"] == 0.81
    assert a["model_metadata"]["safety"] == "ok"
    assert a["file_size"] == 108

    # lane state still "generating" because not all 2 candidates landed
    assert index["lanes"][lane_id]["state"] == "generating"

    log_lines = (project_root / "generation_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 2
    deposit_log = json.loads(log_lines[1])
    assert deposit_log["event"] == "asset_deposited"
    assert deposit_log["asset_id"] == "img-001"
    assert deposit_log["lane_final"] is None or deposit_log["lane_final"] is False


def test_deposit_asset_final_candidate_transitions_lane_to_deposited(cartooner_env, cartooner_root, tmp_path):
    lane_id = _spawn(cartooner_env, count=1)
    asset = _make_fake_asset(tmp_path, "img-final.png")
    res = _run(
        "deposit_asset.py",
        "--project", "demo",
        "--lane-id", lane_id,
        "--asset-id", "img-final",
        "--asset-path", str(asset),
        "--actor", "builder-image",
        "--asset-type", "image",
        "--all-candidates-deposited",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert index["lanes"][lane_id]["state"] == "deposited"
    assert "deposited_at" in index["lanes"][lane_id]


def test_deposit_asset_rejects_nonexistent_lane(cartooner_env, tmp_path):
    asset = _make_fake_asset(tmp_path, "img.png")
    res = _run(
        "deposit_asset.py",
        "--project", "demo",
        "--lane-id", "lane-fake-deadbeef",
        "--asset-id", "img-001",
        "--asset-path", str(asset),
        "--actor", "builder-image",
        "--asset-type", "image",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_deposit_asset_rejects_actor_seat_mismatch(cartooner_env, tmp_path):
    lane_id = _spawn(cartooner_env, seat="builder-image", count=1)
    video = _make_fake_asset(tmp_path, "v.mp4")
    res = _run(
        "deposit_asset.py",
        "--project", "demo",
        "--lane-id", lane_id,
        "--asset-id", "v-001",
        "--asset-path", str(video),
        "--actor", "builder-av",  # mismatch: lane.seat = builder-image
        "--asset-type", "video",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_deposit_asset_rejects_asset_type_mismatch(cartooner_env, tmp_path):
    lane_id = _spawn(cartooner_env, seat="builder-image", count=1)
    video = _make_fake_asset(tmp_path, "v.mp4")
    res = _run(
        "deposit_asset.py",
        "--project", "demo",
        "--lane-id", lane_id,
        "--asset-id", "v-001",
        "--asset-path", str(video),
        "--actor", "builder-image",
        "--asset-type", "video",  # builder-image cannot deposit video
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_deposit_asset_rejects_empty_file(cartooner_env, tmp_path):
    lane_id = _spawn(cartooner_env, count=1)
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    res = _run(
        "deposit_asset.py",
        "--project", "demo",
        "--lane-id", lane_id,
        "--asset-id", "img-empty",
        "--asset-path", str(empty),
        "--actor", "builder-image",
        "--asset-type", "image",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_deposit_asset_rejects_into_superseded_lane(cartooner_env, tmp_path):
    lane_id = _spawn(cartooner_env, count=2)
    # supersede via report_to_memory
    res = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "user_direct_request",
        "--seat", "builder-image",
        "--triggered-by", "user",
        "--intent", "stop",
        "--supersedes", lane_id,
        env=cartooner_env,
    )
    assert res.returncode == 0
    asset = _make_fake_asset(tmp_path, "img.png")
    res = _run(
        "deposit_asset.py",
        "--project", "demo",
        "--lane-id", lane_id,
        "--asset-id", "img-orphan",
        "--asset-path", str(asset),
        "--actor", "builder-image",
        "--asset-type", "image",
        env=cartooner_env,
    )
    assert res.returncode != 0


# ── report_to_memory ──────────────────────────────────────────────────


def test_report_to_memory_user_direct_logs_actor_user(cartooner_env, cartooner_root):
    res = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "user_direct_request",
        "--seat", "builder-image",
        "--triggered-by", "user",
        "--intent", "再来 4 张更暗",
        "--action", "spawn_lane",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    project_root = cartooner_root / "projects" / "demo"
    log = json.loads((project_root / "generation_log.jsonl").read_text(encoding="utf-8").strip())
    assert log["event"] == "user_direct_request"
    assert log["actor"] == "user"
    assert log["triggered_by"] == "user"
    assert log["intent"] == "再来 4 张更暗"
    assert log["seat"] == "builder-image"


def test_report_to_memory_supersedes_marks_lane(cartooner_env, cartooner_root):
    lane_id = _spawn(cartooner_env, count=4)
    res = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "user_direct_request",
        "--seat", "builder-image",
        "--triggered-by", "user",
        "--intent", "stop, do wide shots instead",
        "--action", "spawn_lane",
        "--supersedes", lane_id,
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert index["lanes"][lane_id]["state"] == "superseded"
    assert "superseded_at" in index["lanes"][lane_id]
    assert index["lanes"][lane_id]["superseded_by_event"] == "user_direct_request"

    lane_text = (project_root / "lanes" / f"{lane_id}.toml").read_text(encoding="utf-8")
    assert 'state = "superseded"' in lane_text


def test_report_to_memory_rejects_unknown_supersedes(cartooner_env):
    res = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "user_direct_request",
        "--seat", "builder-image",
        "--triggered-by", "user",
        "--supersedes", "lane-fake",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_report_to_memory_flips_auto_to_manual_on_user_direct(cartooner_env, cartooner_root):
    project_root = cartooner_root / "projects" / "demo"
    project_root.mkdir(parents=True)
    initial = {
        "project_id": "demo",
        "version": 1,
        "created_at": "2026-05-10T00:00:00.000+00:00",
        "automation_mode": "auto",
        "lanes": {},
        "assets": {},
        "tournaments": {},
    }
    (project_root / "PROJECT_INDEX.json").write_text(json.dumps(initial), encoding="utf-8")

    res = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "user_direct_request",
        "--seat", "writer",
        "--triggered-by", "user",
        "--intent", "改对白",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr

    after = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert after["automation_mode"] == "manual"
    assert "automation_flipped_at" in after
    assert after["automation_flipped_reason"] == "user_direct_received"


def test_report_to_memory_does_not_flip_for_non_user_events(cartooner_env, cartooner_root):
    project_root = cartooner_root / "projects" / "demo"
    project_root.mkdir(parents=True)
    initial = {
        "project_id": "demo",
        "version": 1,
        "created_at": "2026-05-10T00:00:00.000+00:00",
        "automation_mode": "auto",
        "lanes": {}, "assets": {}, "tournaments": {},
    }
    (project_root / "PROJECT_INDEX.json").write_text(json.dumps(initial), encoding="utf-8")

    # patrol-triggered event in auto mode should NOT flip mode
    res = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "subagent_completed",
        "--seat", "patrol",
        "--triggered-by", "patrol",
        "--intent", "sla check passed",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    after = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert after["automation_mode"] == "auto"  # unchanged


def test_report_to_memory_subagent_event_carries_payload(cartooner_env, cartooner_root):
    res = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "subagent_started",
        "--seat", "builder-av",
        "--triggered-by", "user",
        "--intent", "ingest WKW for shot rhythm reference",
        "--action", "spawn_subagent",
        "--subagent-type", "reference_learning",
        "--subagent-inputs", '{"url": "https://youtube.com/watch?v=...", "focus": "shot rhythm"}',
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr

    project_root = cartooner_root / "projects" / "demo"
    log = json.loads((project_root / "generation_log.jsonl").read_text(encoding="utf-8").strip())
    assert log["subagent_type"] == "reference_learning"
    assert log["subagent_inputs"]["focus"] == "shot rhythm"


# ── end-to-end mini flow ──────────────────────────────────────────────


def test_full_mini_flow_spawn_two_deposits_then_user_supersede(cartooner_env, cartooner_root, tmp_path):
    """spawn(2) → deposit(1, generating) → deposit(2, deposited) → user supersedes."""
    lane_id = _spawn(cartooner_env, count=2, prompt="apple close-up")

    a1 = _make_fake_asset(tmp_path, "a1.png")
    a2 = _make_fake_asset(tmp_path, "a2.png")

    r1 = _run(
        "deposit_asset.py",
        "--project", "demo", "--lane-id", lane_id,
        "--asset-id", "img-1", "--asset-path", str(a1),
        "--actor", "builder-image", "--asset-type", "image",
        "--model", "nano-banana", "--seed", "1",
        env=cartooner_env,
    )
    assert r1.returncode == 0
    r2 = _run(
        "deposit_asset.py",
        "--project", "demo", "--lane-id", lane_id,
        "--asset-id", "img-2", "--asset-path", str(a2),
        "--actor", "builder-image", "--asset-type", "image",
        "--model", "nano-banana", "--seed", "2",
        "--all-candidates-deposited",
        env=cartooner_env,
    )
    assert r2.returncode == 0

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert index["lanes"][lane_id]["state"] == "deposited"
    assert set(index["assets"].keys()) == {"img-1", "img-2"}

    # user changes mind
    sup = _run(
        "report_to_memory.py",
        "--project", "demo",
        "--event", "user_direct_request",
        "--seat", "builder-image",
        "--triggered-by", "user",
        "--intent", "actually I want wide shots",
        "--supersedes", lane_id,
        env=cartooner_env,
    )
    assert sup.returncode == 0
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert index["lanes"][lane_id]["state"] == "superseded"

    log_lines = (project_root / "generation_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["event"] for line in log_lines]
    assert events == ["lane_spawned", "asset_deposited", "asset_deposited", "user_direct_request"]


# ── pick_winner ───────────────────────────────────────────────────────


def _spawn_and_deposit(env, tmp_path, *,
                       seat="builder-image", asset_type="image",
                       shot_id="shot-1", asset_ids=("img-001", "img-002"),
                       metadata=None):
    """Helper: spawn a lane and deposit a set of candidates with optional metadata."""
    res = _run(
        "spawn_lane.py",
        "--project", "demo",
        "--seat", seat,
        "--count", str(len(asset_ids)),
        "--prompt", "x",
        "--shot-id", shot_id,
        env=env,
    )
    assert res.returncode == 0, res.stderr
    lane_id = res.stdout.strip()

    suffix = {"image": ".png", "video": ".mp4", "audio": ".wav"}[asset_type]
    for i, asset_id in enumerate(asset_ids):
        f = tmp_path / f"{asset_id}{suffix}"
        f.write_bytes(b"X" * 100)
        meta = {}
        if metadata is not None:
            meta = metadata.get(asset_id, {})
        is_last = i == len(asset_ids) - 1
        args = [
            "--project", "demo",
            "--lane-id", lane_id,
            "--asset-id", asset_id,
            "--asset-path", str(f),
            "--actor", seat,
            "--asset-type", asset_type,
            "--model-metadata", json.dumps(meta),
        ]
        if is_last:
            args.append("--all-candidates-deposited")
        rd = _run("deposit_asset.py", *args, env=env)
        assert rd.returncode == 0, rd.stderr
    return lane_id


def test_pick_winner_manual_records_pick_and_marks_lane(cartooner_env, cartooner_root, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path,
                       asset_ids=("img-001", "img-002", "img-003", "img-004"))
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-001,img-002,img-003,img-004",
        "--strategy", "manual",
        "--picked", "img-002",
        "--reason", "best mood for shot-1",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "img-002"

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert index["tournaments"]["shot-1-r1"]["picked"] == "img-002"
    assert index["assets"]["img-002"]["status"] == "picked"
    winner_lane = index["assets"]["img-002"]["lane"]
    assert index["lanes"][winner_lane]["state"] == "picked"

    tournament_text = (project_root / "tournaments" / "shot-1-r1.toml").read_text(encoding="utf-8")
    assert 'picked = "img-002"' in tournament_text
    assert 'reason = "best mood for shot-1"' in tournament_text


def test_pick_winner_reject_all_records_no_winner(cartooner_env, cartooner_root, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path,
                       asset_ids=("img-001", "img-002"))
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-001,img-002",
        "--strategy", "manual",
        "--reject-all",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == ""

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    rec = index["tournaments"]["shot-1-r1"]
    assert rec["picked"] == ""
    assert rec["rejected_all"] is True
    # no asset/lane status changes
    assert index["assets"]["img-001"].get("status") != "picked"


def test_pick_winner_model_metadata_rank_picks_highest(cartooner_env, cartooner_root, tmp_path):
    _spawn_and_deposit(
        cartooner_env, tmp_path,
        asset_ids=("img-a", "img-b", "img-c", "img-d"),
        metadata={
            "img-a": {"aesthetic_score": 0.71},
            "img-b": {"aesthetic_score": 0.86},
            "img-c": {"aesthetic_score": 0.78},
            "img-d": {"aesthetic_score": 0.62},
        },
    )
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-a,img-b,img-c,img-d",
        "--strategy", "model-metadata-rank",
        "--min-score", "0.75",
        "--picker", "memory_acting_director",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "img-b"  # highest above 0.75


def test_pick_winner_model_metadata_rank_below_threshold_fails(cartooner_env, tmp_path):
    _spawn_and_deposit(
        cartooner_env, tmp_path,
        asset_ids=("img-1", "img-2"),
        metadata={
            "img-1": {"aesthetic_score": 0.5},
            "img-2": {"aesthetic_score": 0.6},
        },
    )
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1,img-2",
        "--strategy", "model-metadata-rank",
        "--min-score", "0.75",
        "--picker", "memory_acting_director",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_pick_winner_model_metadata_rank_no_scores_fails(cartooner_env, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path, asset_ids=("img-1", "img-2"))  # no metadata
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1,img-2",
        "--strategy", "model-metadata-rank",
        "--picker", "memory_acting_director",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_pick_winner_rejects_picked_not_in_candidates(cartooner_env, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path, asset_ids=("img-1", "img-2"))
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1,img-2",
        "--strategy", "manual",
        "--picked", "img-9",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_pick_winner_rejects_unknown_candidate(cartooner_env, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path, asset_ids=("img-1",))
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1,img-not-exist",
        "--strategy", "manual",
        "--picked", "img-1",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_pick_winner_rejects_candidates_across_shots(cartooner_env, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path, shot_id="shot-1", asset_ids=("img-1",))
    _spawn_and_deposit(cartooner_env, tmp_path, shot_id="shot-2", asset_ids=("img-2",))
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "mixed-r1",
        "--candidates", "img-1,img-2",
        "--strategy", "manual",
        "--picked", "img-1",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_pick_winner_idempotent_same_winner_re_call(cartooner_env, cartooner_root, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path, asset_ids=("img-1", "img-2"))
    common_args = [
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1,img-2",
        "--strategy", "manual",
        "--picked", "img-1",
    ]
    r1 = _run("pick_winner.py", *common_args, env=cartooner_env)
    assert r1.returncode == 0
    r2 = _run("pick_winner.py", *common_args, env=cartooner_env)
    assert r2.returncode == 0  # same winner re-call OK


def test_pick_winner_rejects_change_winner_after_pick(cartooner_env, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path, asset_ids=("img-1", "img-2"))
    r1 = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1,img-2",
        "--strategy", "manual",
        "--picked", "img-1",
        env=cartooner_env,
    )
    assert r1.returncode == 0
    r2 = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1,img-2",
        "--strategy", "manual",
        "--picked", "img-2",  # different winner
        env=cartooner_env,
    )
    assert r2.returncode != 0


def test_pick_winner_rejects_mutually_exclusive_picked_and_reject_all(cartooner_env, tmp_path):
    _spawn_and_deposit(cartooner_env, tmp_path, asset_ids=("img-1",))
    res = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "img-1",
        "--strategy", "manual",
        "--picked", "img-1",
        "--reject-all",
        env=cartooner_env,
    )
    assert res.returncode != 0


# ── iterate_prompt ────────────────────────────────────────────────────


def test_iterate_prompt_L3_records_lane_iteration(cartooner_env, cartooner_root):
    lane_id = _spawn(cartooner_env)
    res = _run(
        "iterate_prompt.py",
        "--project", "demo",
        "--layer", "L3",
        "--feedback", "all 4 too bright; want low-key lighting",
        "--parent-lane", lane_id,
        "--target", "lane",
        "--triggered-by-event", "user_direct",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    iter_id = res.stdout.strip()
    assert iter_id.startswith("iter-l3-")

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert iter_id in index["iterations"]
    rec = index["iterations"][iter_id]
    assert rec["layer"] == "L3"
    assert rec["parent_lane"] == lane_id
    assert rec["status"] == "open"

    iter_text = (project_root / "iterations" / f"{iter_id}.toml").read_text(encoding="utf-8")
    assert 'layer = "L3"' in iter_text
    assert "low-key lighting" in iter_text


def test_iterate_prompt_L2_records_shot_revision(cartooner_env, cartooner_root):
    res = _run(
        "iterate_prompt.py",
        "--project", "demo",
        "--layer", "L2",
        "--feedback", "shot 5 should be wide composition",
        "--parent-shot", "shot-5",
        "--target", "shot_list",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    iter_id = res.stdout.strip()
    assert iter_id.startswith("iter-l2-")

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    rec = index["iterations"][iter_id]
    assert rec["layer"] == "L2"
    assert rec["parent_shot"] == "shot-5"
    assert rec["target"] == "shot_list"


def test_iterate_prompt_L1_records_brief_revision(cartooner_env, cartooner_root):
    res = _run(
        "iterate_prompt.py",
        "--project", "demo",
        "--layer", "L1",
        "--feedback", "audience should be 18-25 not 25-35",
        "--target", "brief",
        env=cartooner_env,
    )
    assert res.returncode == 0, res.stderr
    iter_id = res.stdout.strip()
    assert iter_id.startswith("iter-l1-")


def test_iterate_prompt_L3_requires_parent_lane(cartooner_env):
    res = _run(
        "iterate_prompt.py",
        "--project", "demo",
        "--layer", "L3",
        "--feedback", "fix it",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_iterate_prompt_rejects_empty_feedback(cartooner_env):
    res = _run(
        "iterate_prompt.py",
        "--project", "demo",
        "--layer", "L1",
        "--feedback", "   ",
        env=cartooner_env,
    )
    assert res.returncode != 0


def test_iterate_prompt_rejects_unknown_parent_lane(cartooner_env):
    res = _run(
        "iterate_prompt.py",
        "--project", "demo",
        "--layer", "L3",
        "--feedback", "fix it",
        "--parent-lane", "lane-fake-deadbeef",
        env=cartooner_env,
    )
    assert res.returncode != 0


# ── full lifecycle: spawn → deposit → pick → iterate L3 → re-spawn ────


def test_full_lifecycle_with_iteration(cartooner_env, cartooner_root, tmp_path):
    """Realistic flow: spawn, deposit, user picks one but later iterates L3."""
    lane1 = _spawn_and_deposit(cartooner_env, tmp_path,
                               shot_id="shot-1",
                               asset_ids=("a", "b", "c", "d"))
    # user picks one
    r = _run(
        "pick_winner.py",
        "--project", "demo",
        "--round-id", "shot-1-r1",
        "--candidates", "a,b,c,d",
        "--strategy", "manual",
        "--picked", "b",
        env=cartooner_env,
    )
    assert r.returncode == 0

    # user later wants iteration on the parent lane
    r = _run(
        "iterate_prompt.py",
        "--project", "demo",
        "--layer", "L3",
        "--feedback", "even better mood, deeper shadows",
        "--parent-lane", lane1,
        "--triggered-by-event", "user_direct",
        env=cartooner_env,
    )
    assert r.returncode == 0
    iter_id = r.stdout.strip()

    # caller (memory) would now spawn a child lane:
    r = _run(
        "spawn_lane.py",
        "--project", "demo",
        "--seat", "builder-image",
        "--count", "2",
        "--prompt", "[iterated] deeper shadows on apple close-up",
        "--shot-id", "shot-1",
        "--parent-lane", lane1,
        "--triggered-by", "iterate_prompt",
        env=cartooner_env,
    )
    assert r.returncode == 0
    child_lane = r.stdout.strip()

    project_root = cartooner_root / "projects" / "demo"
    index = json.loads((project_root / "PROJECT_INDEX.json").read_text(encoding="utf-8"))
    assert child_lane in index["lanes"]
    assert index["lanes"][child_lane]["triggered_by"] == "iterate_prompt"
    assert iter_id in index["iterations"]

    log_events = [
        json.loads(line)["event"]
        for line in (project_root / "generation_log.jsonl")
        .read_text(encoding="utf-8").strip().splitlines()
    ]
    # spawn_lane(parent) + 4×asset_deposited + pick_winner + iterate_prompt + spawn_lane(child)
    assert log_events.count("lane_spawned") == 2
    assert log_events.count("asset_deposited") == 4
    assert "pick_winner" in log_events
    assert "iterate_prompt" in log_events
