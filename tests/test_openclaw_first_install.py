"""Tests for the canonical OpenClaw first-install entrypoint."""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import openclaw_first_install as mod


def test_ensure_canonical_checkout_blocks_noncanonical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path / "dev-clawseat")
    monkeypatch.setattr(mod, "CLAWSEAT_ROOT", tmp_path / "dev-clawseat")
    monkeypatch.setattr(mod, "CANONICAL_REPO_ROOT", tmp_path / ".clawseat")

    with pytest.raises(RuntimeError, match="canonical checkout required"):
        mod.ensure_canonical_checkout()


def test_planner_is_configured_requires_tool_auth_and_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile = tmp_path / "install-profile-dynamic.toml"
    profile.write_text(
        "\n".join(
            [
                "[seat_overrides.planner]",
                'tool = "codex"',
                'auth_mode = "oauth"',
                'provider = "xcode-best"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "dynamic_profile_path", lambda _project: profile)

    assert mod.planner_is_configured("install") is True


def test_main_stops_at_config_gate_when_planner_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        mod,
        "parse_args",
        lambda: Namespace(project="install", openclaw_home=str(tmp_path / ".openclaw"), feishu_group_id=""),
    )
    monkeypatch.setattr(mod, "ensure_canonical_checkout", lambda: calls.append("canonical"))
    monkeypatch.setattr(mod, "ensure_bundle", lambda _home: calls.append("bundle"))
    monkeypatch.setattr(mod, "ensure_preflight", lambda _project: calls.append("preflight"))
    monkeypatch.setattr(
        mod,
        "ensure_koder_workspace",
        lambda _project, _home, feishu_group_id="": calls.append(f"koder:{feishu_group_id}"),
    )
    monkeypatch.setattr(mod, "bootstrap_materialized_seats", lambda _project: calls.append("bootstrap"))
    monkeypatch.setattr(mod, "start_planner_if_configured", lambda _project: False)
    monkeypatch.setattr(mod, "render_console", lambda _project: calls.append("console"))
    monkeypatch.setattr(mod, "print_config_gate", lambda _project: calls.append("config_gate"))

    rc = mod.main()

    assert rc == 0
    assert calls == [
        "canonical",
        "bundle",
        "preflight",
        "koder:",
        "bootstrap",
        "console",
        "config_gate",
    ]


def test_main_starts_planner_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        mod,
        "parse_args",
        lambda: Namespace(project="install", openclaw_home=str(tmp_path / ".openclaw"), feishu_group_id="oc_demo"),
    )
    monkeypatch.setattr(mod, "ensure_canonical_checkout", lambda: calls.append("canonical"))
    monkeypatch.setattr(mod, "ensure_bundle", lambda _home: calls.append("bundle"))
    monkeypatch.setattr(mod, "ensure_preflight", lambda _project: calls.append("preflight"))
    monkeypatch.setattr(
        mod,
        "ensure_koder_workspace",
        lambda _project, _home, feishu_group_id="": calls.append(f"koder:{feishu_group_id}"),
    )
    monkeypatch.setattr(mod, "bootstrap_materialized_seats", lambda _project: calls.append("bootstrap"))
    monkeypatch.setattr(
        mod,
        "start_planner_if_configured",
        lambda _project: calls.append("start_planner") or True,
    )
    monkeypatch.setattr(mod, "render_console", lambda _project: calls.append("console"))
    monkeypatch.setattr(mod, "print_config_gate", lambda _project: calls.append("config_gate"))

    rc = mod.main()

    assert rc == 0
    assert calls == [
        "canonical",
        "bundle",
        "preflight",
        "koder:oc_demo",
        "bootstrap",
        "start_planner",
        "console",
    ]


def test_ensure_preflight_raises_on_hard_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "run_command",
        lambda *_args, **_kwargs: type("Result", (), {"returncode": 1, "stdout": "", "stderr": ""})(),
    )

    with pytest.raises(RuntimeError, match="HARD_BLOCKED"):
        mod.ensure_preflight("install")


def test_ensure_preflight_raises_on_remaining_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "run_command",
        lambda *_args, **_kwargs: type("Result", (), {"returncode": 2, "stdout": "", "stderr": ""})(),
    )

    with pytest.raises(RuntimeError, match="RETRYABLE"):
        mod.ensure_preflight("install")
