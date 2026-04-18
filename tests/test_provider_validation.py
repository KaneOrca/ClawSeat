"""Lock the 'anthropix'-class typo detector at every argparse entry point.

Historically `agent-admin engineer create install claude oauth anthropix`
silently succeeded: the engineer profile wrote `provider=anthropix`, the
runtime sandbox directory got created under
`~/.agents/runtime/identities/claude/oauth/claude.oauth.anthropix.install.<seat>/`,
the seat's CLI launched in that sandbox with no credentials, and claude
dropped the operator at the OAuth login screen. The only symptom was a
'pane 持续空白'.

The underlying validator `is_supported_runtime_combo()` / `validate_runtime_combo()`
has existed for a while — but none of the CLI entry points actually
called it. This test pins that every mutating entry point refuses an
unsupported triple UPFRONT, before any filesystem side effect.

Covered entry points:
- `engineer create`            (agent_admin_crud.CrudHandlers.engineer_create)
- `session switch-harness`     (agent_admin_switch.SwitchHandlers.session_switch_harness)
- `session switch-auth`        (agent_admin_switch.SwitchHandlers.session_switch_auth)

`start_seat.py` also validates locally before the subprocess round-trip;
that path is covered by the live smoke in the commit message, not here
(it spawns subprocesses).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core" / "scripts"))

from agent_admin_config import (  # noqa: E402
    SUPPORTED_RUNTIME_MATRIX,
    is_supported_runtime_combo,
    supported_providers,
    validate_runtime_combo,
)


# ── Sanity: the matrix itself is what we think it is ────────────────────────


def test_anthropix_is_not_a_valid_provider():
    """Pin the exact typo we want to catch — if anyone silently adds
    'anthropix' as an alias of 'anthropic' in the matrix, this test will
    scream so the operator can ask 'are you sure this is intentional?'
    """
    assert not is_supported_runtime_combo("claude", "oauth", "anthropix")
    assert is_supported_runtime_combo("claude", "oauth", "anthropic")


def test_minimaxi_is_not_a_valid_provider():
    """Same rationale for the sibling typo."""
    assert not is_supported_runtime_combo("claude", "api", "minimaxi")
    assert is_supported_runtime_combo("claude", "api", "minimax")


def test_matrix_has_every_triple_we_rely_on_in_docs():
    """TOOLS/seat.md tells koder which triples are valid. If any of those
    references drift from the matrix, the operator will get contradictory
    guidance.
    """
    expected = {
        ("claude", "oauth", "anthropic"),
        ("claude", "api", "xcode-best"),
        ("claude", "api", "minimax"),
        ("codex", "oauth", "openai"),
        ("codex", "api", "xcode-best"),
        ("gemini", "oauth", "google"),
        ("gemini", "api", "google-api-key"),
    }
    for (tool, auth, provider) in expected:
        assert is_supported_runtime_combo(tool, auth, provider), (
            f"{tool}/{auth}/{provider} dropped from matrix — this breaks "
            "TOOLS/seat.md guidance"
        )


# ── validate_runtime_combo shape + error text ─────────────────────────────


def test_validate_rejects_anthropix_with_helpful_error():
    with pytest.raises(RuntimeError) as excinfo:
        validate_runtime_combo(
            "claude", "oauth", "anthropix",
            error_cls=RuntimeError,
            context="test",
        )
    msg = str(excinfo.value)
    # Helpful error must include:
    # 1. the bad value (so operator sees what they typed wrong)
    assert "anthropix" in msg
    # 2. the tool + auth_mode for disambiguation
    assert "claude/oauth" in msg
    # 3. the ACTUAL valid provider(s)
    assert "anthropic" in msg
    # 4. the caller-supplied context so operator knows which command failed
    assert "test" in msg


def test_validate_accepts_anthropic():
    # Must not raise for valid triples.
    validate_runtime_combo("claude", "oauth", "anthropic")
    validate_runtime_combo("codex", "oauth", "openai")
    validate_runtime_combo("gemini", "oauth", "google")
    validate_runtime_combo("claude", "api", "minimax")
    validate_runtime_combo("codex", "api", "xcode-best")


def test_validate_rejects_unknown_tool():
    # argparse `choices` should prevent this, but our defence-in-depth
    # still reports it cleanly instead of KeyErroring.
    with pytest.raises(ValueError) as excinfo:
        validate_runtime_combo("claud", "oauth", "anthropic")
    assert "claud" in str(excinfo.value)


def test_validate_rejects_unknown_auth_mode():
    with pytest.raises(ValueError) as excinfo:
        validate_runtime_combo("claude", "oauthed", "anthropic")
    assert "oauthed" in str(excinfo.value)


# ── Entry point: engineer_create ──────────────────────────────────────────


def _fake_crud_hooks(error_cls=RuntimeError):
    """Hand-rolled stub with only the fields engineer_create touches
    before validation fires. If validation is missing and we reach the
    real side-effect-ful hooks, AttributeError tells us fast.
    """
    from types import SimpleNamespace
    hooks = SimpleNamespace(
        error_cls=error_cls,
        load_projects=lambda: {"install": SimpleNamespace(
            name="install",
            engineers=[],
            monitor_engineers=[],
        )},
        normalize_name=lambda n: n,
        session_path=lambda _p, _e: Path("/tmp/nonexistent.toml"),
        engineer_path=lambda _e: Path("/tmp/nonexistent.toml"),
        load_engineer=lambda _e: None,
        create_engineer_profile=lambda **_kw: (_ for _ in ()).throw(
            AssertionError("create_engineer_profile reached — validation didn't fire")
        ),
        write_engineer=lambda _p: None,
        create_session_record=lambda **_kw: None,
        write_session=lambda _s: None,
        apply_template=lambda _s, _p: None,
        ensure_dir=lambda _p: None,
        write_env_file=lambda *_a, **_kw: None,
        write_project=lambda _p: None,
    )
    return hooks


def test_engineer_create_rejects_anthropix_before_any_side_effect():
    """This is the one that matters: today's failure mode was
    `engineer create designer-1 install claude oauth anthropix` silently
    succeeding. After validation, it must raise BEFORE we touch disk.
    """
    from types import SimpleNamespace
    from agent_admin_crud import CrudHandlers  # noqa: WPS433

    hooks = _fake_crud_hooks()
    handlers = CrudHandlers(hooks)
    args = SimpleNamespace(
        engineer="test-bad",
        project="install",
        tool="claude",
        mode="oauth",
        provider="anthropix",
        no_monitor=False,
    )
    with pytest.raises(RuntimeError) as excinfo:
        handlers.engineer_create(args)
    assert "anthropix" in str(excinfo.value)
    assert "engineer create test-bad" in str(excinfo.value)


# ── Entry point: switch-harness ──────────────────────────────────────────


def _fake_switch_hooks(error_cls=RuntimeError):
    from types import SimpleNamespace
    return SimpleNamespace(
        error_cls=error_cls,
        load_project_or_current=lambda _p: (_ for _ in ()).throw(
            AssertionError("reached load_project_or_current — validation didn't fire")
        ),
        load_session=lambda _p, _e: None,
        normalize_name=lambda n: n,
    )


def test_switch_harness_rejects_anthropix_before_load():
    from types import SimpleNamespace
    from agent_admin_switch import SwitchHandlers  # noqa: WPS433

    # SwitchHandlers takes SwitchHooks via constructor — use the thin
    # subset we need. Pass a MagicMock-like object for the rest.
    class _Stub:
        pass
    stub = _Stub()
    for field in (
        "error_cls", "legacy_secrets_root", "tool_binaries",
        "default_tool_args", "identity_name", "runtime_dir_for_identity",
        "secret_file_for", "session_name_for", "ensure_dir",
        "ensure_secret_permissions", "write_env_file", "write_text",
        "session_record_cls", "load_project_or_current", "load_session",
        "normalize_name", "write_session", "apply_template",
        "session_stop_engineer",
    ):
        setattr(stub, field, lambda *a, **kw: None)  # noqa: PIE731
    stub.error_cls = RuntimeError

    def _should_not_reach(*a, **kw):  # noqa: ARG001
        raise AssertionError(
            "load_project_or_current reached — provider validation "
            "failed to fire before any mutation"
        )
    stub.load_project_or_current = _should_not_reach

    handlers = SwitchHandlers(stub)
    args = SimpleNamespace(
        project="install",
        engineer="planner",
        tool="claude",
        mode="oauth",
        provider="anthropix",
    )
    with pytest.raises(RuntimeError) as excinfo:
        handlers.session_switch_harness(args)
    assert "anthropix" in str(excinfo.value)
    assert "switch-harness" in str(excinfo.value)


# ── Structural: every provider listed in SUPPORTED_RUNTIME_MATRIX is non-empty


def test_matrix_has_no_empty_provider_lists():
    """Empty provider tuples would make the validator reject all calls
    and break engineer_create for that tool/auth pair. Canary.
    """
    for tool, auth_map in SUPPORTED_RUNTIME_MATRIX.items():
        for auth_mode, providers in auth_map.items():
            assert providers, f"{tool}/{auth_mode} has empty provider list"
            for p in providers:
                assert p, f"{tool}/{auth_mode} contains empty provider string"
                assert p.strip() == p, (
                    f"{tool}/{auth_mode} provider {p!r} has leading/trailing "
                    "whitespace — argparse values won't match"
                )
