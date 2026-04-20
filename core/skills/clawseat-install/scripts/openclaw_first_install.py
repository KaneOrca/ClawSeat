#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core._bootstrap import CLAWSEAT_ROOT
from core.resolve import dynamic_profile_path


PROJECT = "install"
CANONICAL_REPO_ROOT = Path.home() / ".clawseat"
OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser()
WORKSPACE_KODER = OPENCLAW_HOME / "workspace-koder"
PRECHECK = CLAWSEAT_ROOT / "core" / "preflight.py"
INSTALL_BUNDLE = CLAWSEAT_ROOT / "shells" / "openclaw-plugin" / "install_openclaw_bundle.py"
INIT_KODER = CLAWSEAT_ROOT / "core" / "skills" / "clawseat-install" / "scripts" / "init_koder.py"
REFRESH_WORKSPACES = CLAWSEAT_ROOT / "core" / "skills" / "clawseat-install" / "scripts" / "refresh_workspaces.py"
BOOTSTRAP = CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "bootstrap_harness.py"
START_SEAT = CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "start_seat.py"
RENDER_CONSOLE = CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "render_console.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Canonical OpenClaw first-install / repair entrypoint for ClawSeat.",
    )
    parser.add_argument("--project", default=PROJECT, help="Project name. Defaults to canonical install.")
    parser.add_argument(
        "--openclaw-home",
        default=str(OPENCLAW_HOME),
        help="Path to the OpenClaw home. Defaults to ~/.openclaw.",
    )
    parser.add_argument(
        "--feishu-group-id",
        default="",
        help="Optional Feishu group id for the initial koder workspace contract.",
    )
    return parser.parse_args()


def run_command(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("CLAWSEAT_ROOT", str(CLAWSEAT_ROOT))
    result = subprocess.run(
        command,
        cwd=cwd or CLAWSEAT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result


def require_success(result: subprocess.CompletedProcess[str], *, step: str) -> None:
    if result.returncode == 0:
        return
    raise RuntimeError(f"{step} failed (rc={result.returncode})")


def ensure_canonical_checkout() -> None:
    expected = CANONICAL_REPO_ROOT.expanduser().resolve()
    repo_root = REPO_ROOT.resolve()
    configured_root = CLAWSEAT_ROOT.resolve()
    if repo_root == expected and configured_root == expected:
        return
    raise RuntimeError(
        "canonical checkout required for OpenClaw first install.\n"
        f"expected:       {expected}\n"
        f"script repo:    {repo_root}\n"
        f"CLAWSEAT_ROOT:  {configured_root}\n"
        "One-step fix:\n"
        "  git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat\n"
        "  export CLAWSEAT_ROOT=\"$HOME/.clawseat\"\n"
        "  python3 \"$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py\""
    )


def ensure_bundle(openclaw_home: Path) -> None:
    print("step: repair_openclaw_bundle")
    result = run_command(
        [
            "python3",
            str(INSTALL_BUNDLE),
            "--openclaw-home",
            str(openclaw_home),
        ]
    )
    require_success(result, step="install_openclaw_bundle")


def ensure_preflight(project: str) -> None:
    print("step: preflight_openclaw")
    result = run_command(
        [
            "python3",
            str(PRECHECK),
            project,
            "--runtime",
            "openclaw",
            "--auto-fix",
        ]
    )
    if result.returncode == 0:
        return
    if result.returncode == 1:
        raise RuntimeError(
            "preflight failed with HARD_BLOCKED items. Resolve the printed blockers, then re-run "
            "openclaw_first_install.py."
        )
    raise RuntimeError(
        "preflight still has RETRYABLE items after --auto-fix. Inspect the printed diagnostics, "
        "resolve the remaining drift, then re-run openclaw_first_install.py."
    )


def ensure_koder_workspace(project: str, openclaw_home: Path, *, feishu_group_id: str) -> None:
    print("step: ensure_koder_workspace")
    workspace = openclaw_home / "workspace-koder"
    workspace.mkdir(parents=True, exist_ok=True)
    profile_path = dynamic_profile_path(project)
    contract = workspace / "WORKSPACE_CONTRACT.toml"
    if contract.exists():
        result = run_command(
            [
                "python3",
                str(REFRESH_WORKSPACES),
                "--project",
                project,
                "--profile",
                str(profile_path),
                "--koder-workspace",
                str(workspace),
            ]
        )
        require_success(result, step="refresh_workspaces")
        return
    result = run_command(
        [
            "python3",
            str(INIT_KODER),
            "--workspace",
            str(workspace),
            "--project",
            project,
            "--profile",
            str(profile_path),
            "--feishu-group-id",
            feishu_group_id,
        ]
    )
    require_success(result, step="init_koder")


def bootstrap_materialized_seats(project: str) -> None:
    print("step: bootstrap_materialized_seats")
    profile_path = dynamic_profile_path(project)
    result = run_command(
        [
            "python3",
            str(BOOTSTRAP),
            "--profile",
            str(profile_path),
            "--project-name",
            project,
        ]
    )
    require_success(result, step="bootstrap_harness")


def planner_is_configured(project: str) -> bool:
    profile_path = dynamic_profile_path(project)
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore
    data = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    planner = data.get("seat_overrides", {}).get("planner", {})
    required_fields = ("tool", "auth_mode", "provider")
    return all(str(planner.get(field, "")).strip() for field in required_fields)


def start_planner_if_configured(project: str) -> bool:
    if not planner_is_configured(project):
        return False
    print("step: start_planner")
    result = run_command(
        [
            "python3",
            str(START_SEAT),
            "--profile",
            str(dynamic_profile_path(project)),
            "--seat",
            "planner",
            "--confirm-start",
        ]
    )
    require_success(result, step="start_planner")
    return True


def render_console(project: str) -> None:
    print("step: render_console")
    result = run_command(
        [
            "python3",
            str(RENDER_CONSOLE),
            "--profile",
            str(dynamic_profile_path(project)),
        ]
    )
    require_success(result, step="render_console")


def print_config_gate(project: str) -> None:
    profile_path = dynamic_profile_path(project)
    print("planner_config_required:")
    print("  planner 尚未完成显式 tool/auth/provider 配置，所以首装停在 configuration gate。")
    print("next_step:")
    print(
        "  python3 "
        f"\"{START_SEAT}\" "
        f"--profile \"{profile_path}\" "
        "--seat planner "
        "--tool <claude|codex|gemini> "
        "--auth-mode <oauth|api> "
        "--provider <provider> "
        "--confirm-start"
    )


def main() -> int:
    args = parse_args()
    openclaw_home = Path(args.openclaw_home).expanduser()
    ensure_canonical_checkout()
    ensure_bundle(openclaw_home)
    ensure_preflight(args.project)
    ensure_koder_workspace(args.project, openclaw_home, feishu_group_id=args.feishu_group_id)
    bootstrap_materialized_seats(args.project)
    planner_started = start_planner_if_configured(args.project)
    render_console(args.project)
    if planner_started:
        print("planner_state: started_or_already_running")
    else:
        print_config_gate(args.project)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
