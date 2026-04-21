"""B1 tests: resolve_auth_mode.py — install-flow auth-mode interview,
batch config, CLI flag, secret-file handling, and shape validation.

All tests use tmp_path-based HOME isolation via monkeypatching
``real_user_home`` so ``~/.agents/*`` paths resolve to the fixture dir.
"""
from __future__ import annotations

import io
import os
import stat
import sys
from pathlib import Path
from typing import Callable

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core" / "skills" / "clawseat-install" / "scripts"))

import resolve_auth_mode as rm  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_home(tmp_path, monkeypatch) -> Path:
    """Redirect real_user_home() to tmp_path so secret paths land in the sandbox."""
    monkeypatch.setattr(rm, "real_user_home", lambda: tmp_path)
    # Pre-create .agents so env.global writes don't collide with other tests.
    (tmp_path / ".agents").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _scripted_input(answers: list[str]) -> Callable[[str], str]:
    """Return an input() stub that pops pre-seeded answers in order."""
    queue = list(answers)

    def _in(_prompt: str = "") -> str:
        if not queue:
            raise EOFError("test input exhausted")
        return queue.pop(0)

    return _in


# ---------------------------------------------------------------------------
# Resolution — interactive
# ---------------------------------------------------------------------------

def test_interactive_choice_1_oauth_token(fake_home):
    err = io.StringIO()
    choice = rm.resolve(
        "planner",
        input_fn=_scripted_input(["1"]),
        stream_out=err,
    )
    assert choice.auth_mode == "oauth_token"
    assert choice.provider == "anthropic"
    assert choice.env_var == "CLAUDE_CODE_OAUTH_TOKEN"
    assert "Auth mode for planner" in err.getvalue()


def test_interactive_default_is_choice_1(fake_home):
    err = io.StringIO()
    choice = rm.resolve(
        "planner",
        input_fn=_scripted_input([""]),  # empty → default
        stream_out=err,
    )
    assert choice.key == "1"


def test_interactive_choice_2_api_anthropic_console(fake_home):
    err = io.StringIO()
    choice = rm.resolve(
        "builder-1",
        input_fn=_scripted_input(["2"]),
        stream_out=err,
    )
    assert choice.auth_mode == "api"
    assert choice.provider == "anthropic-console"
    assert choice.env_var == "ANTHROPIC_API_KEY"


def test_interactive_choice_6_oauth_legacy_marked_deprecated(fake_home):
    err = io.StringIO()
    choice = rm.resolve(
        "planner",
        input_fn=_scripted_input(["6"]),
        stream_out=err,
    )
    assert choice.auth_mode == "oauth"
    assert choice.deprecated is True


def test_interactive_invalid_input_reprompts(fake_home):
    err = io.StringIO()
    choice = rm.resolve(
        "planner",
        input_fn=_scripted_input(["99", "foo", "3"]),
        stream_out=err,
    )
    assert choice.key == "3"
    msg = err.getvalue()
    assert "invalid choice '99'" in msg
    assert "invalid choice 'foo'" in msg


# ---------------------------------------------------------------------------
# Resolution — batch config + CLI flag
# ---------------------------------------------------------------------------

def test_batch_config_drives_without_prompt(fake_home, tmp_path):
    cfg = tmp_path / "install-config.toml"
    cfg.write_text(
        "[seats.koder]\n"
        'auth_mode = "oauth_token"\n'
        "\n"
        "[seats.builder-2]\n"
        'auth_mode = "api"\n'
        'provider = "anthropic-console"\n',
        encoding="utf-8",
    )

    def _noop_input(_prompt: str = "") -> str:
        raise AssertionError("interactive prompt should not be invoked")

    c1 = rm.resolve("koder", batch_config=cfg, input_fn=_noop_input)
    c2 = rm.resolve("builder-2", batch_config=cfg, input_fn=_noop_input)
    assert c1.auth_mode == "oauth_token"
    assert c2.auth_mode == "api" and c2.provider == "anthropic-console"


def test_batch_config_missing_seat_falls_through_to_prompt(fake_home, tmp_path):
    cfg = tmp_path / "install-config.toml"
    cfg.write_text(
        '[seats.koder]\nauth_mode = "oauth_token"\n', encoding="utf-8",
    )
    err = io.StringIO()
    # seat not listed in config → should prompt.
    c = rm.resolve(
        "builder-1",
        batch_config=cfg,
        input_fn=_scripted_input(["5"]),
        stream_out=err,
    )
    assert c.auth_mode == "ccr"


def test_non_interactive_without_answer_raises(fake_home, tmp_path):
    cfg = tmp_path / "install-config.toml"  # does not exist
    with pytest.raises(RuntimeError, match="no auth_mode"):
        rm.resolve(
            "planner",
            batch_config=cfg,
            interactive=False,
            input_fn=_scripted_input([]),
        )


def test_cli_auth_mode_flag_overrides_everything(fake_home, tmp_path):
    cfg = tmp_path / "install-config.toml"
    cfg.write_text(
        '[seats.koder]\nauth_mode = "oauth"\n', encoding="utf-8",
    )
    # Batch says oauth, CLI says oauth_token — CLI wins.
    c = rm.resolve(
        "koder",
        cli_auth_mode="oauth_token",
        batch_config=cfg,
        input_fn=_scripted_input([]),
    )
    assert c.auth_mode == "oauth_token"


def test_cli_auth_mode_api_requires_provider(fake_home):
    # api has three providers → unambiguous without --provider.
    with pytest.raises(ValueError, match="requires --provider"):
        rm.choice_from_auth_mode("api")


def test_cli_auth_mode_api_minimax(fake_home):
    c = rm.choice_from_auth_mode("api", "minimax")
    assert c.key == "3"


def test_cli_auth_mode_invalid_provider(fake_home):
    with pytest.raises(ValueError, match="not a B1 choice"):
        rm.choice_from_auth_mode("api", "unknown-vendor")


def test_cli_auth_mode_ccr_is_unambiguous(fake_home):
    c = rm.choice_from_auth_mode("ccr")
    assert c.provider == "ccr-local"


# ---------------------------------------------------------------------------
# ensure_secret — oauth_token
# ---------------------------------------------------------------------------

def test_ensure_secret_oauth_token_reads_existing_env_global(fake_home):
    env = fake_home / ".agents" / ".env.global"
    env.write_text("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-abc123_def\n")
    choice = rm.AUTH_CHOICES["1"]
    report = rm.ensure_secret(choice, env_global=env)
    assert report["action"] == "existing"
    assert report["path"] == str(env)


def test_ensure_secret_oauth_token_prompts_and_validates_shape(fake_home):
    env = fake_home / ".agents" / ".env.global"
    err = io.StringIO()
    choice = rm.AUTH_CHOICES["1"]
    # First attempt fails shape check; second passes.
    report = rm.ensure_secret(
        choice,
        env_global=env,
        input_fn=_scripted_input(["not-a-token", "sk-ant-oat01-VALID_TOKEN"]),
        stream_out=err,
    )
    assert report["action"] == "written"
    assert "shape check failed" in err.getvalue()
    content = env.read_text()
    assert "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-VALID_TOKEN" in content


def test_ensure_secret_oauth_token_non_interactive_reports_missing(fake_home):
    env = fake_home / ".agents" / ".env.global"
    report = rm.ensure_secret(
        rm.AUTH_CHOICES["1"], env_global=env, non_interactive=True,
    )
    assert report["missing"] is True
    assert report["action"] == "skipped"


# ---------------------------------------------------------------------------
# ensure_secret — api key
# ---------------------------------------------------------------------------

def test_ensure_secret_api_key_writes_0o600(fake_home):
    err = io.StringIO()
    choice = rm.AUTH_CHOICES["2"]  # anthropic-console
    report = rm.ensure_secret(
        choice,
        input_fn=_scripted_input(["sk-ant-api03-KEY123"]),
        stream_out=err,
    )
    assert report["action"] == "written"
    path = Path(report["path"])
    assert path.exists()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"expected 0o600 got {oct(mode)}"
    assert "ANTHROPIC_API_KEY=sk-ant-api03-KEY123" in path.read_text()


def test_ensure_secret_api_key_shape_invalid_reprompts(fake_home):
    err = io.StringIO()
    choice = rm.AUTH_CHOICES["2"]
    report = rm.ensure_secret(
        choice,
        input_fn=_scripted_input(["wrong", "sk-ant-api03-OK"]),
        stream_out=err,
    )
    assert report["action"] == "written"
    assert "shape check failed" in err.getvalue()


def test_ensure_secret_api_minimax_no_shape_enforcement(fake_home):
    err = io.StringIO()
    choice = rm.AUTH_CHOICES["3"]  # minimax, no shape_re
    report = rm.ensure_secret(
        choice,
        input_fn=_scripted_input(["minimax-whatever-format"]),
        stream_out=err,
    )
    assert report["action"] == "written"
    assert Path(report["path"]).read_text().startswith("MINIMAX_API_KEY=")


def test_ensure_secret_api_key_existing_mode_upgraded_to_600(fake_home):
    path = rm.AUTH_CHOICES["2"].secret_file()
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ANTHROPIC_API_KEY=sk-ant-api03-EXIST\n")
    path.chmod(0o644)  # deliberately wrong
    report = rm.ensure_secret(rm.AUTH_CHOICES["2"], env_global=fake_home / ".agents" / ".env.global")
    assert report["action"] == "existing"
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_ensure_secret_api_key_non_interactive_missing(fake_home):
    report = rm.ensure_secret(rm.AUTH_CHOICES["3"], non_interactive=True)
    assert report["missing"] is True
    assert report["action"] == "skipped"


# ---------------------------------------------------------------------------
# ensure_secret — ccr + legacy oauth
# ---------------------------------------------------------------------------

def test_ensure_secret_ccr_not_listening_warns(fake_home, monkeypatch):
    monkeypatch.setattr(rm, "_port_listening", lambda *a, **kw: False)
    err = io.StringIO()
    report = rm.ensure_secret(
        rm.AUTH_CHOICES["5"], stream_out=err, non_interactive=True,
    )
    assert report["action"] == "warned"
    assert report["missing"] is True
    assert "ccr not detected" in err.getvalue()


def test_ensure_secret_ccr_listening_ok(fake_home, monkeypatch):
    monkeypatch.setattr(rm, "_port_listening", lambda *a, **kw: True)
    err = io.StringIO()
    report = rm.ensure_secret(
        rm.AUTH_CHOICES["5"], stream_out=err, non_interactive=True,
    )
    assert report["action"] == "existing"
    assert report["missing"] is False


def test_ensure_secret_oauth_legacy_emits_warning(fake_home):
    err = io.StringIO()
    report = rm.ensure_secret(
        rm.AUTH_CHOICES["6"], stream_out=err, non_interactive=True,
    )
    assert report["action"] == "warned"
    assert "legacy" in err.getvalue().lower()
    assert "Keychain" in err.getvalue()


# ---------------------------------------------------------------------------
# CLI end-to-end
# ---------------------------------------------------------------------------

def test_cli_non_interactive_via_flag(fake_home, capsys, monkeypatch):
    # Simulate env.global already populated.
    env = fake_home / ".agents" / ".env.global"
    env.write_text("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-TESTKEY\n")
    monkeypatch.setattr(rm, "_ENV_GLOBAL", lambda: env)
    rc = rm.main([
        "--seat", "planner",
        "--auth-mode", "oauth_token",
        "--non-interactive",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "AUTH_MODE=oauth_token" in out
    assert "PROVIDER=anthropic" in out
    assert "SECRET_ACTION=existing" in out


def test_cli_batch_config(fake_home, tmp_path, capsys, monkeypatch):
    cfg = fake_home / ".agents" / "install-config.toml"
    cfg.write_text(
        '[seats.reviewer-1]\nauth_mode = "ccr"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(rm, "_port_listening", lambda *a, **kw: True)
    rc = rm.main([
        "--seat", "reviewer-1",
        "--non-interactive",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "AUTH_MODE=ccr" in out
    assert "PROVIDER=ccr-local" in out


def test_cli_error_when_no_input(fake_home, capsys):
    rc = rm.main([
        "--seat", "some-seat",
        "--non-interactive",
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no auth_mode" in err


def test_cli_api_requires_provider(fake_home, capsys):
    rc = rm.main([
        "--seat", "builder-1",
        "--auth-mode", "api",
        "--non-interactive",
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "requires --provider" in err
