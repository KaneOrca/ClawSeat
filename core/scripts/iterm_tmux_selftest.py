#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import subprocess
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

import agent_admin
import agent_admin_window


ROOT = Path(__file__).resolve().parents[2]
SEND_AND_VERIFY_SH = ROOT / "core" / "shell-scripts" / "send-and-verify.sh"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_executable(path: Path, text: str) -> None:
    write_text(path, text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_command(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path = ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(args)}\n"
            f"exit={result.returncode}\nstdout=\n{result.stdout}\nstderr=\n{result.stderr}"
        )
    return result


@contextlib.contextmanager
def patched_environ(overrides: dict[str, str]):
    original = os.environ.copy()
    os.environ.update(overrides)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def setup_agent_home(agent_home: Path) -> None:
    project_root = agent_home / ".agents" / "projects" / "demo"
    engineer_root = agent_home / ".agents" / "engineers" / "seat1"
    session_root = agent_home / ".agents" / "sessions" / "demo" / "seat1"
    write_text(
        project_root / "project.toml",
        textwrap.dedent(
            """\
            name = "demo"
            repo_root = "/tmp/demo-repo"
            monitor_session = "project-demo-monitor"
            engineers = ["seat1"]
            monitor_engineers = ["seat1"]
            """
        ),
    )
    write_text(
        engineer_root / "engineer.toml",
        textwrap.dedent(
            """\
            id = "seat1"
            display_name = "Seat One"
            role = "builder"
            """
        ),
    )
    write_text(
        session_root / "session.toml",
        textwrap.dedent(
            """\
            project = "demo"
            engineer_id = "seat1"
            tool = "claude"
            auth_mode = "oauth"
            provider = "anthropic"
            identity = "claude.oauth.anthropic.demo.seat1"
            workspace = "/tmp/demo-workspace"
            runtime_dir = "/tmp/demo-runtime"
            session = "demo-seat-claude"
            bin_path = "/opt/homebrew/bin/claude"
            monitor = true
            legacy_sessions = []
            launch_args = []
            """
        ),
    )


def setup_fake_binaries(fakebin: Path) -> tuple[Path, Path]:
    fake_tmux_state = fakebin / "fake_tmux_state.json"
    fake_osascript_state = fakebin / "fake_osascript_state.json"
    write_executable(
        fakebin / "tmux",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            state_path = Path(os.environ["FAKE_TMUX_STATE"])
            scenario = os.environ.get("FAKE_TMUX_SCENARIO", "send_success")

            def load_state():
                if state_path.exists():
                    return json.loads(state_path.read_text(encoding="utf-8"))
                return {}

            def save_state(payload):
                state_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

            def parse_payload(argv):
                filtered = []
                skip = False
                for item in argv:
                    if skip:
                        skip = False
                        continue
                    if item == "-t":
                        skip = True
                        continue
                    if item.startswith("-"):
                        continue
                    filtered.append(item)
                return filtered

            args = sys.argv[1:]
            state = load_state()

            if not args:
                sys.exit(0)

            if args[0] == "capture-pane":
                if scenario == "capture_fail":
                    print("capture failed", file=sys.stderr)
                    sys.exit(1)
                count = int(state.get("capture_count", 0)) + 1
                state["capture_count"] = count
                save_state(state)
                message = str(state.get("last_message", ""))
                outputs = {
                    "send_success": {
                        1: "prompt\\n",
                        2: "accepted\\n",
                        3: "accepted\\n",
                    },
                    "send_retry_success": {
                        1: "prompt\\n",
                        2: f"{message}\\n",
                        3: "accepted\\n",
                        4: "accepted\\n",
                    },
                }
                sys.stdout.write(outputs.get(scenario, outputs["send_success"]).get(count, "accepted\\n"))
                sys.exit(0)

            if args[0] == "send-keys":
                payload = parse_payload(args[1:])
                if payload and payload[-1] == "Enter":
                    state["enter_count"] = int(state.get("enter_count", 0)) + 1
                elif payload:
                    state["last_message"] = payload[-1]
                    messages = list(state.get("messages", []))
                    messages.append(payload[-1])
                    state["messages"] = messages
                save_state(state)
                sys.exit(0)

            if args[0] == "display-message":
                sys.stdout.write("codex|Working\\n")
                sys.exit(0)

            if args[0] == "has-session":
                sys.exit(0)

            if args[0] == "list-panes":
                sys.stdout.write("%1\\t120\\t40\\t0\\t0\\n")
                sys.exit(0)

            if args[0] == "list-clients":
                if scenario == "no_clients":
                    sys.exit(0)
                sys.stdout.write("client0\\n")
                sys.exit(0)

            if args[0] == "new-session":
                commands = list(state.get("commands", []))
                commands.append({"cmd": "new-session", "args": args[1:]})
                state["commands"] = commands
                save_state(state)
                sys.exit(0)

            if args[0] == "split-window":
                commands = list(state.get("commands", []))
                commands.append({"cmd": "split-window", "args": args[1:]})
                split_count = int(state.get("split_count", 0))
                if scenario == "layout_fail" and split_count >= 1:
                    state["commands"] = commands
                    save_state(state)
                    sys.exit(1)
                state["split_count"] = split_count + 1
                state["commands"] = commands
                save_state(state)
                sys.exit(0)

            if args[0] == "kill-session":
                commands = list(state.get("commands", []))
                commands.append({"cmd": "kill-session", "args": args[1:]})
                state["commands"] = commands
                save_state(state)
                sys.exit(0)

            if args[0] == "select-layout":
                commands = list(state.get("commands", []))
                commands.append({"cmd": "select-layout", "args": args[1:]})
                state["commands"] = commands
                save_state(state)
                sys.exit(0)

            sys.exit(0)
            """
        ),
    )
    write_executable(
        fakebin / "osascript",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import re
            import sys
            from pathlib import Path

            state_path = Path(os.environ["FAKE_OSASCRIPT_STATE"])
            scenario = os.environ.get("FAKE_OSASCRIPT_SCENARIO", "record_success")

            def load_state():
                if state_path.exists():
                    return json.loads(state_path.read_text(encoding="utf-8"))
                return {"attempts": {}, "scripts": []}

            def save_state(payload):
                state_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

            script = ""
            if len(sys.argv) >= 3 and sys.argv[1] == "-e":
                script = sys.argv[2]
            state = load_state()
            match = re.search(r'tell application "([^"]+)"', script)
            app = match.group(1) if match else "unknown"
            attempts = dict(state.get("attempts", {}))
            attempts[app] = int(attempts.get(app, 0)) + 1
            state["attempts"] = attempts
            scripts = list(state.get("scripts", []))
            scripts.append({"app": app, "script": script})
            state["scripts"] = scripts
            state["last_app"] = app
            state["last_script"] = script
            save_state(state)

            if scenario == "fallback_to_second_app" and app == "iTerm":
                print(f"{app} unavailable", file=sys.stderr)
                sys.exit(1)

            if scenario == "both_apps_fail":
                print(f"{app} unavailable", file=sys.stderr)
                sys.exit(1)

            sys.exit(0)
            """
        ),
    )
    return fake_tmux_state, fake_osascript_state


def base_env(fakebin: Path, agent_home: Path, fake_tmux_state: Path, fake_osascript_state: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fakebin}:{env.get('PATH', '')}",
            "AGENT_HOME": str(agent_home),
            "HOME": str(agent_home),
            "FAKE_TMUX_STATE": str(fake_tmux_state),
            "FAKE_OSASCRIPT_STATE": str(fake_osascript_state),
        }
    )
    return env


def assert_contains(text: str, needle: str, *, context: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{context}: expected to find {needle!r} in output:\n{text}")


def test_send_and_verify_direct_success(env: dict[str, str]) -> dict[str, object]:
    local_env = dict(env, FAKE_TMUX_SCENARIO="send_success")
    result = run_command(
        [
            "bash",
            str(SEND_AND_VERIFY_SH),
            "--project",
            "demo",
            "seat1",
            "ping direct",
        ],
        env=local_env,
    )
    assert_contains(result.stdout, "demo-seat-claude: OK", context="send direct")
    state = read_state(Path(local_env["FAKE_TMUX_STATE"]))
    if int(state.get("enter_count", 0)) != 1:
        raise RuntimeError(f"send direct: expected exactly one Enter, got {state}")
    return {
        "returncode": result.returncode,
        "stdout_tail": result.stdout.strip().splitlines()[-1],
        "enter_count": state.get("enter_count", 0),
    }


def test_send_and_verify_retry_success(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_TMUX_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_TMUX_SCENARIO="send_retry_success")
    result = run_command(
        [
            "bash",
            str(SEND_AND_VERIFY_SH),
            "--project",
            "demo",
            "seat1",
            "ping retry",
        ],
        env=local_env,
    )
    # send-and-verify.sh has two code paths:
    # 1. With wait-for-text.sh: may resolve as "OK (processing)" if message consumed
    # 2. Without wait-for-text.sh: triggers RETRY_NEEDED + OK (retry Enter)
    # Accept either path as success
    if "RETRY_NEEDED" in result.stdout:
        assert_contains(result.stdout, "OK (retry Enter)", context="send retry (classic path)")
    else:
        assert_contains(result.stdout, "OK", context="send retry (wait-for-text path)")
    state = read_state(state_path)
    enter_count = int(state.get("enter_count", 0))
    # Classic path: 2 Enter presses (initial + retry). Wait-for-text path: 1 Enter (no retry needed).
    if enter_count not in (1, 2):
        raise RuntimeError(f"send retry: expected 1 or 2 Enter presses, got {state}")
    return {
        "returncode": result.returncode,
        "stdout_tail": result.stdout.strip().splitlines()[-1],
        "enter_count": state.get("enter_count", 0),
    }


def test_send_and_verify_capture_failure(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_TMUX_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_TMUX_SCENARIO="capture_fail")
    result = run_command(
        [
            "bash",
            str(SEND_AND_VERIFY_SH),
            "--project",
            "demo",
            "seat1",
            "ping fail",
        ],
        env=local_env,
        check=False,
    )
    if result.returncode == 0:
        raise RuntimeError("send capture failure: expected non-zero exit")
    assert_contains(result.stdout, "CAPTURE_BEFORE_FAILED", context="send capture failure")
    assert_contains(result.stdout, "HARD_BLOCK", context="send capture failure")
    return {
        "returncode": result.returncode,
        "stdout_tail": result.stdout.strip().splitlines()[-1],
    }


def test_check_engineer_status_capture_failure(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_TMUX_STATE"])
    state_path.unlink(missing_ok=True)
    tasks_root = Path(env["AGENT_HOME"]) / "tasks"
    tasks_root.mkdir(parents=True, exist_ok=True)
    local_env = dict(
        env,
        FAKE_TMUX_SCENARIO="capture_fail",
        AGENT_PROJECT="demo",
        TASKS_ROOT=str(tasks_root),
    )
    result = run_command(
        [
            "bash",
            str(ROOT / "core" / "shell-scripts" / "check-engineer-status.sh"),
            "seat1",
        ],
        env=local_env,
    )
    assert_contains(result.stdout, "seat1: SESSION_CAPTURE_FAILED", context="status capture failure")
    assert_contains(result.stderr, "TMUX_CAPTURE_FAILED rc=1", context="status capture failure")
    return {
        "returncode": result.returncode,
        "stdout_tail": result.stdout.strip().splitlines()[-1],
    }


def test_iterm_run_command_fallback(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_OSASCRIPT_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_OSASCRIPT_SCENARIO="fallback_to_second_app")
    stderr = io.StringIO()
    with patched_environ(local_env), contextlib.redirect_stderr(stderr):
        agent_admin_window.iterm_run_command("echo hello", title="Demo")
    logs = stderr.getvalue()
    assert_contains(logs, "iterm_script_retry: app=iTerm attempt=1/3", context="iTerm fallback")
    assert_contains(logs, "iterm_script_failed_once: app=iTerm", context="iTerm fallback")
    state = read_state(state_path)
    if state.get("last_app") != "iTerm2":
        raise RuntimeError(f"iTerm fallback: expected iTerm2 success, got {state}")
    assert_contains(str(state.get("last_script", "")), 'tell application "iTerm2"', context="iTerm fallback")
    return {
        "last_app": state.get("last_app"),
        "attempts": state.get("attempts", {}),
    }


def test_open_project_tabs_window_multitab(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_OSASCRIPT_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_OSASCRIPT_SCENARIO="record_success")
    project = SimpleNamespace(
        name="demo",
        monitor_engineers=["seat1", "seat2", "seat3"],
        engineers=["seat1", "seat2", "seat3"],
    )
    sessions = {
        "seat1": SimpleNamespace(engineer_id="seat1", session="demo-seat1", workspace="/tmp/ws1"),
        "seat2": SimpleNamespace(engineer_id="seat2", session="demo-seat2", workspace="/tmp/ws2"),
        "seat3": SimpleNamespace(engineer_id="seat3", session="demo-seat3", workspace="/tmp/ws3"),
    }
    engineers = {
        "seat1": SimpleNamespace(display_name="Seat One"),
        "seat2": SimpleNamespace(display_name="Seat Two"),
        "seat3": SimpleNamespace(display_name="Seat Three"),
    }
    original_tmux_has_session = agent_admin_window.tmux_has_session
    agent_admin_window.tmux_has_session = lambda _: True
    try:
        with patched_environ(local_env):
            agent_admin_window.open_project_tabs_window(project, sessions, engineers)
    finally:
        agent_admin_window.tmux_has_session = original_tmux_has_session
    state = read_state(state_path)
    script = str(state.get("last_script", ""))
    tab_creates = script.count("create tab with default profile")
    if tab_creates != 2:
        raise RuntimeError(f"multi-tab script: expected 2 extra tab creations, got {tab_creates}\n{script}")
    assert_contains(script, 'set name to "demo:Seat One"', context="multi-tab script")
    assert_contains(script, 'set name to "demo:Seat Three"', context="multi-tab script")
    return {
        "last_app": state.get("last_app"),
        "tab_creates": tab_creates,
    }


def test_build_runtime_exports_shared_agent_home(env: dict[str, str]) -> dict[str, object]:
    temp_root = Path(env["AGENT_HOME"])
    runtime_dir = temp_root / ".agents" / "runtime" / "identities" / "claude" / "api" / "demo.seat1"
    secret_file = temp_root / ".agents" / "secrets" / "claude" / "minimax" / "seat1.env"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text("DUMMY_TOKEN=1\n", encoding="utf-8")
    session = SimpleNamespace(
        project="demo",
        tool="claude",
        auth_mode="api",
        provider="minimax",
        bin_path="/opt/homebrew/bin/claude",
        runtime_dir=str(runtime_dir),
        secret_file=str(secret_file),
        engineer_id="seat1",
    )
    with patched_environ(env):
        binary, runtime_env = agent_admin.build_runtime(session)
    if runtime_env.get("AGENT_HOME") != str(temp_root):
        raise RuntimeError(
            f"runtime env must export shared AGENT_HOME, got {runtime_env.get('AGENT_HOME')!r}"
        )
    if runtime_env.get("AGENTS_ROOT") != str(temp_root / ".agents"):
        raise RuntimeError(
            f"runtime env must export shared AGENTS_ROOT, got {runtime_env.get('AGENTS_ROOT')!r}"
        )
    if runtime_env.get("HOME") != str(runtime_dir / "home"):
        raise RuntimeError(
            f"runtime env must keep seat HOME isolated, got {runtime_env.get('HOME')!r}"
        )
    return {
        "binary": binary,
        "agent_home": runtime_env.get("AGENT_HOME"),
        "agents_root": runtime_env.get("AGENTS_ROOT"),
        "home": runtime_env.get("HOME"),
    }


def test_build_attach_command_correctness(env: dict[str, str]) -> dict[str, object]:
    with patched_environ(env):
        from agent_admin_window import build_attach_command

        cmd = build_attach_command(session="test-sess", workspace="/tmp/ws")
    assert_contains(cmd, "env -u TMUX", context="build_attach_command")
    if "cd '/tmp/ws'" not in cmd and "cd /tmp/ws" not in cmd:
        raise RuntimeError(f"build_attach_command: expected cd into workspace, got: {cmd}")
    assert_contains(cmd, "tmux attach -t", context="build_attach_command")
    assert_contains(cmd, "test-sess", context="build_attach_command")
    return {"cmd": cmd}


def test_monitor_attach_command_correctness(env: dict[str, str]) -> dict[str, object]:
    with patched_environ(env):
        from agent_admin_window import monitor_attach_command

        cmd = monitor_attach_command("my-session")
    assert_contains(cmd, "env -u TMUX", context="monitor_attach_command")
    assert_contains(cmd, "tmux attach -t", context="monitor_attach_command")
    assert_contains(cmd, "my-session", context="monitor_attach_command")
    return {"cmd": cmd}


def test_build_monitor_layout_2_panes(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_TMUX_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_TMUX_SCENARIO="send_success")
    project = SimpleNamespace(
        name="test-proj",
        monitor_session="test-monitor",
        repo_root="/tmp",
        monitor_engineers=["eng-1", "eng-2"],
        monitor_max_panes=4,
        window_mode="panes",
    )
    sessions = {
        "eng-1": SimpleNamespace(session="sess-eng-1", engineer_id="eng-1"),
        "eng-2": SimpleNamespace(session="sess-eng-2", engineer_id="eng-2"),
    }
    with patched_environ(local_env):
        agent_admin_window.build_monitor_layout(project, sessions)
    state = read_state(state_path)
    commands = state.get("commands", [])
    cmd_names = [c["cmd"] for c in commands]
    if "new-session" not in cmd_names:
        raise RuntimeError(f"build_monitor_layout 2 panes: expected new-session, got {cmd_names}")
    if "split-window" not in cmd_names:
        raise RuntimeError(f"build_monitor_layout 2 panes: expected split-window, got {cmd_names}")
    split_cmds = [c for c in commands if c["cmd"] == "split-window"]
    has_horizontal = any("-h" in c.get("args", []) for c in split_cmds)
    if not has_horizontal:
        raise RuntimeError(f"build_monitor_layout 2 panes: expected split-window -h, got {split_cmds}")
    return {"commands": cmd_names, "split_count": len(split_cmds)}


def test_build_monitor_layout_4_panes(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_TMUX_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_TMUX_SCENARIO="send_success")
    project = SimpleNamespace(
        name="test-proj-4",
        monitor_session="test-monitor-4",
        repo_root="/tmp",
        monitor_engineers=["eng-1", "eng-2", "eng-3", "eng-4"],
        monitor_max_panes=4,
        window_mode="panes",
    )
    sessions = {
        "eng-1": SimpleNamespace(session="sess-eng-1", engineer_id="eng-1"),
        "eng-2": SimpleNamespace(session="sess-eng-2", engineer_id="eng-2"),
        "eng-3": SimpleNamespace(session="sess-eng-3", engineer_id="eng-3"),
        "eng-4": SimpleNamespace(session="sess-eng-4", engineer_id="eng-4"),
    }
    with patched_environ(local_env):
        agent_admin_window.build_monitor_layout(project, sessions)
    state = read_state(state_path)
    commands = state.get("commands", [])
    cmd_names = [c["cmd"] for c in commands]
    if "new-session" not in cmd_names:
        raise RuntimeError(f"build_monitor_layout 4 panes: expected new-session, got {cmd_names}")
    split_cmds = [c for c in commands if c["cmd"] == "split-window"]
    if len(split_cmds) != 3:
        raise RuntimeError(
            f"build_monitor_layout 4 panes: expected 3 split-windows, got {len(split_cmds)}: {cmd_names}"
        )
    layout_cmds = [c for c in commands if c["cmd"] == "select-layout"]
    if not layout_cmds:
        raise RuntimeError(f"build_monitor_layout 4 panes: expected select-layout, got {cmd_names}")
    layout_args_flat = " ".join(str(a) for c in layout_cmds for a in c.get("args", []))
    if "tiled" not in layout_args_flat:
        raise RuntimeError(f"build_monitor_layout 4 panes: expected 'tiled' layout, got {layout_cmds}")
    return {"commands": cmd_names, "split_count": len(split_cmds), "layout": layout_cmds}


def test_build_monitor_layout_rollback_on_failure(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_TMUX_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_TMUX_SCENARIO="layout_fail")
    project = SimpleNamespace(
        name="test-proj-fail",
        monitor_session="test-monitor-fail",
        repo_root="/tmp",
        monitor_engineers=["eng-1", "eng-2", "eng-3"],
        monitor_max_panes=4,
        window_mode="panes",
    )
    sessions = {
        "eng-1": SimpleNamespace(session="sess-eng-1", engineer_id="eng-1"),
        "eng-2": SimpleNamespace(session="sess-eng-2", engineer_id="eng-2"),
        "eng-3": SimpleNamespace(session="sess-eng-3", engineer_id="eng-3"),
    }
    caught = False
    with patched_environ(local_env):
        try:
            agent_admin_window.build_monitor_layout(project, sessions)
        except agent_admin_window.AgentAdminWindowError:
            caught = True
    if not caught:
        raise RuntimeError("build_monitor_layout rollback: expected AgentAdminWindowError")
    state = read_state(state_path)
    commands = state.get("commands", [])
    cmd_names = [c["cmd"] for c in commands]
    if "kill-session" not in cmd_names:
        raise RuntimeError(f"build_monitor_layout rollback: expected kill-session for rollback, got {cmd_names}")
    return {"caught": caught, "commands": cmd_names}


def test_iterm_both_apps_fail(env: dict[str, str]) -> dict[str, object]:
    state_path = Path(env["FAKE_OSASCRIPT_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_OSASCRIPT_SCENARIO="both_apps_fail")
    caught = False
    stderr = io.StringIO()
    with patched_environ(local_env), contextlib.redirect_stderr(stderr):
        try:
            agent_admin_window.iterm_run_command("echo test")
        except agent_admin_window.AgentAdminWindowError:
            caught = True
    if not caught:
        raise RuntimeError("iterm_both_apps_fail: expected AgentAdminWindowError")
    state = read_state(state_path)
    attempts = state.get("attempts", {})
    if "iTerm" not in attempts or "iTerm2" not in attempts:
        raise RuntimeError(f"iterm_both_apps_fail: expected attempts for both apps, got {attempts}")
    return {"caught": caught, "attempts": attempts}


def test_verify_tui_visible(env: dict[str, str]) -> dict[str, object]:
    # Test 1: default scenario (send_success) — session exists + 1 client → visible=True
    state_path = Path(env["FAKE_TMUX_STATE"])
    state_path.unlink(missing_ok=True)
    local_env = dict(env, FAKE_TMUX_SCENARIO="send_success")
    with patched_environ(local_env):
        result_visible = agent_admin_window.verify_tui_visible("test-session", retries=1, delay=0.0)
    if not result_visible.get("visible"):
        raise RuntimeError(f"verify_tui_visible: expected visible=True with 1 client, got {result_visible}")
    if result_visible.get("clients", 0) != 1:
        raise RuntimeError(f"verify_tui_visible: expected 1 client, got {result_visible}")

    # Test 2: no_clients scenario — session exists + 0 clients → visible=False
    state_path.unlink(missing_ok=True)
    local_env_no = dict(env, FAKE_TMUX_SCENARIO="no_clients")
    with patched_environ(local_env_no):
        result_no_clients = agent_admin_window.verify_tui_visible("test-session", retries=1, delay=0.0)
    if result_no_clients.get("visible"):
        raise RuntimeError(f"verify_tui_visible: expected visible=False with 0 clients, got {result_no_clients}")
    if result_no_clients.get("clients", -1) != 0:
        raise RuntimeError(f"verify_tui_visible: expected 0 clients, got {result_no_clients}")

    return {
        "visible_result": result_visible,
        "no_clients_result": result_no_clients,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="iterm-tmux-selftest-") as tmp:
        temp_root = Path(tmp)
        fakebin = temp_root / "fakebin"
        fakebin.mkdir(parents=True, exist_ok=True)
        fake_tmux_state, fake_osascript_state = setup_fake_binaries(fakebin)
        agent_home = temp_root / "agent-home"
        setup_agent_home(agent_home)
        env = base_env(fakebin, agent_home, fake_tmux_state, fake_osascript_state)

        results = {
            "send_and_verify_direct_success": test_send_and_verify_direct_success(env),
            "send_and_verify_retry_success": test_send_and_verify_retry_success(env),
            "send_and_verify_capture_failure": test_send_and_verify_capture_failure(env),
            "check_engineer_status_capture_failure": test_check_engineer_status_capture_failure(env),
            "iterm_run_command_fallback": test_iterm_run_command_fallback(env),
            "open_project_tabs_window_multitab": test_open_project_tabs_window_multitab(env),
            "build_runtime_exports_shared_agent_home": test_build_runtime_exports_shared_agent_home(env),
            "build_attach_command_correctness": test_build_attach_command_correctness(env),
            "monitor_attach_command_correctness": test_monitor_attach_command_correctness(env),
            "build_monitor_layout_2_panes": test_build_monitor_layout_2_panes(env),
            "build_monitor_layout_4_panes": test_build_monitor_layout_4_panes(env),
            "build_monitor_layout_rollback_on_failure": test_build_monitor_layout_rollback_on_failure(env),
            "iterm_both_apps_fail": test_iterm_both_apps_fail(env),
            "verify_tui_visible": test_verify_tui_visible(env),
        }
        print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
