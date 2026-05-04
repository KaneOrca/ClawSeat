from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
REAL_SCRIPT = REPO / "core" / "scripts" / "build_product_bundle.py"


def _write(path: Path, text: str, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)


def _build_fake_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "fake-repo"
    script_path = repo / "core" / "scripts" / "build_product_bundle.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REAL_SCRIPT, script_path)

    _write(repo / "README.md", "bundle smoke test\n")
    _write(
        repo / "manifest.toml",
        textwrap.dedent(
            """\
            [modules]
            root = ["README.md", "manifest.toml"]
            core = ["core/scripts"]
            """
        ),
    )
    _write(repo / "core" / "scripts" / "keep.txt", "keep me\n")
    _write(repo / "core" / "scripts" / "compiled.pyc", "compiled-bytecode")
    _write(repo / "core" / "scripts" / ".tasks" / "secret.txt", "do not copy\n")
    _write(repo / "core" / "scripts" / ".git" / "config", "git-secret\n")
    _write(repo / "core" / "scripts" / "__pycache__" / "ignored.pyc", "cache")
    return repo, script_path


def test_build_product_bundle_copies_key_files_and_skips_exclusions(tmp_path: Path) -> None:
    repo, script_path = _build_fake_repo(tmp_path)
    bundle_root = tmp_path / "bundle-out"

    result = subprocess.run(
        [sys.executable, str(script_path), "--output", str(bundle_root), "--clean"],
        capture_output=True,
        text=True,
        cwd=repo,
        env={**os.environ, "PYTHONPATH": os.environ.get("PYTHONPATH", "")},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"bundle_root: {bundle_root.resolve()}" in result.stdout
    assert "mode: complete_minimal" in result.stdout

    assert (bundle_root / "README.md").is_file()
    assert (bundle_root / "manifest.toml").is_file()
    assert (bundle_root / "core" / "scripts" / "build_product_bundle.py").is_file()
    assert (bundle_root / "core" / "scripts" / "keep.txt").is_file()

    assert not (bundle_root / "core" / "scripts" / ".git").exists()
    assert not (bundle_root / "core" / "scripts" / ".tasks").exists()
    assert not (bundle_root / "core" / "scripts" / "__pycache__").exists()
    assert not (bundle_root / "core" / "scripts" / "compiled.pyc").exists()
