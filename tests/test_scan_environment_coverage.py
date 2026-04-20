"""F7 regression: scan_credentials() must cover the canonical
~/.agent-runtime/secrets path (ClawSeat seat secrets)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]


def test_scan_credentials_finds_agent_runtime_secrets(monkeypatch, tmp_path):
    fake_home = tmp_path / "fake-user"
    fake_home.mkdir()
    secret = fake_home / ".agent-runtime" / "secrets" / "claude" / "minimax.env"
    secret.parent.mkdir(parents=True)
    secret.write_text("MINIMAX_API_KEY=testvalue_F7_regression\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("CLAWSEAT_SANDBOX_HOME_STRICT", "1")

    # Load module fresh so HOME is re-evaluated from patched os.environ
    mod_path = _REPO / "core" / "skills" / "memory-oracle" / "scripts" / "scan_environment.py"
    spec = importlib.util.spec_from_file_location("scan_env_f7", mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scan_env_f7"] = mod
    spec.loader.exec_module(mod)

    result = mod.scan_credentials()
    assert "MINIMAX_API_KEY" in result["keys"], (
        f"F7 regression: scan_credentials must find MINIMAX_API_KEY under "
        f"~/.agent-runtime/secrets/. Got: {list(result['keys'].keys())}"
    )
