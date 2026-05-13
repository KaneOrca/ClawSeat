from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "restart-seat.sh"


def test_restart_seat_translates_canonical_api_auth_to_launcher_labels() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'claude:api:deepseek) LAUNCHER_AUTH="deepseek"' in text
    assert 'claude:api:minimax) LAUNCHER_AUTH="minimax"' in text
    assert 'claude:api:xcode-best) LAUNCHER_AUTH="xcode"' in text
    assert 'codex:api:xcode-best) LAUNCHER_AUTH="xcode"' in text
    assert '--auth "$LAUNCHER_AUTH"' in text
