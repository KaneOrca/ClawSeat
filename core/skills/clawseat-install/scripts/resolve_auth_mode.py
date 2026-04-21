"""resolve_auth_mode.py — B1 auth-mode interview + batch resolution.

Drives the install-flow auth_mode decision for one claude seat. Three
input paths, tried in order:

  1. ``--auth-mode <mode> [--provider <p>]`` — CLI flag (highest priority).
  2. ``~/.agents/install-config.toml`` with ``[seats.<seat>]`` block.
  3. Interactive six-choice prompt (only if --non-interactive is absent).

On success, writes the resolved ``(auth_mode, provider)`` to stdout in
a shell-eval-friendly form so the runbook can capture it and pass it to
``start_seat.py --auth-mode … --provider …`` downstream.

Secret-file handling (``ensure_secret``):

  - ``oauth_token`` → expect ``CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-…``
    in ``~/.agents/.env.global``; if missing, prompt + shape-validate +
    append.
  - ``api`` (any provider) → expect ``<ENV_VAR>=<key>`` in
    ``~/.agents/secrets/claude/<provider>.env`` with 0o600; if missing,
    prompt + shape-validate + write.
  - ``ccr`` → probe ``127.0.0.1:3456``; warn if not listening.
  - ``oauth`` (legacy) → loud warning about Keychain popup.

Non-interactive callers (``--non-interactive`` or ``--no-secret-prompt``)
skip the secret prompt — the runbook still handles missing keys via its
own halt path.
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover — Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

# Import real_user_home, tolerating both package and script invocation.
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[3]
for _p in (str(_REPO / "core" / "lib"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from real_home import real_user_home  # noqa: E402


# ---------------------------------------------------------------------------
# Choice table
# ---------------------------------------------------------------------------

_SECRETS_DIR = lambda: real_user_home() / ".agents" / "secrets" / "claude"
_ENV_GLOBAL = lambda: real_user_home() / ".agents" / ".env.global"


@dataclass(frozen=True)
class AuthChoice:
    key: str            # "1".."6"
    auth_mode: str      # oauth_token | api | ccr | oauth
    provider: str       # anthropic | anthropic-console | minimax | xcode-best | ccr-local
    secret_kind: str | None = None      # "oauth_token" | "api_key" | None
    env_var: str | None = None          # CLAUDE_CODE_OAUTH_TOKEN | ANTHROPIC_API_KEY | …
    secret_filename: str | None = None  # basename under secrets/claude/
    shape_re: re.Pattern[str] | None = None
    shape_hint: str = ""
    deprecated: bool = False

    def secret_file(self) -> Path | None:
        return _SECRETS_DIR() / self.secret_filename if self.secret_filename else None


_SHAPE_OAT = re.compile(r"^sk-ant-oat01-[A-Za-z0-9_\-]+$")
_SHAPE_API = re.compile(r"^sk-ant-api03-[A-Za-z0-9_\-]+$")

AUTH_CHOICES: dict[str, AuthChoice] = {
    "1": AuthChoice(
        key="1", auth_mode="oauth_token", provider="anthropic",
        secret_kind="oauth_token", env_var="CLAUDE_CODE_OAUTH_TOKEN",
        shape_re=_SHAPE_OAT, shape_hint="sk-ant-oat01-…",
    ),
    "2": AuthChoice(
        key="2", auth_mode="api", provider="anthropic-console",
        secret_kind="api_key", env_var="ANTHROPIC_API_KEY",
        secret_filename="anthropic-console.env",
        shape_re=_SHAPE_API, shape_hint="sk-ant-api03-…",
    ),
    "3": AuthChoice(
        key="3", auth_mode="api", provider="minimax",
        secret_kind="api_key", env_var="MINIMAX_API_KEY",
        secret_filename="minimax.env",
    ),
    "4": AuthChoice(
        key="4", auth_mode="api", provider="xcode-best",
        secret_kind="api_key", env_var="XCODE_API_KEY",
        secret_filename="xcode-best.env",
    ),
    "5": AuthChoice(
        key="5", auth_mode="ccr", provider="ccr-local",
    ),
    "6": AuthChoice(
        key="6", auth_mode="oauth", provider="anthropic",
        deprecated=True,
    ),
}


PROMPT_BODY = """\
Auth mode for {seat} (tool=claude):

  1. oauth_token — Share one 1-year token across seats (recommended for
                   subscription users; run `claude setup-token` once).
                   Backed by your Claude Pro/Max subscription.
  2. api (anthropic-console) — Per-seat API key from Anthropic Console
                   (Claude Code scoped role). Pay-as-you-go; ideal for
                   isolation or heavy concurrent use.
  3. api (minimax) — Route to MiniMax's Anthropic-compatible endpoint.
                   Cheapest; different model quality vs Anthropic direct.
  4. api (xcode-best) — Route to xcode.best aggregator. GPT-5.4 via
                   Codex compat; not Claude models actually.
  5. ccr — Route through local Claude Code Router proxy. Multi-provider
                   switching at runtime.
  6. oauth (legacy) — Original keychain OAuth. NOT recommended due to
                   Keychain expiry popup (upstream #43000). Use only if
                   none of the above fit.
"""


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def choice_from_auth_mode(auth_mode: str, provider: str | None = None) -> AuthChoice:
    """Map ``(auth_mode, provider)`` back onto one of the six canonical choices.

    Raises ``ValueError`` if the combination isn't supported.
    """
    am = (auth_mode or "").strip()
    pv = (provider or "").strip() or None
    candidates = [c for c in AUTH_CHOICES.values() if c.auth_mode == am]
    if not candidates:
        raise ValueError(f"unknown auth_mode {auth_mode!r}")
    if pv is None:
        # Unambiguous only when auth_mode has a single choice.
        if len(candidates) == 1:
            return candidates[0]
        names = sorted(c.provider for c in candidates)
        raise ValueError(
            f"auth_mode={am!r} requires --provider; choose one of {names}"
        )
    for c in candidates:
        if c.provider == pv:
            return c
    raise ValueError(
        f"auth_mode={am!r} provider={pv!r} is not a B1 choice "
        f"(valid providers: {sorted(c.provider for c in candidates)})"
    )


def load_batch_config(path: Path, seat: str) -> dict[str, str] | None:
    """Return ``{'auth_mode': ..., 'provider': ...}`` for seat, or None.

    Missing file / missing seat block → None. Malformed TOML raises.
    """
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    seats = data.get("seats")
    if not isinstance(seats, dict):
        return None
    cfg = seats.get(seat)
    if not isinstance(cfg, dict):
        return None
    if "auth_mode" not in cfg:
        return None
    return {
        "auth_mode": str(cfg["auth_mode"]),
        "provider": str(cfg.get("provider", "")) or None,  # type: ignore[dict-item]
    }


def prompt_interactive(
    seat: str,
    *,
    input_fn: Callable[[str], str] = input,
    stream_out: Any = sys.stderr,
) -> AuthChoice:
    """Loop until the operator picks a valid choice."""
    print(PROMPT_BODY.format(seat=seat), file=stream_out)
    while True:
        raw = input_fn("[1/2/3/4/5/6, default=1]: ").strip() or "1"
        if raw in AUTH_CHOICES:
            return AUTH_CHOICES[raw]
        print(
            f"invalid choice {raw!r}; enter 1, 2, 3, 4, 5, or 6",
            file=stream_out,
        )


def resolve(
    seat: str,
    *,
    cli_auth_mode: str | None = None,
    cli_provider: str | None = None,
    batch_config: Path | None = None,
    interactive: bool = True,
    input_fn: Callable[[str], str] = input,
    stream_out: Any = sys.stderr,
) -> AuthChoice:
    """Pick a choice for ``seat`` using CLI / batch / interactive in order."""
    if cli_auth_mode:
        return choice_from_auth_mode(cli_auth_mode, cli_provider)
    if batch_config is not None:
        cfg = load_batch_config(batch_config, seat)
        if cfg:
            return choice_from_auth_mode(cfg["auth_mode"], cfg.get("provider"))
    if not interactive:
        raise RuntimeError(
            f"seat {seat!r}: no auth_mode in CLI flag or batch config, "
            f"and interactive prompt disabled"
        )
    return prompt_interactive(seat, input_fn=input_fn, stream_out=stream_out)


# ---------------------------------------------------------------------------
# Secret-file management
# ---------------------------------------------------------------------------

def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _append_env_global(env_path: Path, var: str, value: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    prior = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    sep = "" if (not prior or prior.endswith("\n")) else "\n"
    new = f"{prior}{sep}{var}={value}\n"
    env_path.write_text(new, encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass


def _write_secret_file(path: Path, var: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{var}={value}\n", encoding="utf-8")
    path.chmod(0o600)


def _port_listening(host: str = "127.0.0.1", port: int = 3456, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionError):
        return False


def _prompt_secret(
    choice: AuthChoice,
    *,
    input_fn: Callable[[str], str],
    stream_out: Any,
    max_retries: int = 3,
) -> str:
    """Read a secret from the operator, shape-validating when a regex is set."""
    label = f"{choice.env_var} for {choice.provider}"
    for attempt in range(max_retries):
        raw = input_fn(f"paste {label}: ").strip()
        if not raw:
            print("(empty input, try again)", file=stream_out)
            continue
        if choice.shape_re and not choice.shape_re.match(raw):
            print(
                f"shape check failed (expected {choice.shape_hint or choice.shape_re.pattern})",
                file=stream_out,
            )
            continue
        return raw
    raise RuntimeError(
        f"{choice.env_var}: no valid input after {max_retries} attempts"
    )


def ensure_secret(
    choice: AuthChoice,
    *,
    env_global: Path | None = None,
    input_fn: Callable[[str], str] = input,
    stream_out: Any = sys.stderr,
    non_interactive: bool = False,
) -> dict[str, Any]:
    """Verify / install the secret for a choice.

    Returns a small report dict: ``{'action': 'existing'|'written'|'warned'|'skipped',
    'path': str|None, 'missing': bool}``. Raises RuntimeError on hard failures.
    """
    env_global = env_global or _ENV_GLOBAL()
    report: dict[str, Any] = {"action": "existing", "path": None, "missing": False}

    if choice.secret_kind == "oauth_token":
        existing = _read_env_file(env_global).get(choice.env_var or "", "")
        if existing and (not choice.shape_re or choice.shape_re.match(existing)):
            report["path"] = str(env_global)
            return report
        if non_interactive:
            report["action"] = "skipped"
            report["missing"] = True
            return report
        print(
            f"{choice.env_var} missing or malformed in {env_global}.\n"
            "Run `claude setup-token` in another terminal, then paste the output here.",
            file=stream_out,
        )
        value = _prompt_secret(choice, input_fn=input_fn, stream_out=stream_out)
        _append_env_global(env_global, choice.env_var or "", value)
        report["action"] = "written"
        report["path"] = str(env_global)
        return report

    if choice.secret_kind == "api_key":
        path = choice.secret_file()
        assert path is not None  # api_key choices always set secret_filename
        if path.is_file():
            # Enforce 0o600 even if it already exists.
            try:
                mode = stat.S_IMODE(path.stat().st_mode)
                if mode != 0o600:
                    path.chmod(0o600)
            except OSError:
                pass
            existing = _read_env_file(path).get(choice.env_var or "", "")
            if existing and (not choice.shape_re or choice.shape_re.match(existing)):
                report["path"] = str(path)
                return report
        if non_interactive:
            report["action"] = "skipped"
            report["missing"] = True
            report["path"] = str(path)
            return report
        print(
            f"{choice.env_var} missing or malformed in {path}.",
            file=stream_out,
        )
        value = _prompt_secret(choice, input_fn=input_fn, stream_out=stream_out)
        _write_secret_file(path, choice.env_var or "", value)
        report["action"] = "written"
        report["path"] = str(path)
        return report

    if choice.auth_mode == "ccr":
        listening = _port_listening("127.0.0.1", 3456)
        report["path"] = "127.0.0.1:3456"
        if not listening:
            print(
                "warning: ccr not detected on 127.0.0.1:3456. "
                "Start it with `ccr start` in another terminal before running the seat.",
                file=stream_out,
            )
            report["action"] = "warned"
            report["missing"] = True
        return report

    if choice.deprecated:  # oauth legacy
        print(
            "WARNING: you chose 'oauth' (legacy). "
            "Expect macOS Keychain popups on every seat start "
            "(upstream anthropics/claude-code#43000). "
            "Press Enter to continue, or Ctrl-C to re-pick.",
            file=stream_out,
        )
        if not non_interactive:
            try:
                input_fn("")
            except EOFError:
                pass
        report["action"] = "warned"
        return report

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resolve_auth_mode.py",
        description=(
            "B1 install-flow auth-mode resolver. Picks one of six canonical "
            "(auth_mode, provider) pairs for a claude seat, validates/writes "
            "the corresponding secret, and prints the resolution for the "
            "runbook to feed into start_seat.py."
        ),
    )
    parser.add_argument("--seat", required=True, help="Seat id, e.g. planner, builder-1.")
    parser.add_argument(
        "--auth-mode", default=None,
        help="Bypass the prompt: oauth_token | api | ccr | oauth.",
    )
    parser.add_argument(
        "--provider", default=None,
        help="Required with --auth-mode=api (anthropic-console | minimax | xcode-best).",
    )
    parser.add_argument(
        "--batch-config", default=None,
        help="Path to install-config.toml. Default: ~/.agents/install-config.toml.",
    )
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="Fail if no CLI/batch answer is available; do not prompt.",
    )
    parser.add_argument(
        "--no-secret-prompt", action="store_true",
        help="Do not prompt for/validate the seat's secret file.",
    )
    parser.add_argument(
        "--env-global", default=None,
        help="Override the env.global path (tests).",
    )
    return parser


def _default_batch_path(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    default = real_user_home() / ".agents" / "install-config.toml"
    return default if default.exists() else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    batch_config = _default_batch_path(args.batch_config)
    try:
        choice = resolve(
            args.seat,
            cli_auth_mode=args.auth_mode,
            cli_provider=args.provider,
            batch_config=batch_config,
            interactive=not args.non_interactive,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    env_global = Path(args.env_global).expanduser() if args.env_global else None
    try:
        report = ensure_secret(
            choice,
            env_global=env_global,
            non_interactive=args.non_interactive or args.no_secret_prompt,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    # Shell-eval-friendly output. The runbook captures these and forwards
    # them to start_seat.py --tool claude --auth-mode … --provider …
    print(f"AUTH_MODE={choice.auth_mode}")
    print(f"PROVIDER={choice.provider}")
    if choice.secret_kind == "api_key" and choice.secret_file():
        print(f"SECRET_FILE={choice.secret_file()}")
    print(f"SECRET_ACTION={report['action']}")
    if report.get("missing"):
        # Non-fatal, but visible. Runbook may treat as halt.
        print("SECRET_MISSING=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
