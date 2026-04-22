from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "apply-koder-overlay.sh"


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    return path


def _seed_home(tmp_path: Path) -> Path:
    real_home = tmp_path / "home"
    for name in ("a", "b", "c"):
        (real_home / ".openclaw" / f"workspace-{name}").mkdir(parents=True, exist_ok=True)
    (real_home / ".agents" / "profiles").mkdir(parents=True, exist_ok=True)
    (real_home / ".agents" / "profiles" / "install-profile-dynamic.toml").write_text(
        'profile_name = "install"\n',
        encoding="utf-8",
    )
    return real_home


def _run(
    args: list[str],
    *,
    real_home: Path,
    input_text: str = "",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "CLAWSEAT_REAL_HOME": str(real_home),
            "HOME": str(real_home),
            "PYTHON_BIN": sys.executable,
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        input=input_text,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
    )


def test_dry_run_lists_menu_items(tmp_path: Path) -> None:
    real_home = _seed_home(tmp_path)

    result = _run(["--dry-run", "install"], real_home=real_home)

    assert result.returncode == 0, result.stderr
    assert "可选的 OpenClaw agent" in result.stdout
    assert "[1] a" in result.stdout
    assert "[2] b" in result.stdout
    assert "[3] c" in result.stdout


def test_pick_first_invokes_init_and_bind(tmp_path: Path) -> None:
    real_home = _seed_home(tmp_path)
    log_path = tmp_path / "calls.log"
    runner = _write(
        tmp_path / "runner.sh",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$0 $*\" >> \"$CALLS_LOG\"\n",
    )

    result = _run(
        ["install"],
        real_home=real_home,
        input_text="1\ny\n",
        extra_env={
            "CALLS_LOG": str(log_path),
            "INIT_KODER_RUNNER": str(runner),
            "KODER_BIND_RUNNER": str(runner),
        },
    )

    assert result.returncode == 0, result.stderr
    log = log_path.read_text(encoding="utf-8")
    assert "--workspace" in log
    assert str(real_home / ".openclaw" / "workspace-a") in log
    assert "--tenant a" in log
    assert "OK: 'a' 已改造为 koder" in result.stdout


def test_dry_run_does_not_execute_runners(tmp_path: Path) -> None:
    real_home = _seed_home(tmp_path)
    marker = tmp_path / "executed.txt"
    runner = _write(
        tmp_path / "runner-touch.sh",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "touch \"$MARKER\"\n",
    )

    result = _run(
        ["--dry-run", "install", "oc_group123"],
        real_home=real_home,
        extra_env={
            "MARKER": str(marker),
            "INIT_KODER_RUNNER": str(runner),
            "KODER_BIND_RUNNER": str(runner),
            "CONFIGURE_KODER_FEISHU_RUNNER": str(runner),
            "OPENCLAW_HOME": str(real_home / ".openclaw"),
        },
    )

    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert "[dry-run]" in result.stdout
    assert "configure_koder_feishu" in result.stdout or "runner-touch.sh" in result.stdout
