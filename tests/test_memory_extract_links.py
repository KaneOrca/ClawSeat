"""Tests for the typed-link / backlink graph extraction (P1 memory-graph)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[1]
_EXTRACT = _REPO / "core" / "skills" / "memory-oracle" / "scripts" / "extract_links.py"
_QUERY = _REPO / "core" / "skills" / "memory-oracle" / "scripts" / "query_memory.py"


def _run(*args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _make_page(memory_root: Path, *, project: str, kind: str, name: str, body: str) -> Path:
    page_dir = memory_root / "projects" / project / kind
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{name}.md"
    page.write_text(body, encoding="utf-8")
    return page


def test_extract_basic_entities(tmp_path: Path) -> None:
    page = _make_page(
        tmp_path,
        project="arena",
        kind="decision",
        name="d1",
        body=(
            "Looking at ARENA-228 we landed commit 318de65bb in "
            "src/views/Home/v3/HomeViewV3.tsx — see [KEY: 边界]. "
            "Also https://github.com/KaneOrca/ClawSeat for context. "
            "BitmaskPhysic and PretextLayer are involved."
        ),
    )
    rc, out, _err = _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path))
    assert rc == 0, out
    summary = json.loads(out)
    assert summary["source"] == "projects/arena/decision/d1"
    targets = set(summary["targets_added"])
    assert "entity:taskid:ARENA-228" in targets
    assert "entity:commit:318de65bb" in targets
    assert "entity:file:src/views/Home/v3/HomeViewV3.tsx" in targets
    assert "entity:key:边界" in targets
    assert "entity:url:https://github.com/KaneOrca/ClawSeat" in targets
    assert "entity:component:BitmaskPhysic" in targets
    assert "entity:component:PretextLayer" in targets


def test_idempotent_rerun(tmp_path: Path) -> None:
    page = _make_page(
        tmp_path,
        project="arena",
        kind="decision",
        name="i1",
        body="ARENA-228 + commit 318de65 + src/foo.tsx",
    )
    rc1, _o1, _ = _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path), "--quiet")
    rc2, _o2, _ = _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path), "--quiet")
    assert rc1 == 0
    assert rc2 == 0

    links_file = tmp_path / "_links" / "projects__arena__decision__i1.jsonl"
    assert links_file.is_file()
    edges = [json.loads(line) for line in links_file.read_text().splitlines() if line]
    assert len(edges) == 3  # ARENA-228 + 318de65 + src/foo.tsx

    backlinks_file = tmp_path / "_backlinks" / "entity++taskid++ARENA-228.jsonl"
    backlink_lines = [
        line for line in backlinks_file.read_text().splitlines() if line
    ]
    assert len(backlink_lines) == 1  # one source, one entry — never duplicated


def test_edge_removal_when_source_changes(tmp_path: Path) -> None:
    page = _make_page(
        tmp_path,
        project="arena",
        kind="decision",
        name="r1",
        body="ARENA-228 mentioned",
    )
    _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path), "--quiet")
    backlink = tmp_path / "_backlinks" / "entity++taskid++ARENA-228.jsonl"
    assert backlink.is_file()

    # Rewrite source: drop ARENA-228, add ARENA-999
    page.write_text("ARENA-999 only", encoding="utf-8")
    rc, out, _ = _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path))
    assert rc == 0
    summary = json.loads(out)
    assert "entity:taskid:ARENA-228" in summary["targets_removed"]
    assert "entity:taskid:ARENA-999" in summary["targets_added"]
    assert not backlink.exists(), "stale backlink file should be cleaned up"
    new_backlink = tmp_path / "_backlinks" / "entity++taskid++ARENA-999.jsonl"
    assert new_backlink.is_file()


def test_query_backlinks_command(tmp_path: Path) -> None:
    p1 = _make_page(tmp_path, project="arena", kind="decision", name="q1", body="ARENA-228")
    p2 = _make_page(tmp_path, project="arena", kind="finding", name="q2", body="ARENA-228 again")
    for page in (p1, p2):
        _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path), "--quiet")

    rc, out, _ = _run(
        str(_QUERY),
        "--memory-dir",
        str(tmp_path),
        "--backlinks",
        "entity:taskid:ARENA-228",
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["target"] == "entity:taskid:ARENA-228"
    assert payload["incoming_count"] == 2
    sources = {item["from"] for item in payload["incoming"]}
    assert sources == {"projects/arena/decision/q1", "projects/arena/finding/q2"}


def test_query_graph_bfs_depth_2(tmp_path: Path) -> None:
    page = _make_page(
        tmp_path,
        project="arena",
        kind="decision",
        name="g1",
        body="ARENA-228 + commit 318de65 + BitmaskPhysic",
    )
    _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path), "--quiet")

    rc, out, _ = _run(
        str(_QUERY),
        "--memory-dir",
        str(tmp_path),
        "--graph",
        "projects/arena/decision/g1",
        "--depth",
        "2",
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["root"] == "projects/arena/decision/g1"
    assert payload["depth"] == 2
    assert payload["edge_count"] == 3
    nodes = set(payload["nodes"])
    assert "projects/arena/decision/g1" in nodes
    assert "entity:taskid:ARENA-228" in nodes
    assert "entity:commit:318de65" in nodes
    assert "entity:component:BitmaskPhysic" in nodes


def test_slug_normalization_accepts_md_extension(tmp_path: Path) -> None:
    page = _make_page(tmp_path, project="arena", kind="decision", name="n1", body="ARENA-228")
    _run(str(_EXTRACT), "--file", str(page), "--memory-dir", str(tmp_path), "--quiet")

    # Same slug with .md extension should resolve to the same backlinks file
    rc1, out1, _ = _run(
        str(_QUERY),
        "--memory-dir",
        str(tmp_path),
        "--graph",
        "projects/arena/decision/n1.md",
    )
    rc2, out2, _ = _run(
        str(_QUERY),
        "--memory-dir",
        str(tmp_path),
        "--graph",
        "projects/arena/decision/n1",
    )
    assert rc1 == 0 and rc2 == 0
    p1 = json.loads(out1)
    p2 = json.loads(out2)
    assert p1["root"] == p2["root"]
    assert p1["edge_count"] == p2["edge_count"]


def test_outside_memory_root_returns_error(tmp_path: Path) -> None:
    other = tmp_path / "outside"
    other.mkdir()
    rogue = other / "rogue.md"
    rogue.write_text("ARENA-228", encoding="utf-8")
    rc, _out, err = _run(
        str(_EXTRACT),
        "--file",
        str(rogue),
        "--memory-dir",
        str(tmp_path / "memroot"),
    )
    assert rc == 2
    assert "memory root" in err
