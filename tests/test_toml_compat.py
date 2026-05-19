from __future__ import annotations

import io
import textwrap
from pathlib import Path

import _toml_compat


def test_fallback_parses_quoted_dotted_provider_table(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(_toml_compat, "_toml_module", lambda: None)
    home = tmp_path / "home"
    secret_file = home / ".agents" / "secrets" / "claude" / "anthropic.env"

    data = _toml_compat.loads_safe(
        textwrap.dedent(
            f"""\
            version = 1

            [providers."anthropic"]
            tool = "claude"
            kind = "oauth_token"
            family = "anthropic"
            secret_file = "{secret_file}"
            created_at = "2026-05-14T00:00:00Z"
            updated_at = "2026-05-14T00:00:00Z"
            """
        )
    )

    assert sorted(data["providers"]) == ["anthropic"]
    assert data["providers"]["anthropic"]["tool"] == "claude"


def test_fallback_parses_project_seat_overrides_and_multiline_arrays(monkeypatch) -> None:
    monkeypatch.setattr(_toml_compat, "_toml_module", lambda: None)
    seat = "cartooner-product-solo-planner"

    data = _toml_compat.loads_safe(
        textwrap.dedent(
            f"""\
            name = "cartooner-front"
            repo_root = "/repo"
            monitor_session = "project-cartooner-front-monitor"
            engineers = [
              "memory",
              "{seat}",
            ]
            monitor_engineers = ["memory", "{seat}"]

            [seat_overrides.{seat}]
            tool = "claude"
            auth_mode = "oauth_token"
            provider = "anthropic"
            capabilities = ["root-cause research", "tests"]
            active_loop_owner = true
            """
        )
    )

    assert data["engineers"] == ["memory", seat]
    assert data["seat_overrides"][seat]["provider"] == "anthropic"
    assert data["seat_overrides"][seat]["capabilities"] == ["root-cause research", "tests"]
    assert data["seat_overrides"][seat]["active_loop_owner"] is True


def test_fallback_parses_array_of_tables(monkeypatch) -> None:
    monkeypatch.setattr(_toml_compat, "_toml_module", lambda: None)

    data = _toml_compat.load_safe(
        io.BytesIO(
            textwrap.dedent(
                """\
                [[engineers]]
                id = "planner"
                skills = ["a", "b"]

                [[engineers]]
                id = "builder"
                """
            ).encode("utf-8")
        )
    )

    assert data["engineers"] == [
        {"id": "planner", "skills": ["a", "b"]},
        {"id": "builder"},
    ]
